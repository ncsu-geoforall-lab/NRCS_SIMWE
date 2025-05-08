#!/usr/bin/env python3

############################################################################
#
# MODULE:       soillib
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Soil property definitions and conversion factors
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import sys
from contextlib import contextmanager
import gettext
import grass.script as gs
import grass.script.core as gcore
from grass.exceptions import CalledModuleError

# Set up translation function
_ = gettext.gettext


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


def region_to_wgs84_decimal_degrees_bbox():
    """convert region bbox to wgs84 decimal degrees bbox"""
    region = gs.parse_command("g.region", quiet=True, flags="ubg")
    bbox = [
        float(c)
        for c in [region["ll_w"], region["ll_s"], region["ll_e"], region["ll_n"]]
    ]
    return bbox


def region_to_crs_bbox(target_crs: str):
    """Convert GRASS region bounds to a bounding box in another CRS using m.proj."""
    region = gs.region()
    # Extract corner coordinates
    west, south, east, north = region["w"], region["s"], region["e"], region["n"]

    # Format input coordinates for m.proj (as string input to stdin)
    coords = f"{west} {south}\n{east} {north}\n"

    proj_in = gs.parse_command("g.proj", flags="j")
    proj_out = gs.parse_command("g.proj", flags="j", proj=target_crs)

    try:
        output = gs.read_command(
            "m.proj",
            input="-",
            proj_in=proj_in,
            proj_out=proj_out,
            stdin=coords,
            quiet=True,
        )
    except CalledModuleError as e:
        gs.fatal(f"Projection failed: {e}")

    # Parse output
    lines = output.strip().splitlines()
    ll_x, ll_y = map(float, lines[0].split())  # Lower-left
    ur_x, ur_y = map(float, lines[1].split())  # Upper-right

    return [ll_x, ll_y, ur_x, ur_y]


def check_addon_installed(addon: str, fatal=True) -> None:
    """Check if a GRASS GIS addon is installed"""
    if not gcore.find_program(addon, "--help"):
        call = gcore.fatal if fatal else gcore.warning
        call(
            _(
                "Addon {a} is not installed. Please install it using g.extension."
            ).format(a=addon)
        )


class InvalidMUKEYError(Exception):
    def __init__(self, mukey: str, valid_mukeys: set):
        self.mukey = mukey
        self.valid_mukeys = valid_mukeys
        super().__init__(
            f"Invalid MUKEY '{mukey}'. Must be one of: {', '.join(valid_mukeys)}"
        )


def validate_mukey(mukey: str, valid_mukeys: set = None) -> None:
    if valid_mukeys is None:
        valid_mukeys = {
            "gnatsgo",
            "gssurgo",
            "statsgo",
            "hi_ssurgo",
            "pr_ssurgo",
            "rss",
        }
    if mukey.lower() not in valid_mukeys:
        raise InvalidMUKEYError(mukey, valid_mukeys)


def lookup_mukey_crs(mukey: str) -> str:
    """
    Lookup the coordinate reference system (CRS) for a given MUKEY.

    Args:
        mukey (str): The MUKEY identifier.

    Returns:
        str: The CRS string for the specified MUKEY.
    """
    mukey = mukey.lower()
    if mukey == "gssurgo":
        return "EPSG:5070"
    elif mukey == "statsgo":
        return "EPSG:5070"
    elif mukey == "gnatsgo":
        return "EPSG:5070"
    elif mukey == "hi_ssurgo":
        return "EPSG:6628"
    elif mukey == "pr_ssurgo":
        return "EPSG:32161"
    else:
        raise ValueError(f"Unknown MUKEY '{mukey}'")


