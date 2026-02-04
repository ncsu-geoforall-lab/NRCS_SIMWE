#!/usr/bin/env python3
# Import Ksat data from gSSURGO into GRASS using DuckDB
# This script is designed to figure out the correct workflow
# before converting into a GRASS tool.

import os
import sys
import subprocess
import duckdb
from pathlib import Path
import tempfile
import gettext
from io import StringIO

# Set up translation function
_ = gettext.gettext

BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"


# Borrowed from scripts r.soildb module
def region_to_crs_bbox(target_crs: str) -> [float]:
    """Convert GRASS region bounds to a bounding box in another CRS using m.proj."""
    region = gs.region()
    # Extract corner coordinates
    west, south, east, north = region["w"], region["s"], region["e"], region["n"]
    # nsres = region["nsres"]
    # ewres = region["ewres"]

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

        return [ll_x, ll_y, ur_x, ur_y]


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


def hydrologic_soil_group_color_scheme(tools, map_name: str) -> None:
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


def ksat_color_scheme(tools, map_name: str) -> None:
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


def update_hydrologic_group(tools, vector_map, source_col="hydgrp", target_col="hsg"):
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


# Define main function
def main():
    project_name = None
    with open("site-CRS-info.txt", "r") as file:
        data = file.readlines()
        for line in data:
            try:
                project_name, projcrs, resolution, naip = line.split(":")
                print(f"Project Name: {project_name}")
                main_session = gj.init(f"{gisdb}/{project_name}/PERMANENT")
                tools = Tools(session=main_session, overwrite=True)
                region_json = tools.g_region(
                    raster="elevation", res=resolution, flags="bwe", format="json"
                ).json
                # print(f"Region JSON: {region_json}")
                region_bbox = [
                    region_json["ll_w"],
                    region_json["ll_s"],
                    region_json["ll_e"],
                    region_json["ll_n"],
                ]
                # print(f"Region BBOX: {region_bbox}")
                bbox_wtk = f"POLYGON(({region_bbox[0]} {region_bbox[1]}, {region_bbox[2]} {region_bbox[1]}, {region_bbox[2]} {region_bbox[3]}, {region_bbox[0]} {region_bbox[3]}, {region_bbox[0]} {region_bbox[1]}))"
                print(f"Region BBOX: {bbox_wtk}")
                data_path = "/vsizip/data/gSSURGO_NC.zip/gSSURGO_NC.gdb"
                crs_bbox = region_to_crs_bbox("EPSG:5070")
                crs_bbox_wkt = f"POLYGON(({crs_bbox[0]} {crs_bbox[1]}, {crs_bbox[2]} {crs_bbox[1]}, {crs_bbox[2]} {crs_bbox[3]}, {crs_bbox[0]} {crs_bbox[3]}, {crs_bbox[0]} {crs_bbox[1]}))"
                print(f"CRS BBOX: {crs_bbox}")
                output = ksat_import(
                    f"{data_path}", project_name, crs_bbox_wkt, 30, tools
                )
                session = gj.init(f"{gisdb}/{project_name}/PERMANENT")
                with Tools(session=session, overwrite=True) as mtools:
                    session_env = mtools.g_gisenv(
                        get="GISDBASE,LOCATION_NAME,MAPSET", sep="/"
                    ).text
                    print(f"Session info: {session_env}")
                    if output:
                        print("Checking data was imported correctly...")
                        new_vect = mtools.g_list(type="vector", format="json").json
                        print(f"{new_vect=}")
                        update_hydrologic_group(mtools, output)
                        cols = mtools.v_info(map=output, format="json", flags="c").json
                        print(f"{cols=}")
                        if type(cols) is dict:
                            cols = cols.get("columns", [])
                        numeric_columns = [x for x in cols if x.get("is_number")]
                        print(f"{numeric_columns=}")
                        for i in numeric_columns:
                            print(i)
                            layer_name = i.get("name")
                            if layer_name != "cat":
                                mtools.v_to_rast(
                                    input=output,
                                    type="area",
                                    use="attr",
                                    attribute_column=layer_name,
                                    output=i.get("name"),
                                )

                                if layer_name in [
                                    "ksat_l",
                                    "ksat_r",
                                    "ksat_h",
                                ]:
                                    ksat_color_scheme(mtools, layer_name)

                                if layer_name == "hsg":
                                    hydrologic_soil_group_color_scheme(
                                        mtools, layer_name
                                    )

            except ValueError:
                exit(1)

    # data_path = "/vsizip/data/gSSURGO_NC.zip/gSSURGO_NC.gdb"
    # check = Path(data_path)
    # if not check.exists():
    #     print(f"Data path {data_path} does not exist.")

    # ksat_import(f"{data_path}", "example_project", bbox_wtk, 30)


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


