#!/usr/bin/env python3

############################################################################
#
# MODULE:       r.in.soilgrids
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Get SoilGrids 2.0 Property Estimates
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

# %module
# % description: Import soil property rasters from ISRIC SoilGrids (2020)
# %              global database
# % keyword: raster
# % keyword: import
# % keyword: soil
# % keyword: soilgrids
# %end

# %option G_OPT_R_OUTPUT
# % description: Output raster base name (e.g., sand_0_5cm)
# %end

# %option
# % key: property
# % type: string
# % required: yes
# % options: bdod,cec,cfvo,clay,nitrogen,ocd,phh2o,sand,silt,soc
# % answer: bdod,cec,cfvo,clay,nitrogen,ocd,phh2o,sand,silt,soc
# % description: Soil property to import (e.g., sand, clay, soc)
# %end

# %option
# % key: depth
# % type: string
# % required: yes
# % options: 0-5cm,5-15cm,15-30cm,30-60cm,60-100cm,100-200cm
# % description: Depth interval (e.g., 0-5cm)
# %end

# %option
# % key: target_resolution
# % type: double
# % required: no
# % answer: 250
# % description: Spatial resolution of the output raster in meters
# %end

# %option
# % key: summary_type
# % type: string
# % required: no
# % multiple: yes
# % description: One or more of "Q0.05", "Q0.5", "Q0.95", "mean"; these are summary statistics that correspond to 5th, 50th, 95th percentiles, and mean value for selected variables.
# %end

# %option
# % key: bbox
# % type: string
# % description: Bounding box to extract (xmin,ymin,xmax,ymax) in WGS84
# % required: yes
# % guisection: Region
# %end

# %flag
# % key: s
# % description: Import standard deviation layer instead of mean
# % guisection: Property
# %end

# %flag
# % key: q
# % description: Quiet mode
# % guisection: Output
# %end


import sys
import tempfile
import requests
import grass.script as gs
from grass.pygrass.utils import get_lib_path
from contextlib import contextmanager

BASE_URL = "https://files.isric.org/soilgrids/latest/data"


@contextmanager
def add_sys_path(new_path):
    """Add a path to sys.path and remove it when done"""
    original_sys_path = sys.path[:]
    sys.path.append(new_path)
    try:
        yield
    finally:
        sys.path = original_sys_path


def download_soilgrids_tile(property, depth, bbox, use_sd=False):
    stat = "uncertainty" if use_sd else "mean"
    prop_dir = f"{BASE_URL}/{property}/{depth}/{stat}.tif"

    gs.message(f"Downloading {property} at {depth} ({stat})...")

    response = requests.get(prop_dir, stream=True)
    if response.status_code != 200:
        gs.fatal(f"Failed to download: {prop_dir} — Status {response.status_code}")

    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            tmpfile.write(chunk)
    tmpfile.close()

    return tmpfile.name


def import_cog(tif_path, bbox, output_name):
    xmin, ymin, xmax, ymax = map(float, bbox.split(","))
    region = f"{xmin},{xmax},{ymin},{ymax}"
    gs.run_command(
        "r.import",
        input=tif_path,
        output=output_name,
        extent=region,
        resample="bilinear",
        resolution="",
        resolution_value="",
        title="",
        flags="o",
        memory=1000,
        overwrite=True,
    )


def main():
    output = options["output"]
    prop = options["property"]
    depth = options["depth"].replace("-", "_").replace("cm", "cm")
    bbox = options["bbox"]
    use_sd = flags["s"]

    # Import dependencies
    path = get_lib_path(modname="t.stac", libname="staclib")
    if path is None:
        gs.fatal("Not able to find the stac library directory.")

    with add_sys_path(path):
        try:
            import soillib as libsoil  # noqa: F401
        except ImportError as err:
            gs.fatal(f"Unable to import libsoil: {err}")

    tif_path = download_soilgrids_tile(prop, depth, bbox, use_sd=use_sd)

    gs.message(f"Imported SoilGrids raster <{output}>")
    return tif_path


if __name__ == "__main__":
    options, flags = gs.parser()
    main()