class MUKEY_WCS:
    """
    Class to handle the MUKEY WCS (Web Coverage Service) for soil data.

    This class provides methods to interact with the MUKEY WCS, including
    downloading and processing soil data.

    Attributes:
        mukey (str): The MUKEY identifier for the soil data.
        bbox (list): The bounding box coordinates for the area of interest.
    """

    _base_url = "https://casoilresource.lawr.ucdavis.edu/cgi-bin/mapserv?"
    _service_url = "map=/soilmap2/website/wcs/mukey.map&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
    db = "gSSURGO"
    crs = "EPSG:5070"

    def __init__(
        self, mukey: str, region: str = None, project: str = None, crs: str = None
    ):
        validate_mukey(mukey)
        self.mukey = mukey
        self.region = None  # Use current region if not set
        self.project = None  # Use current project if not set
        self.crs = None  # CRS use to request data

    def get_coverage(self, output: str = None) -> str:
        """
        Get the coverage for the specified MUKEY and bounding box.

        This method constructs the URL for the WCS request and retrieves the
        soil data for the specified MUKEY and bounding box.

        Returns:
            str: The URL for the WCS request.
        """
        check_addon_installed("r.in.wcs")
        url_params = (
            "SERVICE=WCS&VERSION=2.0.1&"
            + "REQUEST=GetCoverage&"
            + "FORMAT=image/tiff&"
            + "GEOTIFF:COMPRESSION=DEFLATE"
        )

        crs = lookup_mukey_crs(self.mukey)

        try:
            gs.run_command(
                "r.in.wcs",
                url=self._base_url,
                coverage=self.mukey,
                urlparams=url_params,
                output=output,
                crs=crs,
                location=self.project,
                region=self.region,
                flags="r",
                verbose=True,
                # overwrite=True,
                # quiet=True,
            )
        except CalledModuleError as e:
            gs.fatal(_("Error running r.in.wcs: {e}").format(e=e))


SOIL_PROPERTIES = {
    "bdod": {
        "description": "Bulk density of the fine earth fraction",
        "mapped_units": "cg/cm^3",
        "conversion_factor": 100,
        "conventional_units": "kg/dm^3",
    },
    "cec": {
        "description": "Cation Exchange Capacity of the soil",
        "mapped_units": "mmol(c)/kg",
        "conversion_factor": 10,
        "conventional_units": "cmol(c)/kg",
    },
    "cfvo": {
        "description": "Volumetric fraction of coarse fragments (> 2 mm)",
        "mapped_units": "cm^3/dm^3 (vol per mil)",
        "conversion_factor": 10,
        "conventional_units": "cm^3/100cm^3 (vol%)",
    },
    "clay": {
        "description": "Proportion of clay particles (< 0.002 mm) in the fine earth fraction",
        "mapped_units": "g/kg",
        "conversion_factor": 10,
        "conventional_units": "g/100g (%)",
    },
    "nitrogen": {
        "description": "Total nitrogen (N)",
        "mapped_units": "cg/kg",
        "conversion_factor": 100,
        "conventional_units": "g/kg",
    },
    "phh2o": {
        "description": "Soil pH",
        "mapped_units": "pH*10",
        "conversion_factor": 10,
        "conventional_units": "pH",
    },
    "sand": {
        "description": "Proportion of sand particles (> 0.05 mm) in the fine earth fraction",
        "mapped_units": "g/kg",
        "conversion_factor": 10,
        "conventional_units": "g/100g (%)",
    },
    "silt": {
        "description": "Proportion of silt particles (>= 0.002 mm and <= 0.05 mm) in the fine earth fraction",
        "mapped_units": "g/kg",
        "conversion_factor": 10,
        "conventional_units": "g/100g (%)",
    },
    "soc": {
        "description": "Soil organic carbon content in the fine earth fraction",
        "mapped_units": "dg/kg",
        "conversion_factor": 10,
        "conventional_units": "g/kg",
    },
    "ocd": {
        "description": "Organic carbon density",
        "mapped_units": "hg/m^3",
        "conversion_factor": 10,
        "conventional_units": "kg/m^3",
    },
    "ocs": {
        "description": "Organic carbon stocks (0-30cm depth interval only)",
        "mapped_units": "t/ha",
        "conversion_factor": 10,
        "conventional_units": "kg/m^2",
    },
    "wv0010": {
        "description": "Volumetric Water Content at 10kPa",
        "mapped_units": "0.1 v% or 1 mm/m",
        "conversion_factor": 10,
        "conventional_units": "volume (%)",
    },
    "wv0033": {
        "description": "Volumetric Water Content at 33kPa",
        "mapped_units": "0.1 v% or 1 mm/m",
        "conversion_factor": 10,
        "conventional_units": "volume (%)",
    },
    "wv1500": {
        "description": "Volumetric Water Content at 1500kPa",
        "mapped_units": "0.1 v% or 1 mm/m",
        "conversion_factor": 10,
        "conventional_units": "volume (%)",
    },
}
