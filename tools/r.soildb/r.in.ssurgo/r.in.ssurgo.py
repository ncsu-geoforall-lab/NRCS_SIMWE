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

# %option G_OPT_F_INPUT
# % key: ssurgo_path
# % description: Path to the SSURGO ZIP file downloaded from Web Soil Survey
# % guisection: Inputs
# % required: no
# %end

# %option G_OPT_R_OUTPUT
# % key: hydgrp
# % description: Hydrologic soil group
# % guisection: Outputs
# % required: no
# %end

# %option G_OPT_R_OUTPUT
# % key: ksat_h
# % description: Saturated Hydraulic Conductivity of Soil Ksat (high) [mm/hr]
# % guisection: Outputs
# % required: no
# %end

# %option G_OPT_R_OUTPUT
# % key: ksat_r
# % description: Saturated Hydraulic Conductivity of Soil Ksat (regular) [mm/hr]
# % guisection: Outputs
# % required: no
# %end

# %option G_OPT_R_OUTPUT
# % key: ksat_l
# % description: Saturated Hydraulic Conductivity of Soil Ksat (low) [mm/hr]
# % guisection: Outputs
# % required: no
# %end

# %option G_OPT_R_OUTPUT
# % key: mukey
# % description: Map unit key
# % guisection: Outputs
# % required: no
# %end

# %option G_OPT_V_OUTPUT
# % key: ssurgo_areas
# % description: Name for output soil grid
# % guisection: Outputs
# % required: no
# %end

# %option
# % key: desgnmaster
# % guisection: Options
# % type: string
# % required: no
# % multiple: no
# % options: A
# % answer: A
# % description: Designation of master horizon
# %end

# %option
# % key: hzdept_r
# % guisection: Options
# % type: integer
# % required: no
# % multiple: no
# % answer: 0
# % description: Horizon depth top (cm)
# %end

# %option
# % key: hzdepb_r
# % guisection: Options
# % type: integer
# % required: no
# % description: Horizon depth bottom (cm)
# %end

# %option G_OPT_M_NPROCS
# %end

# %flag
# % key: d
# % description: Use Soil Data Access (SDA) to query and download data for the specified map unit key (mukey) instead of using a local SSURGO ZIP file.
# %end

import os
from pathlib import Path
import sys
import tempfile

from requests import options
import grass.script as gs
import grass.jupyter as gj
from grass.exceptions import CalledModuleError
from grass.tools import Tools
from grass.pygrass.utils import get_lib_path
from contextlib import contextmanager
from io import StringIO
import gettext

# Set up translation function
_ = gettext.gettext

# Active GRASS session tools
tools = Tools()


def _import_duckdb(error):
    """Import duckdb module"""
    try:
        import duckdb

        return duckdb
    except ImportError as err:
        if error:
            raise err
        return None


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


def check_if_zipfile(file_path: Path) -> Path:
    """Check if the provided file path is a ZIP file."""
    # if not file_path.is_file():
    #     raise FileNotFoundError(f"File not found: {file_path}")
    # if file_path.suffix.lower() == ".zip":
    return Path("/vsizip") / file_path.relative_to(file_path.anchor)
    # return file_path


def connect_duckdb(threads=None):
    """Connect to a DuckDB database."""
    duckdb = _import_duckdb(error=True)
    duckdb_config = {}

    # By default, duckdb uses all available threads.
    if threads > 0:
        duckdb_config = {"threads": threads}

    con = duckdb.connect(read_only=False, config=duckdb_config)
    con.install_extension("spatial")
    con.load_extension("spatial")
    return con


def hydrologic_group_categories(hydgrp_code):
    """Lookup table for hydrologic group codes to descriptions."""
    lookup = {
        "A": "Low runoff potential",
        "B": "Moderate runoff potential",
        "C": "High runoff potential",
        "D": "Very high runoff potential",
        "A/B": "Between A and B",
        "A/C": "Between A and C",
        "A/D": "Between A and D",
        "B/C": "Between B and C",
        "B/D": "Between B and D",
        "C/D": "Between C and D",
    }
    return lookup.get(hydgrp_code, "Unknown")


