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
import textwrap
import grass.script as gs
import grass.script.core as gcore
from grass.exceptions import CalledModuleError
import tempfile
import requests
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
from enum import Enum
from pathlib import Path

# Set up translation function
_ = gettext.gettext

MICROMETERS_PER_SECOND_TO_MM_PER_HOUR = 3.6  # Conversion factor

# Notes:

##### Infiltration Concepts #####
# Infiltration Rate - The rate at which water infiltrates into the ground at any given
# moment, regardless of the current soil saturation level.
# Ksat (Saturated Hydraulic Conductivity of Soil) - is the infiltration rate once the ground
# has reached 100% saturation and the infiltration rate has become constant.

##### Rainfall excess models #####
# SCS Curve Number Method - Uses hydrologic soil groups (HSG) A, B, C, D to estimate runoff
# based on soil infiltration rates, land use, and antecedent moisture conditions.

##### Emprical Infiltration Models #####
# Horton Infiltration Model - Uses initial and final infiltration rates along with a decay constant
# to describe how infiltration decreases over time.
# Kostiakov Model - An empirical model that describes infiltration rate as a function of time
# Holtan Model - An empirical model that relates infiltration rate to cumulative infiltration.

##### Approximate Theory-Based Models #####

# Green-Ampt Model - A physically based model that considers soil properties and wetting front
# movement to estimate infiltration.
#
# parameters:
# K - the effective hydraulic conductivity of the soil [cm/h]
# S - the wetting front suction head [cm]
# phi - the soil porosity
# theta_i - the initial volumetric water content [L^3 L^-3]
#
# BD (Soil Bulk Density) = 100 / (% Organic Matter / Organic Matter bulk density) + ((100 - % Organic Matter) / Mineral bulk density))
#
# where:
# BD = Bulk Density of <2-mm material, (g/cm³)
# S = Percent sand content of the soil
# OM = Percent organic matter content of the soil
# C = Percent clay content of the soil
# CEC = Cation exchange capacity of the soil (cmol(+)/kg)
#   CEC ranges from 0.1 - 0.9
#
# Philip's Model - A model that uses sorptivity and steady-state infiltration rate to describe
# infiltration behavior over time.

# GRASS (r.sim.water)
# parameter: infil - Name of runoff infiltration rate raster map [mm/hr]
# parameter: rain - Name of rainfall excess rate (rain-infilt) raster map [mm/hr]


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


def check_if_zipfile(file_path: Path) -> Path:
    """Check if the provided file path is a ZIP file."""
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_path.suffix.lower() == ".zip":
        return Path("/vsizip") / file_path.relative_to(file_path.anchor)
    return file_path


def region_to_wgs84_decimal_degrees_bbox():
    """convert region bbox to wgs84 decimal degrees bbox"""
    region = gs.parse_command("g.region", quiet=True, flags="ubg")
    bbox = [
        float(c)
        for c in [region["ll_w"], region["ll_s"], region["ll_e"], region["ll_n"]]
    ]
    return bbox


def region_to_wkt_wgs84():
    """Convert GRASS region bounds to a WKT polygon in WGS84."""
    west, south, east, north = region_to_wgs84_decimal_degrees_bbox()
    wkt = f"POLYGON(({west} {south}, {east} {south}, {east} {north}, {west} {north}, {west} {south}))"
    return wkt


def region_to_crs_bbox(target_crs: str) -> [float]:
    """Convert GRASS region bounds to a bounding box in another CRS using m.proj."""
    region = gs.region()
    # Extract corner coordinates
    west, south, east, north = region["w"], region["s"], region["e"], region["n"]
    nsres = region["nsres"]
    ewres = region["ewres"]

    # Format input coordinates for m.proj (as string input to stdin)
    coords = f"{west}|{south}\n{east}|{north}\n"

    proj_in = gs.parse_command("g.proj", format="proj4", flags="pf")
    gs.debug(_("region_to_crs_bbox: proj_in: %s" % proj_in))
    proj_out = gs.parse_command("g.proj", format="proj4", srid=target_crs, flags="pf")
    gs.debug(_("region_to_crs_bbox: proj_out: %s" % proj_out))

    # We currently dont have an easy way to get arround needing a tempfile when
    # we want to both pass an argument to stdin and we want the results added to the stdout
    with tempfile.NamedTemporaryFile(
        mode="w+t", prefix="r_soildb", suffix=".txt"
    ) as fp:
        try:
            gs.write_command(
                "m.proj",
                input="-",
                proj_in=f"+proj={proj_in['+proj']}",
                proj_out=f"+proj={proj_out['+proj']}",
                stdin=coords,
                output=fp.name,
                verbose=True,
                quiet=False,
                overwrite=True,
            )
        except CalledModuleError as e:
            gs.fatal(f"Projection failed: {e}")

        # Parse the tempfile output
        lines = fp.readlines()
        gs.message(_("Reproject Bounds for WCS query: %s" % lines))
        clean_lines = [line.strip() for line in lines]
        ll_x, ll_y, ll_z = map(float, clean_lines[0].split("|"))  # Lower-left
        ur_x, ur_y, ur_z = map(float, clean_lines[1].split("|"))  # Upper-right

        return [ll_x, ll_y, ur_x, ur_y, ewres, nsres]


