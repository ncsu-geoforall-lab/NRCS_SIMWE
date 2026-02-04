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


def hydrologic_group_lookup(hydgrp_code):
    """Lookup table for hydrologic group codes to descriptions."""
    lookup = {
        "A": "Low runoff potential",
        "B": "Moderate runoff potential",
        "C": "High runoff potential",
        "D": "Very high runoff potential",
        "AB": "Between A and B",
        "AC": "Between A and C",
        "AD": "Between A and D",
        "BC": "Between B and C",
        "BD": "Between B and D",
        "CD": "Between C and D",
    }
    return lookup.get(hydgrp_code, "Unknown")


def update_hydrologic_group(tools, vector_map, source_col="hydgrp", target_col="hsg"):
    """
    Ensure an integer Hydrologic Soil Group (HSG) column exists on the vector and populate it from source_col.
    Mapping:
      A->1, B->2, C->3, D->4
      A/D->11, B/D->12, C/D->13, D/D->14 (dual drained/undrained codes)
    Skips unknown/ambiguous codes.
    """
    # Ensure target column exists
    cols = tools.v_info(map=vector_map, format="json", flags="c").json.get(
        "columns", []
    )
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
                        numeric_columns = [
                            x for x in cols.get("columns") if x.get("is_number")
                        ]
                        print(f"{numeric_columns=}")
                        for i in numeric_columns:
                            print(i)
                            if i.get("name") != "cat":
                                mtools.v_to_rast(
                                    input=output,
                                    type="area",
                                    use="attr",
                                    attribute_column=i.get("name"),
                                    output=i.get("name"),
                                )

            except ValueError:
                exit(1)

    # data_path = "/vsizip/data/gSSURGO_NC.zip/gSSURGO_NC.gdb"
    # check = Path(data_path)
    # if not check.exists():
    #     print(f"Data path {data_path} does not exist.")

    # ksat_import(f"{data_path}", "example_project", bbox_wtk, 30)


def ksat_import(db_path, project_name, bbox_wkt, resolution, tools):
    # Connect to DuckDB
    # db_config = {"threads": 1}
    con = duckdb.connect(read_only=False)
    con.install_extension("spatial")
    con.load_extension("spatial")

    # Query to fetch ksat data
    query = f"""
    WITH mu AS (
        SELECT mukey, shape AS geom
        FROM ST_Read('{db_path}', layer='MUPOLYGON', spatial_filter=ST_AsWKB(ST_GeomFromText(?)))
    )
    SELECT mu.geom,
           c.mukey,
           c.cokey,
           c.compname,
           c.comppct_r,
           c.runoff,
           c.hydgrp,
           c.hydricon,
           c.hydricrating,
           c.drainagecl,
           ROW_NUMBER() OVER (PARTITION BY c.mukey ORDER BY c.comppct_r DESC) AS rn
    FROM ST_Read('{db_path}', layer='component') AS c
    INNER JOIN mu ON mu.mukey = c.mukey
    WHERE c.comppct_r IS NOT NULL
    """
    # Execute the query and fetch data
    ksat_data = con.execute(query, [bbox_wkt]).fetchdf()
    ksat_data.describe()
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
