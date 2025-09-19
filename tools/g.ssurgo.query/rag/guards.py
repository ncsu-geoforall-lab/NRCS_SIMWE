############################################################################
#
# MODULE:       g.ssurgo.query/rag/gaurds.py
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Gardrails for SSURGO RAG SQL generation
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import re
import sqlite3

ALLOWED_JOIN_PAIRS = {
    ("mapunit", "mukey", "component", "mukey"),
    ("component", "cokey", "chorizon", "cokey"),
    ("mapunit", "mukey", "muaggatt", "mukey"),  # MU-level direct
}


def inspect_schema(sqlite_path):
    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()
    tables = {
        t for (t,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    cols = {t: set() for t in tables}
    for t in tables:
        for r in cur.execute(f"PRAGMA table_info('{t}')"):
            cols[t].add(r[1].lower())
    con.close()
    return tables, cols


def validate_sql(sql, sqlite_path):
    if ";" in sql:
        raise ValueError("Semicolons forbidden.")
    if not re.match(r"^\s*(with|select)\b", sql, re.I):
        raise ValueError("Only SELECT/CTE allowed.")
    tables, cols = inspect_schema(sqlite_path)
    used_tables = {t for t in tables if re.search(rf"\b{t}\b", sql, re.I)}
    if not used_tables:
        raise ValueError("No known SSURGO tables referenced.")

    # Verify qualified columns exist
    for t in used_tables:
        for m in re.finditer(rf"\b{t}\.(\w+)\b", sql, re.I):
            if m.group(1).lower() not in cols[t]:
                raise ValueError(f"Unknown column {t}.{m.group(1)}")

    # Light join sanity: require MU→CO for horizon, and prefer MUAGGATT for MU-only asks
    # (Optional: parse ON clauses fully and compare to ALLOWED_JOIN_PAIRS)
    return True
