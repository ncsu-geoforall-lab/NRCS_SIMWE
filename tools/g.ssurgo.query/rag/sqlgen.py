############################################################################
#
# MODULE:       g.ssurgo.query/rag/sqlgen.py
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      SQL generation and execution for SSURGO RAG
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate

SYSTEM = """You are a SSURGO text-to-SQL planner.
Rules:
- Use only tables/columns that exist in the provided schema dump.
- Legal horizon path: mapunit.mukey -> component.mukey -> chorizon.cokey.
- If an attribute exists at MU level (muaggatt.*), prefer that (No Aggregation Necessary).
- Mapunit-level Weighted Average uses component percent: comppct_r/100.
- Horizon depth rollups weight by thickness: (MIN(hzdepb_r, {depth_cm}) - hzdept_r), clipped to depth.
- Output columns must be (mukey, value). For “series” requests also produce a per-component SELECT with
  columns (mukey, cokey, compname, comppct_r, value) after a line: ---SERIES---.
- Never generate DDL, INSERT/UPDATE/DELETE, PRAGMA, or semicolons.
"""

FEWSHOTS = [
    (
        "hydric rating by map unit",
        "WITH x AS (SELECT mu.mukey, ma.hydclprs AS value FROM mapunit mu JOIN muaggatt ma USING(mukey)) SELECT mukey,value FROM x",
    ),
    (
        "weighted average awc to 100 cm",
        """WITH hz AS (
          SELECT mu.mukey, co.cokey, co.comppct_r,
                 MAX(0, MIN(ch.hzdepb_r, 100) - ch.hzdept_r) AS thk, ch.awc_r
          FROM mapunit mu JOIN component co USING(mukey) JOIN chorizon ch USING(cokey)
          WHERE ch.hzdept_r < 100
        ),
        co_agg AS (
          SELECT mukey, cokey, SUM(awc_r*thk)/NULLIF(SUM(thk),0) AS comp_val
          FROM hz GROUP BY mukey,cokey
        ),
        mu_agg AS (
          SELECT co.mukey,
                 SUM(comp_val*(co.comppct_r/100.0))/NULLIF(SUM(co.comppct_r/100.0),0) AS value
          FROM co_agg JOIN component co USING(mukey,cokey) GROUP BY co.mukey
        )
        SELECT mukey,value FROM mu_agg""",
    ),
    (
        "list soil series",
        "---SERIES---\nSELECT mu.mukey, co.cokey, co.compname, co.comppct_r, NULL as value FROM mapunit mu JOIN component co USING(mukey)",
    ),
]


def make_prompt(depth_cm: int | None):
    depth = depth_cm if depth_cm is not None else 9999
    sys = SYSTEM.format(depth_cm=depth)
    return ChatPromptTemplate.from_messages(
        [
            ("system", sys),
            (
                "human",
                "Schema:\n{schema}\n\nContext:\n{context}\n\nExamples:\n{shots}\n\nQuestion:\n{question}\nReturn only the SQL.",
            ),
        ]
    )


def plan_sql(question, retriever, schema_text, depth_cm=None):
    ctx = "\n\n".join(
        retriever.similarity_search(
            question, k=6, fetch_k=8, lambda_mult=0.0
        ).page_content
        for _ in range(1)
    )
    shots = "\n\n".join([f"Q: {q}\nSQL:\n{a}" for q, a in FEWSHOTS])
    prompt = make_prompt(depth_cm)
    # You can swap in any LC LLM here
    from langchain.chat_models import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm
    sql = chain.invoke(
        {"schema": schema_text, "context": ctx, "shots": shots, "question": question}
    ).content.strip()
    return sql


def run_sql(sqlite_path, sql):
    db = SQLDatabase.from_uri(f"sqlite:///{sqlite_path}")
    from sqlalchemy import text

    parts = sql.split("---SERIES---")
    mu_sql = parts[0].strip()
    series_sql = parts[1].strip() if len(parts) > 1 else None

    with db._engine.connect() as conn:
        mu_rows = list(conn.execute(text(mu_sql)).fetchall())
        series_rows = (
            list(conn.execute(text(series_sql)).fetchall()) if series_sql else None
        )

    mu = {str(m): v for (m, v) in mu_rows}
    comp = None
    if series_rows:
        comp = [
            {
                "mukey": r[0],
                "cokey": r[1],
                "compname": r[2],
                "comppct_r": r[3],
                "value": r[4],
            }
            for r in series_rows
        ]
    return mu, comp