def hydrologic_soil_group_color_scheme(map_name: str) -> None:
    """Apply brown color scheme to elevation map."""
    print("Applying brown elevation color scheme...")
    hydgrp_color_palette = [
        # Single hydrologic soil groups (fast → slow infiltration)
        ("1", "#E7F5FF"),  # A: very fast infiltration (very light cool)
        ("2", "#A6D9FF"),  # B: fast (light cool)
        ("3", "#FFD27A"),  # C: slow (warm / amber)
        ("4", "#7A2E1B"),  # D: very slow (dark warm)
        # Dual groups (drained vs undrained behavior) — perceptual “in-between” blends toward D
        ("11", "#C6A8A1"),  # A/D
        ("12", "#B1846B"),  # B/D
        ("13", "#C06A44"),  # C/D
        ("14", "#4A1A10"),  # strongest D-like / very restricted
    ]
    # Convert palette list to rules string for r_colors
    hydgrp_color_scheme = (
        "\n".join(f"{pos} {color}" for pos, color in hydgrp_color_palette) + "\n"
    )
    tools.r_colors(map=map_name, rules=StringIO(hydgrp_color_scheme), flags="")


def ksat_color_scheme(map_name: str) -> None:
    """Apply brown color scheme to elevation map."""
    print("Applying brown elevation color scheme...")
    ksat_color_palette = [
        # Very low Ksat (clays, compacted soils)
        ("0%", "#3B1F0E"),  # very slow infiltration
        ("10%", "#5A2D1A"),
        ("20%", "#7A3F1D"),
        # Low–moderate Ksat
        ("30%", "#9C5A2A"),
        ("40%", "#B97C3F"),
        # Transitional (loams)
        ("50%", "#D6A95C"),
        # Moderate–high Ksat
        ("60%", "#BFD38A"),
        ("70%", "#8FCB9B"),
        # High Ksat (sands)
        ("80%", "#5FB7B2"),
        ("90%", "#3A8FB7"),
        # Very high Ksat (gravel / macroporous)
        ("100%", "#1E5E8C"),
    ]
    # Convert palette list to rules string for r_colors
    ksat_color_scheme = (
        "\n".join(f"{pos} {color}" for pos, color in ksat_color_palette) + "\n"
    )
    tools.r_colors(map=map_name, rules=StringIO(ksat_color_scheme), flags="")


def update_hydrologic_group(vector_map, source_col="hydgrp", target_col="hsg"):
    """
    Ensure an integer Hydrologic Soil Group (HSG) column exists on the vector and populate it from source_col.
    Mapping:
      A->1, B->2, C->3, D->4
      A/D->11, B/D->12, C/D->13, D/D->14 (dual drained/undrained codes)
    Skips unknown/ambiguous codes.
    """
    # Ensure target column exists
    cols = tools.v_info(map=vector_map, format="json", flags="c").json
    print(f"{cols=}")

    # Handles previous json repsonse structure from GRASS 8.4.1
    if type(cols) is dict:
        cols = cols.get("columns", [])

    col_names = [c["name"] for c in cols]
    if target_col not in col_names:
        tools.v_db_addcolumn(map=vector_map, columns=f"{target_col} INTEGER")

    # Mapping from hydgrp text to numeric HSG
    mapping = {
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4,
        "A/D": 11,  # A/D
        "B/D": 12,  # B/D
        "C/D": 13,  # C/D
        "D/D": 14,  # D/D
        # keep ambiguous combos out (AB, AC, BC, etc.) unless you have a rule
    }

    # Update rows for each mapping entry (handle uppercase/lowercase)
    for code, num in mapping.items():
        where = f"{source_col} = '{code}' OR {source_col} = '{code.lower()}'"
        tools.v_db_update(
            map=vector_map, column=target_col, value=str(num), where=where
        )

    # Optionally set unmatched values to NULL (skip here) or 0:
    tools.v_db_update(
        map=vector_map, column=target_col, value="NULL", where=f"{target_col} IS NULL"
    )

    return target_col