def ksat_import(db_path, project_name, bbox_wkt, resolution, tools):
    """
    Ksat (Saturated Hydraulic Conductivity of Soil) is the infiltration rate once the ground
    has reached 100% saturation and the infiltration rate has become constant.
    """
    # Connect to DuckDB
    # db_config = {"threads": 1}
    con = duckdb.connect(read_only=False)
    con.install_extension("spatial")
    con.load_extension("spatial")

    top = 0
    bottom = 100  # depth range in cm (0–100 cm) for ksat thickness calculation

    # Query to fetch ksat data
    # query = f"""
    # WITH mu AS (
    #     SELECT mukey, shape AS geom
    #     FROM ST_Read('{db_path}', layer='MUPOLYGON', spatial_filter=ST_AsWKB(ST_GeomFromText(?)))
    # )
    # SELECT mu.geom,
    #        c.mukey,
    #        c.cokey,
    #        c.compname,
    #        c.comppct_r,
    #        c.runoff,
    #        c.hydgrp,
    #        c.hydricon,
    #        c.hydricrating,
    #        c.drainagecl,
    #        ROW_NUMBER() OVER (PARTITION BY c.mukey ORDER BY c.comppct_r DESC) AS rn
    # FROM ST_Read('{db_path}', layer='component') AS c
    # INNER JOIN mu ON mu.mukey = c.mukey
    # WHERE c.comppct_r IS NOT NULL
    # """

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
    MICROMETERS_PER_SECOND_TO_MM_PER_HOUR = 3.6  # Conversion factor
    # Build query that returns one row per mukey (dominant component + ksat)
    query = f"""
    WITH mu AS (
        SELECT mukey, shape AS geom
        FROM ST_Read('{db_path}', layer='MUPOLYGON', spatial_filter_box=ST_EXTENT(ST_AsWKB(ST_GeomFromText(?)))::BOX_2D)
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
        FROM ST_Read('{db_path}', layer='component') AS c
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
            INNER JOIN ST_Read('{db_path}', layer='chorizon') AS h ON h.cokey = d.cokey
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
    ksat_data = con.execute(query, [bbox_wkt]).fetchdf()
    print(ksat_data.describe())
    if ksat_data.size == 0:
        print("No records found in your region.")
        return None

    # Export to GRASS using GDAL/OGR_GRASS driver
    tempdir = tempfile.TemporaryDirectory()
    temp_project = f"tmp_{project_name}_5070"

    gs.create_project(path=tempdir.name, name=temp_project, epsg=5070, overwrite=True)
    temp_session = gj.init(Path(tempdir.name, temp_project))
    output_layer = f"{project_name}_mupolygon"

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

        con.execute(export_sql, [bbox_wkt])

        # Create a new GRASS session for the temp dataset
        with Tools(session=temp_session) as t:
            print("#" * 50)
            print("Starting temp GRASS session for SSURGO import...")
            session_env = t.g_gisenv(get="GISDBASE,LOCATION_NAME,MAPSET", sep="/").text
            print(f"Temp Session info: {session_env}")
            t.v_in_ogr(
                input=tmp_filepath, output=output_layer, type="boundary", snap=0.0001
            )

            new_vect = t.g_list(type="vector", format="json").json
            print(f"Temp Session Vectors: {new_vect}")

        # Reproject dataset from temp project to the current GRASS project
        new_session = gj.init(f"{gisdb}/{project_name}/PERMANENT")
        with Tools(session=new_session, overwrite=True) as mtools:
            print("#" * 50)
            session_env = mtools.g_gisenv(
                get="GISDBASE,LOCATION_NAME,MAPSET", sep="/"
            ).text
            print(f"Return to last session: {session_env}")
            print("Reprojecting ssurgo data...")

            mtools.v_proj(
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


if __name__ == "__main__":
    gisdb = os.path.join(os.getenv("HOME"), "grassdata")
    # Ask GRASS GIS where its Python packages are.
    sys.path.append(
        subprocess.check_output(["grass", "--config", "python_path"], text=True).strip()  # noqa: E501
    )

    import grass.script as gs
    import grass.jupyter as gj
    from grass.tools import Tools
    from grass.exceptions import CalledModuleError

    # Execute the main function
    sys.exit(main())