def region_to_crs_wkt(target_crs: str = "EPSG:5070") -> str:
    """Convert GRASS region bounds to a WKT polygon in another CRS using m.proj."""
    west, south, east, north = region_to_crs_bbox(target_crs)[:4]
    wkt = f"POLYGON(({west} {south}, {east} {south}, {east} {north}, {west} {north}, {west} {south}))"
    gs.debug(_("region_to_crs_wkt: wkt: %s" % wkt))
    return wkt


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


def mukey_to_ksat(mukey: str) -> str:
    """
    Convert MUKEY to Ksat (saturated hydraulic conductivity) string.

    Args:
        mukey (str): The MUKEY identifier.

    Returns:
        str: The Ksat string for the specified MUKEY.
    """
    mukey = mukey.lower()
    if mukey == "gssurgo":
        return "Ksat"
    elif mukey == "statsgo":
        return "Ksat"
    elif mukey == "gnatsgo":
        return "Ksat"
    elif mukey == "hi_ssurgo":
        return "Ksat"
    elif mukey == "pr_ssurgo":
        return "Ksat"
    else:
        raise ValueError(f"Unknown MUKEY '{mukey}'")


def soil_texture(mukey: str, sand, clay, silt) -> str:
    """
    Convert MUKEY to soil texture string.

    Args:
        mukey (str): The MUKEY identifier.

    Returns:
        str: The soil texture string for the specified MUKEY.
    """
    mukey = mukey.lower()
    if mukey == "gssurgo":
        return "Texture"
    elif mukey == "statsgo":
        return "Texture"
    elif mukey == "gnatsgo":
        return "Texture"
    elif mukey == "hi_ssurgo":
        return "Texture"
    elif mukey == "pr_ssurgo":
        return "Texture"
    else:
        raise ValueError(f"Unknown MUKEY '{mukey}'")


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

    _base_url = (
        "https://casoilresource.lawr.ucdavis.edu/cgi-bin/mapserv?"
        "map=/soilmap2/website/wcs/mukey.map&"
        "SERVICE=WCS&"
        "VERSION=2.0.1&"
        "REQUEST=GetCoverage&"
        "FORMAT=GEOTIFF_FLOAT&"
        "GEOTIFF:COMPRESSION=DEFLATE&"
        "FORMAT=image/tiff"
    )
    # _service_url = "map=/soilmap2/website/wcs/mukey.map&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
    crs = "EPSG:5070"

    def __init__(
        self, mukey: str, region: str = None, project: str = None, crs: str = None
    ):
        validate_mukey(mukey)
        self.mukey = mukey
        self.region = None  # Use current region if not set
        self.project = None  # Use current project if not set
        self.crs = None  # CRS use to request data

    def _debug(self, fun, msg):
        """Print debug messages"""
        gs.debug("%s.%s: %s" % (self.__class__.__name__, fun, msg))

    def _generate_wcs_url(self):
        crs = lookup_mukey_crs(self.mukey)
        ll_x, ll_y, ur_x, ur_y, ewres, nsres = region_to_crs_bbox(crs)
        url = (
            f"{self._base_url}"
            f"&coverage={self.mukey}"
            f"&SUBSET={self.mukey}"
            f"&SUBSETTINGCRS={crs}"
            f"&SUBSET=x({ll_x},{ur_x})"
            f"&SUBSET=y({ll_y},{ur_y})"
            f"&RESOLUTION=x({ewres})"
            f"&RESOLUTION=x({nsres})"
        )
        gs.debug("url: %s" % url)
        print("url: %s" % url)
        return url

    def _download_geotiff(self, wcs_url, output_path):
        """Download GeoTIFF from WCS URL to given file path."""
        gs.message(_(f"Downloading data from: {wcs_url}"))
        r = requests.get(wcs_url, stream=True)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            gs.message(_("Download complete."))
        else:
            gs.fatal(_("Failed to download data: HTTP %s" % r.status_code))

    def _import_geotiff_to_grass(self, input_tiff, output_raster):
        """Import GeoTiFF into GRASS"""
        gs.run_command(
            "r.import", input=input_tiff, output=output_raster, overwrite=True
        )

    def fetch_wcs(self, *args, **kwargs):
        """Fetch and import data from WMC server"""
        self._debug("fetch_wcs", "started")
        output_raster = kwargs["output_raster"]
        download_path = kwargs["geotiff_path"]
        url = self._generate_wcs_url()
        self._download_geotiff(url, download_path)
        self._import_geotiff_to_grass(
            input_tif=download_path, output_raster=output_raster
        )
        self._debug("fetch_wcs", "ended")


