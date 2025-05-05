#!/usr/bin/env python3

############################################################################
#
# MODULE:       v.in.ssurgo
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Get SSURGO ZIP files from Web Soil Survey
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

# %module
# % description: Download and import SSURGO data from the USDA for a specified
# %              soil survey area
# % keyword: vector
# % keyword: import
# % keyword: soils
# % keyword: SSURGO
# %end

# %option G_OPT_V_OUTPUT
# % description: Name for output vector map of soil polygons
# %end

# %option
# % key: areasymbol
# % type: string
# % description: SSURGO Area Symbol (e.g., NC025)
# % required: yes
# %end

# %option
# % key: format
# % type: string
# % options: sqlite,csv
# % answer: sqlite
# % description: Format of tabular data to retain locally (if desired)
# % required: no
# % guisection: Tabular data
# %end

# %option
# % key: dir
# % type: string
# % description: Directory to download and unpack SSURGO data
# % required: no
# % answer: /tmp
# % guisection: Download
# %end

# %flag
# % key: t
# % description: Load SSURGO tabular data into a SQLite database (for inspection)
# % guisection: Tabular data
# %end

# %flag
# % key: q
# % description: Quiet mode
# % guisection: Output
# %end


import os
import zipfile
import tempfile
import requests
import grass.script as gs
from pathlib import Path

# https://ncss-tech.github.io/soilDB/reference/downloadSSURGO.html


def download_ssurgo_zip(areasymbol, download_dir):
    base_url = "https://websoilsurvey.sc.egov.usda.gov/DSD/Download/AOI"
    zipname = f"{areasymbol}.zip"
    url = f"{base_url}/{zipname}"
    local_path = os.path.join(download_dir, zipname)

    if os.path.exists(local_path):
        gs.message(f"Using cached file: {local_path}")
        return local_path

    gs.message(f"Downloading {url}")
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        gs.fatal(f"Failed to download SSURGO data for {areasymbol}: {r.status_code}")

    with open(local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return local_path


def extract_and_import(zip_path, output, load_tabular, fmt):
    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(tmpdir)

    shp_candidates = list(Path(tmpdir).rglob("*Soilmu_a*.shp"))
    if not shp_candidates:
        gs.fatal("Could not find Soilmu_a shapefile in SSURGO download.")

    shp_path = str(shp_candidates[0])
    gs.message(f"Importing {shp_path}")
    gs.run_command("v.import", input=shp_path, output=output, overwrite=True)

    if load_tabular:
        if fmt == "sqlite":
            db_candidates = list(Path(tmpdir).rglob("*.mdb"))
            if not db_candidates:
                gs.warning("No .mdb file found; SQLite DB will not be created.")
                return
            db_path = str(db_candidates[0])
            gs.message(f"Extracted Access DB (not loaded): {db_path}")
            # NOTE: Use mdbtools or pyodbc externally if needed
        else:
            csv_candidates = list(Path(tmpdir).rglob("tabular/*.csv"))
            if not csv_candidates:
                gs.warning("No CSV files found in tabular directory.")
                return
            gs.message("Tabular CSV files extracted:")
            for csv in csv_candidates:
                gs.message(f" - {csv}")


def main():
    output = options["output"]
    areasymbol = options["areasymbol"]
    fmt = options["format"]
    download_dir = options["dir"]
    load_tabular = flags["t"]

    zip_path = download_ssurgo_zip(areasymbol, download_dir)
    extract_and_import(zip_path, output, load_tabular, fmt)

    gs.message(f"SSURGO data for area symbol '{areasymbol}' imported as <{output}>")


if __name__ == "__main__":
    options, flags = gs.parser()
    main()
