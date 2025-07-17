#!/usr/bin/env python3

############################################################################
#
# MODULE:       r.in.ssurgo
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Get SSURGO ZIP files from Web Soil Survey
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

# %module
# % description: Download and import SSURGO data from the USDA for a specified soil survey area.
# % keyword: raster
# % keyword: import
# % keyword: soils
# % keyword: SSURGO
# %end

# %option G_OPT_R_OUTPUT
# % description: Name for output soil grid
# %end

# %option
# % key: mukey
# % type: string
# % required: yes
# % multiple: no
# % options: gNATSGO,gSSURGO,RSS,STATSGO,PR_SSURGO,HI_SSURGO
# % description: Name of the raster map unit key grid to access
# % descriptions: gNATSGO;Gridded National Soil Survey Geographic Database;gSSURGO;Gridded SSURGO;RSS;Rapid Soil Survey;STATSGO;State Soil Geographic Database;PR_SSURGO;Puerto Rico SSURGO;HI_SSURGO;Hawaii SSURGO
# % guisection: Output
# % answer: input
# %end

import os
import sys
import tempfile
import grass.script as gs
from grass.pygrass.utils import get_lib_path
from contextlib import contextmanager


# https://ncss-tech.github.io/soilDB/reference/downloadSSURGO.html
# https://github.com/ncss-tech/soilDB/blob/master/R/mukey-WCS.R
# https://ncss-tech.github.io/AQP/soilDB/WCS-demonstration-01.html
@contextmanager
def add_sys_path(new_path: str):
    """
    Context manager to temporarily add a directory to the Python module search path (sys.path).

    This function allows you to temporarily include a specified directory in the Python
    module search path. Once the context is exited, the original sys.path is restored.

    Args:
        new_path (str): The directory path to be added to sys.path.

    Yields:
        None: This context manager does not return any value.

    Example:
        with add_sys_path('/path/to/directory'):
        # After the context, sys.path is restored to its original state.
    """
    original_sys_path = sys.path[:]
    sys.path.append(new_path)
    try:
        yield
    finally:
        sys.path = original_sys_path


def main():
    # Import dependencies
    path = get_lib_path(modname="r.soildb", libname="soillib")
    if path is None:
        gs.fatal("Not able to find the soillib library directory.")

    with add_sys_path(path):
        try:
            import soillib as libsoil
        except ImportError as err:
            gs.fatal(f"Unable to import staclib: {err}")

    mukey = options["mukey"]
    output = options["output"]

    wcs = libsoil.MUKEY_WCS(mukey=mukey)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tif_path = tmp.name

        try:
            # Download and import
            wcs.fetch_wcs(output_raster=output, geotiff_path=tif_path)
        finally:
            if os.path.exists(tif_path):
                os.remove(tif_path)

    # wcs.get_coverage()


if __name__ == "__main__":
    options, flags = gs.parser()
    main()