def local_ssurgo_query(
    con,
    wkt_bbox,
    ssurgo_path,
    desgnmaster,
    hzdept_r,
    hzdepb_r,
    hydgrp_out,
    ksat_h_out,
    ksat_r_out,
    ksat_l_out,
    mukey_out,
    ssurgo_areas_out,
):
    """
    Import SSURGO data from a local ZIP file.

    This function processes a local SSURGO ZIP file, extracts the relevant soil data based on the specified parameters,
    and outputs the desired raster and vector layers.

    Args:
        con (duckdb.Connection): An active connection to a DuckDB database with the spatial extension loaded.
        wkt_bbox (str): WKT polygon representing the bounding box.
        ssurgo_path (str): Path to the local SSURGO file.
        desgnmaster (str): Designation of master horizon.
        hzdept_r (int): Horizon depth top (cm).
        hzdepb_r (int): Horizon depth bottom (cm).
        hydgrp_out (str): Name for output hydrologic soil group raster.
        ksat_h_out (str): Name for output Ksat high raster.
        ksat_r_out (str): Name for output Ksat regular raster.
        ksat_l_out (str): Name for output Ksat low raster.
        mukey_out (str): Name for output map unit key raster.
        ssurgo_areas_out (str): Name for output soil grid vector layer.

    Returns:
        None: This function does not return any value. It creates raster and vector layers in the GRASS environment.
    """
    MICROMETERS_PER_SECOND_TO_MM_PER_HOUR = 3.6  # Conversion factor
    top = hzdept_r
    bottom = hzdepb_r
    # Table mu polygon fields used:
    # mukey: Map unit key
    # shape: Geometry field

    # Table component fields used:
    # mukey: Map unit key
    # cokey: Component key
    # comppct_r: Component percentage of map unit
    # compname: Component name
    # runoff: Runoff curve number
    # hydgrp: Hydrologic soil group
    # hydricon: Hydric condition
    # hydricrating: Hydric rating
    # drainagecl: Drainage class

    # Table chorizon fields used:
    # hzdept_r: Horizon depth top (cm)
    # hzdepb_r: Horizon depth bottom (cm)
    # ksat_r: (representative) (micrometers per second)
    #    The amount of water that would move vertically
    #    through a unit area of saturated soil in unit
    #    time under unit hydraulic gradient.
    # ksat_h: (high) (micrometers per second)
    # ksat_l: (low) (micrometers per second)
    # desgnmaster: Designation of master horizon
    query = f"""
    WITH mu AS (
        SELECT mukey, shape AS geom
        FROM ST_Read('{ssurgo_path}', layer='MUPOLYGON', spatial_filter_box=ST_EXTENT(ST_AsWKB(ST_GeomFromText(?))))
    ),
    -- choose dominant component per mukey (deterministic tiebreaker on cokey)
    dom_comp AS (
        SELECT mu.geom,
               c.mukey,
               c.cokey,
               c.comppct_r,
               c.compname,
               c.runoff,
               c.hydgrp,
               c.hydricon,
               c.hydricrating,
               c.drainagecl,
               ROW_NUMBER() OVER (PARTITION BY c.mukey ORDER BY c.comppct_r DESC) AS rn
        FROM ST_Read('{ssurgo_path}', layer='component') AS c
        INNER JOIN mu ON mu.mukey = c.mukey
        WHERE c.comppct_r IS NOT NULL
    ),
    dom AS (
        SELECT
            mukey,
            cokey,
            comppct_r,
            compname,
            runoff,
            hydgrp,
            hydricon,
            hydricrating,
            drainagecl,
            geom
        FROM dom_comp
       -- WHERE rn = 1
    ),
    -- compute weighted ksat for the dominant component's horizons within [top,bottom]
    hz AS (
        SELECT
            mukey,
            CASE
                WHEN SUM(thk) = 0 THEN NULL
                ELSE SUM(thk * ksat_l) / SUM(thk)
            END AS ksat_l,
            CASE
                WHEN SUM(thk) = 0 THEN NULL
                ELSE SUM(thk * ksat_r) / SUM(thk)
            END AS ksat_r,
            CASE
                WHEN SUM(thk) = 0 THEN NULL
                ELSE SUM(thk * ksat_h) / SUM(thk)
            END AS ksat_h
        FROM (
            SELECT
                d.mukey,
                h.ksat_l * {MICROMETERS_PER_SECOND_TO_MM_PER_HOUR} AS ksat_l,
                h.ksat_r * {MICROMETERS_PER_SECOND_TO_MM_PER_HOUR} AS ksat_r,
                h.ksat_h * {MICROMETERS_PER_SECOND_TO_MM_PER_HOUR} AS ksat_h,
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
            INNER JOIN ST_Read('{ssurgo_path}', layer='chorizon') AS h ON h.cokey = d.cokey
            WHERE h.ksat_r IS NOT NULL
              AND h.hzdept_r = 0
              AND h.hzdepb_r > 0
              AND h.desgnmaster = 'A'
        ) x
        GROUP BY
            mukey
    )
    -- final: one row per mukey (dominant component attributes + aggregated ksat)
    SELECT
        d.geom,
        d.mukey,
        d.cokey,
        d.compname,
        d.comppct_r,
        d.runoff,
        d.hydgrp,
        d.hydricon,
        d.hydricrating,
        d.drainagecl,
        hz.ksat_l,
        hz.ksat_r,
        hz.ksat_h
    FROM dom d
    LEFT JOIN hz ON hz.mukey = d.mukey
    """
    ksat_data = con.execute(query, [wkt_bbox]).fetchdf()
    if ksat_data.size == 0:
        gs.warning(_("No records found in your region."))
        return None

    # Export to GRASS using GDAL/OGR_GRASS driver
    tempdir = tempfile.TemporaryDirectory()
    temp_project = "tmp_r_ssurgo_5070"

    gs.create_project(path=tempdir.name, name=temp_project, epsg=5070, overwrite=True)
    temp_session = gj.init(Path(tempdir.name, temp_project))
    output_layer = ssurgo_areas_out
    fd, tmp_filepath = tempfile.mkstemp(suffix=".fgb")

    # GRASS GDAL driver isn't supported by duckdb
    print(f"Tempfile Path: {tmp_filepath}")
    try:
        export_sql = f"""
        COPY (
            {query.strip()}
        ) TO '{tmp_filepath}'
        (FORMAT GDAL, DRIVER 'FlatGeobuf', SRS 'EPSG:5070');
        """

        con.execute(
            export_sql,
            [wkt_bbox],
        )

        # Create a new GRASS session for the temp dataset
        with Tools(session=temp_session) as t:
            print("#" * 50)
            print("Starting temp GRASS session for SSURGO import...")
            session_env = t.g_gisenv(get="GISDBASE,LOCATION_NAME,MAPSET", sep="/").text
            print(f"Temp Session info: {session_env}")
            t.v_in_ogr(
                input=tmp_filepath,
                output=output_layer,
                type="boundary",
                snap=1e-6,
                flags="",
            )

            new_vect = t.g_list(type="vector", format="json").json
            print(f"Temp Session Vectors: {new_vect}")

        # Reproject dataset from temp project to the current GRASS project
        # new_session = gj.init(f"{gisdb}/{project_name}/PERMANENT")
        # with Tools(session=new_session, overwrite=True) as mtools:
        print("#" * 50)
        session_env = wkt_bbox.g_gisenv(
            get="GISDBASE,LOCATION_NAME,MAPSET", sep="/"
        ).text
        print(f"Return to last session: {session_env}")
        print("Reprojecting ssurgo data...")

        tools.v_proj(
            project=temp_project,
            input=output_layer,
            dbase=tempdir.name,
            mapset="PERMANENT",
            output=output_layer,
            verbose=True,
        )

    except CalledModuleError as e:
        print(f"Import failed: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        print("cleaning up temp project")
        tempdir.cleanup()
        print(f"Tempfile Name: {tmp_filepath=}")
        os.close(fd)
        os.remove(tmp_filepath)
        print("cleaned up temp FlatGeoBuff")

    return output_layer


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

    # Inputs
    ssurgo_path = Path(options["ssurgo_path"])

    # TODO: Add ability to specify different Horizons
    desgnmaster = options["desgnmaster"]
    hzdept_r = int(options["hzdept_r"])
    hzdepb_r = int(options["hzdepb_r"])
    flag_d = flags[
        "d"
    ]  # Use Soil Data Access (SDA) to query and download data for the specified map unit key (mukey) instead of using a local SSURGO ZIP file.

    # Outputs
    ###################################################
    # Raster outputs
    hydgrp = options["hydgrp"]
    ksat_h = options["ksat_h"]
    ksat_r = options["ksat_r"]
    ksat_l = options["ksat_l"]
    mukey = options["mukey"]
    # Vector outputs
    ssurgo_areas = options["ssurgo_areas"]

    # Proccessing options
    nprocs = int(options["nprocs"])  # optional

    # Error if no duckdb and flag d is not set.
    if not flag_d:
        _import_duckdb(error=True)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tif_path = tmp.name

        try:
            if flag_d:
                gs.message(
                    "Using Soil Data Access (SDA) to query and download data for the specified map unit key (mukey)."
                )
                aoi_wkt = libsoil.region_to_wkt_wgs84()
                libsoil.fetch_sda(
                    aoi_wkt=aoi_wkt,
                    top_cm=hzdept_r,
                    bottom_cm=hzdepb_r,
                    agg=libsoil.SoilAggMethod.DOMINANT_COMPONENT,
                )
            else:
                gs.message("Importing SSURGO data from local file.")
                _ssurgo_path = check_if_zipfile(ssurgo_path)
                wkt_bbox = region_to_crs_wkt(target_crs="EPSG:5070")
                con = connect_duckdb(threads=nprocs)
                ssurgo_areas = local_ssurgo_query(
                    con=con,
                    wkt_bbox=wkt_bbox,
                    ssurgo_path=_ssurgo_path,
                    desgnmaster=desgnmaster,
                    hzdept_r=hzdept_r,
                    hzdepb_r=hzdepb_r,
                    hydgrp_out=hydgrp,
                    ksat_h_out=ksat_h,
                    ksat_r_out=ksat_r,
                    ksat_l_out=ksat_l,
                    mukey_out=mukey,
                    ssurgo_areas_out=ssurgo_areas,
                )
                update_hydrologic_group(tools, ssurgo_areas)
                _output_maps = [
                    ("hydgrp", hydgrp),
                    ("ksat_h", ksat_h),
                    ("ksat_r", ksat_r),
                    ("ksat_l", ksat_l),
                    ("mukey", mukey),
                ]
                for col, map_name in _output_maps:
                    if map_name is None:
                        continue

                    tools.v_to_rast(
                        input=map_name,
                        type="area",
                        use="attr",
                        attribute_column=col,
                        output=map_name,
                    )

                    ksat_cols = ["ksat_l", "ksat_r", "ksat_h"]
                    if col in ksat_cols:
                        ksat_color_scheme(map_name)

                    if col == "hsg":
                        hydrologic_soil_group_color_scheme(map_name)
        finally:
            if os.path.exists(tif_path):
                os.remove(tif_path)


if __name__ == "__main__":
    options, flags = gs.parser()
    main()
