############################################################################
#
# MODULE:       gs.ssurgo.query
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Import SSURGO data and query via natural language
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import os
import grass.script as gs
from rag.kb import build_kb, load_kb
from rag.sqlgen import plan_and_run_sql


def _require_mukey(mapunit):
    # verify mukey exists
    cols = gs.read_command(
        "v.db.select", map=mapunit, columns="mukey", separator="|", layer=1, flags="c"
    )
    if "mukey" not in (cols or ""):
        gs.fatal("Mapunit layer must have a 'mukey' column.")


def _materialize_result_to_vector(mapunit, out_map, value_by_mukey, col="value"):
    gs.run_command("g.copy", vector=f"{mapunit},{out_map}", overwrite=gs.overwrite())
    try:
        gs.run_command("v.db.addcolumn", map=out_map, columns=f"{col} double precision")
    except gs.CalledModuleError:
        pass
    for mukey, val in value_by_mukey.items():
        if val is None:
            continue
        gs.run_command(
            "v.db.update",
            map=out_map,
            column=col,
            value=str(val),
            where=f"mukey='{mukey}'",
        )


def _materialize_result_to_raster(mapunit, out_rast, value_by_mukey, col="value"):
    tmpv = f"{out_rast}_tmpv"
    gs.run_command("g.copy", vector=f"{mapunit},{tmpv}", overwrite=True)
    try:
        gs.run_command("v.db.addcolumn", map=tmpv, columns=f"{col} double precision")
    except gs.CalledModuleError:
        pass
    for mukey, val in value_by_mukey.items():
        if val is None:
            continue
        gs.run_command(
            "v.db.update",
            map=tmpv,
            column=col,
            value=str(val),
            where=f"mukey='{mukey}'",
        )
    gs.run_command(
        "v.to.rast",
        input=tmpv,
        output=out_rast,
        use="attr",
        attribute_column=col,
        overwrite=gs.overwrite(),
    )
    gs.run_command("g.remove", type="vector", name=tmpv, flags="f")


def _write_series_table(rows, output):
    # rows expected: list of dicts with keys among {mukey,cokey,compname,comppct_r,value}
    import csv
    import tempfile

    fp = os.path.join(tempfile.gettempdir(), f"{output}.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["mukey", "cokey", "compname", "comppct_r", "value"]
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    gs.run_command("db.in.ogr", input=fp, output=output, overwrite=gs.overwrite())
    return fp


def main():
    options, flags = gs.parser()
    mode = options["mode"]
    kb_dir = options["kb_dir"]
    sqlite_p = options["sqlite"]
    pdfs = options["pdfs"]
    ask_q = options["ask"]
    mapunit = options["mapunit"]
    output = options["output"]
    ofmt = options["format"]
    method = (options["method"] or "").upper() or None
    depth = options["depth"]
    sda = flags["s"]

    if mode == "build_kb":
        if not sqlite_p and not sda:
            gs.fatal("Provide --sqlite=… or use -s for SDA.")
        pdf_list = [p.strip() for p in (pdfs or "").split(",") if p.strip()]
        build_kb(sqlite_path=sqlite_p, kb_dir=kb_dir, pdf_paths=pdf_list, use_sda=sda)
        gs.message(f"KB built at {kb_dir}")
        return

    if mode == "ask":
        if not (ask_q and mapunit and output and ofmt):
            gs.fatal("mode=ask requires ask=, mapunit=, output=, format=")
        _require_mukey(mapunit)
        kb = load_kb(kb_dir)
        result = plan_and_run_sql(
            question=ask_q,
            kb=kb,
            sqlite_path=sqlite_p,
            use_sda=sda,
            controls={"method": method, "depth_cm": int(depth) if depth else None},
        )
        value_by_mukey = result["mu_values"]  # dict mukey -> value
        components_tbl = result.get("components")  # optional per-component rows
        sql_used = result["sql"]
        gs.message(f"Planned SQL:\n{sql_used}")

        if ofmt == "vector":
            _materialize_result_to_vector(mapunit, output, value_by_mukey, col="value")
        elif ofmt == "raster":
            _materialize_result_to_raster(mapunit, output, value_by_mukey, col="value")
        elif ofmt == "series":
            if not components_tbl:
                gs.fatal(
                    "This query didn't produce per-component rows. Try a series-oriented question (e.g., 'soil series')."
                )
            _write_series_table(components_tbl, output)
        else:
            gs.fatal("format must be vector|raster|series")
        gs.message(f"Wrote {ofmt} <{output}>.")


if __name__ == "__main__":
    options = {
        "mode": {"type": "string", "required": True, "label": "build_kb | ask"},
        "kb_dir": {
            "type": "string",
            "required": True,
            "label": "Directory for vector index",
        },
        "sqlite": {
            "type": "string",
            "required": False,
            "label": "Path to SSURGO SQLite (omit with -s)",
        },
        "pdfs": {
            "type": "string",
            "required": False,
            "label": "Comma-separated PDF paths for SSURGO docs",
        },
        "ask": {
            "type": "string",
            "required": False,
            "label": "Natural-language question",
        },
        "mapunit": {
            "type": "string",
            "required": False,
            "label": "Mapunit polygon vector (must have mukey)",
        },
        "output": {"type": "string", "required": False, "label": "Output name"},
        "format": {
            "type": "string",
            "required": False,
            "label": "vector|raster|series",
        },
        "method": {
            "type": "string",
            "required": False,
            "label": "Aggregation override (DCP,DCD,WA,MOM,ML,LL,PP,NAN)",
        },
        "depth": {
            "type": "string",
            "required": False,
            "label": "Depth limit in cm (e.g., 100)",
        },
    }
    flags = {"s": {"label": "Use SDA web service (no local SQLite)"}}
    gs.parser()
    main()