class SoilAggMethod(Enum):
    DOMINANT_COMPONENT = "dominant_component"
    WEIGHTED_COMPONENT = "weighted_component"


class SDAClient:
    """
    Client for interacting with the Soil Data Access (SDA) database.

    This class provides methods to execute SQL queries against the SDA database
    and retrieve soil data based on specified parameters.
    """

    REST_URL = (
        "https://SDMDataAccess.sc.egov.usda.gov/Tabular/SDMTabularService/post.rest"
    )

    def _build_sda_sql(self, aoi_wkt, top_cm: int, bottom_cm: int, agg: SoilAggMethod):
        """
        Build one SQL batch that:
        1) gets intersecting mukeys from AOI WKT (WGS84)
        2) aggregates ksat to mapunit (mukey)
        3) returns mupolygon WKT + mukey + ksat

        Uses SDA helper functions described in Advanced Queries.
        """
        # Depth-weighted mean within [top_cm, bottom_cm]
        # thickness = max(0, min(hzdepb_r, bottom) - max(hzdept_r, top))
        # Ksat RV: chorizon.ksat_r
        #
        # dominant_component: pick component with max comppct_r for each mukey
        #
        # weighted_component: weight components by comppct_r and depth-weight horizons per component

        top = float(top_cm)
        bottom = float(bottom_cm)

        if agg == SoilAggMethod.DOMINANT_COMPONENT:
            ksat_cte = f"""
            WITH mu AS (
            SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{aoi_wkt}')
            ),
            dom_comp AS (
            SELECT c.mukey, c.cokey, c.comppct_r,
                    ROW_NUMBER() OVER (PARTITION BY c.mukey ORDER BY c.comppct_r DESC) AS rn
            FROM component c
            INNER JOIN mu ON mu.mukey = c.mukey
            WHERE c.comppct_r IS NOT NULL
            ),
            dom AS (
            SELECT mukey, cokey FROM dom_comp WHERE rn = 1
            ),
            hz AS (
            SELECT d.mukey,
                    CASE
                    WHEN SUM(thk) = 0 THEN NULL
                    ELSE SUM(thk * ksat_r) / SUM(thk)
                    END AS ksat
            FROM (
                SELECT d.mukey,
                    h.ksat_r,
                    CASE
                        WHEN h.hzdept_r IS NULL OR h.hzdepb_r IS NULL THEN 0
                        ELSE
                        CASE
                            WHEN (CASE WHEN h.hzdepb_r < {bottom} THEN h.hzdepb_r ELSE {bottom} END)
                                - (CASE WHEN h.hzdept_r > {top} THEN h.hzdept_r ELSE {top} END) > 0
                            THEN (CASE WHEN h.hzdepb_r < {bottom} THEN h.hzdepb_r ELSE {bottom} END)
                                - (CASE WHEN h.hzdept_r > {top} THEN h.hzdept_r ELSE {top} END)
                            ELSE 0
                        END
                    END AS thk
                FROM dom d
                INNER JOIN chorizon h ON h.cokey = d.cokey
                WHERE h.ksat_r IS NOT NULL
            ) x
            GROUP BY d.mukey
            ),
            poly AS (
            -- get all polygons for the intersecting mukeys
            SELECT t.mukey, p.MupolygonWktWgs84 AS wkt
            FROM (SELECT mukey FROM mu) t
            CROSS APPLY SDA_Get_MupolygonWktWgs84_from_Mukey(t.mukey) p
            )
            SELECT poly.mukey, hz.ksat, poly.wkt
            FROM poly
            LEFT JOIN hz ON hz.mukey = poly.mukey
            """
        else:
            # weighted_component
            ksat_cte = f"""
            WITH mu AS (
            SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{aoi_wkt}')
            ),
            comp AS (
            SELECT c.mukey, c.cokey, c.comppct_r
            FROM component c
            INNER JOIN mu ON mu.mukey = c.mukey
            WHERE c.comppct_r IS NOT NULL
            ),
            comp_hz AS (
            SELECT c.mukey, c.cokey, c.comppct_r,
                    CASE
                    WHEN SUM(thk) = 0 THEN NULL
                    ELSE SUM(thk * ksat_r) / SUM(thk)
                    END AS ksat_comp
            FROM (
                SELECT c.mukey, c.cokey, c.comppct_r,
                    h.ksat_r,
                    CASE
                        WHEN h.hzdept_r IS NULL OR h.hzdepb_r IS NULL THEN 0
                        ELSE
                        CASE
                            WHEN (CASE WHEN h.hzdepb_r < {bottom} THEN h.hzdepb_r ELSE {bottom} END)
                                - (CASE WHEN h.hzdept_r > {top} THEN h.hzdept_r ELSE {top} END) > 0
                            THEN (CASE WHEN h.hzdepb_r < {bottom} THEN h.hzdepb_r ELSE {bottom} END)
                                - (CASE WHEN h.hzdept_r > {top} THEN h.hzdept_r ELSE {top} END)
                            ELSE 0
                        END
                    END AS thk
                FROM comp c
                INNER JOIN chorizon h ON h.cokey = c.cokey
                WHERE h.ksat_r IS NOT NULL
            ) z
            GROUP BY mukey, cokey, comppct_r
            ),
            hz AS (
            SELECT mukey,
                    CASE
                    WHEN SUM(comppct_r) = 0 THEN NULL
                    ELSE SUM(comppct_r * ksat_comp) / SUM(comppct_r)
                    END AS ksat
            FROM comp_hz
            WHERE ksat_comp IS NOT NULL
            GROUP BY mukey
            ),
            poly AS (
            SELECT t.mukey, p.MupolygonWktWgs84 AS wkt
            FROM (SELECT mukey FROM mu) t
            CROSS APPLY SDA_Get_MupolygonWktWgs84_from_Mukey(t.mukey) p
            )
            SELECT poly.mukey, hz.ksat, poly.wkt
            FROM poly
            LEFT JOIN hz ON hz.mukey = poly.mukey
            """

        # SDA likes a single batch; keep it as-is
        return textwrap.dedent(ksat_cte).strip()

    def _sda_post_sql(self, sql, sda_url, timeout=120):
        """
        POST SQL to SDA post.rest. Request JSON output.
        SDA post.rest documented on SDA web service help page.
        """
        headers = {
            "Content-Type": "text/sql",
            "Accept": "application/json",
        }
        req = Request(sda_url, data=sql.encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                return json.loads(data)
        except HTTPError as e:
            raise gs.fatal(f"SDA HTTP error {e.code}: {e.reason}")
        except URLError as e:
            raise gs.fatal(f"SDA connection error: {e.reason}")
        except json.JSONDecodeError:
            raise gs.fatal(
                "SDA did not return JSON. Try changing SDA format or check service status."
            )

    def fetch_sda(
        self,
        aoi_wkt,
        top_cm: int,
        bottom_cm: int,
        agg: SoilAggMethod = SoilAggMethod.DOMINANT_COMPONENT,
    ):
        """Fetch data from SDA for the given AOI and parameters."""
        self._debug("fetch_sda", "started")
        sql = self._build_sda_sql(aoi_wkt, top_cm, bottom_cm, agg)
        self._debug("fetch_sda", f"SQL built: {sql}")
        result = self.sda_post_sql(sql, self.REST_URL)
        self._debug("fetch_sda", f"SDA result: {result}")
        self._debug("fetch_sda", "ended")
        return result


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
