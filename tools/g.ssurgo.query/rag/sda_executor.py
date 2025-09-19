############################################################################
#
# MODULE:       g.ssurgo.query/rag/sda_executor.py
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Query SSURGO RAG via Soil Data Access (SDA) web service
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import re
import requests
from typing import Dict, Any

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post"

# very conservative guardrails
READONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE | re.DOTALL)
BAN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|PRAGMA)\b",
    re.IGNORECASE,
)
ALLOWLIST = {
    # add the SSURGO tabulars you actually query
    "mapunit",
    "component",
    "chorizon",
    "muaggatt",
    "cointerp",
    "sainterp",
    "legend",
    "sacatalog",
    "chtexture",
    "chtexturegrp",
    "chfrags",
}


def _tables_ok(sql: str) -> bool:
    # naive table detector; harden if you support CTEs/aliases
    found = {
        t.lower()
        for t in re.findall(r"\bfrom\s+([a-z_][a-z0-9_]*)(?:\s|$)", sql, re.IGNORECASE)
    }
    found |= {
        t.lower()
        for t in re.findall(r"\bjoin\s+([a-z_][a-z0-9_]*)(?:\s|$)", sql, re.IGNORECASE)
    }
    return all(f in ALLOWLIST for f in found)


class SDAExecutor:
    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def run(self, sql: str) -> Dict[str, Any]:
        if not READONLY.search(sql) or BAN.search(sql) or not _tables_ok(sql):
            raise ValueError(
                "Rejected SQL (must be read-only and use allow-listed tables)."
            )
        payload = {"format": "JSON", "query": sql}
        r = requests.post(SDA_URL, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # SDA returns {"Table":[{...}, ...]} by default
        rows = data.get("Table", data)
        return {"rows": rows}
