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


# Define main function
def main():
    project_name = None
    with open("site-CRS-info.txt", "r") as file:
        data = file.readlines()
        for line in data:
            try:
                project_name, projcrs, resolution, naip = line.split(":")
                print(f"Project Name: {project_name}")
                session = gj.init(f"{gisdb}/{project_name}/PERMANENT")
                tools = Tools(session=session, overwrite=True)
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
                    f"{data_path}", "example_project", crs_bbox_wkt, 30, tools
                )
                session = gj.init(f"{gisdb}/{project_name}/PERMANENT")
                tools = Tools(session=session, overwrite=True)
                if output:
                    new_vect = tools.g_list(type="vector", format="json").json
                    print(f"{new_vect=}")
                    cols = tools.v_info(map=output, format="json", flags="c").json
                    print(cols)
                    numeric_columns = [x for x in cols.get("columns") if x.get("is_number")]
                    print(f"{numeric_columns=}")
                    for i in numeric_columns:
                        print(i)
                        if i.get("name")!= "cat":
                            tools.v_to_rast(
                                input=output,
                                type="area",
                                use="attr",
                                attribute_column=i.get("name"),
                                output=i.get("name")
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
           c.comppct_r,
           c.runoff,
           c.hydgrp,
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
    temp_project = f"tmp_{project_name}_5050"

    gs.create_project(path=tempdir.name, name=temp_project, epsg=26917, overwrite=True)
    session = gj.init(Path(tempdir.name, temp_project))

    # help(session)
    for child in Path(tempdir.name, temp_project).iterdir():
        print(child)
    # grass_dsn = f"GRASS:{Path(tempdir.name) / tempname}"
    output_layer = f"{project_name}_mupolygon"
    # gdal_option = (
    #     f"{Path(tempdir.name) / tempname}/PERMANENT/vector/{output_layer}/head"
    # )

    # Export SSURGO data to GRASS
    # Need to check if GRASS driver is available
    # df_drivers = con.execute("SELECT * FROM ST_Drivers();").fetchdf()
    # for _, row in df_drivers.iterrows():
    #     print(row.get("short_name"), row.get("can_create"))
        # gs.message(f"Driver: {_}, Can Write: {row}")

    fd, tmp_filepath = tempfile.mkstemp()
    # GRASS GDAL driver isn't supported by duckdb
    print(f"Tempfile Path: {tmp_filepath}")
    try:
        export_sql = f"""
        COPY (
            {query.strip()}
        ) TO '{tmp_filepath}'
        (FORMAT GDAL, DRIVER 'FlatGeobuf', SRS 'EPSG:26917');
        """

        con.execute(export_sql, [bbox_wkt])

        # Create a new GRASS session for the temp dataset
        with Tools(session=session) as t:
            session_env = t.g_gisenv(get="GISDBASE,LOCATION_NAME,MAPSET", sep='/').text
            print(f"Session info: {session_env}")
            t.v_in_ogr(
                input=tmp_filepath,
                output=output_layer,
                type="boundary",
                snap=0.001
            )

            new_vect = t.g_list(type="vector", format="json").json
            print(f"{new_vect=}")

        # Reproject dataset from temp project to the current GRASS project
        print("Reprojecting ssurgo data")
        tools.v_proj(
            project=temp_project,
            input=output_layer,
            dbase=tempdir.name,
            mapset="PERMANENT",
            output=output_layer,
        )



    finally:
        print("CLeaning up temp project")
        tempdir.cleanup()
        print(f"{tmp_filepath=}")
        print(f"Is Dir: {Path(tmp_filepath).is_dir()}")
        print(f"Is file: {Path(tmp_filepath).is_file()}")
        tmp_files = Path(tmp_filepath).name
        print(f"Tempfile Name: {tmp_files=}")
        # print(f"Temp files: {list(tmp_files)}")
        # for f in tmp_files:
        #     print (f"Removing file {f=}")
        #     f.unlink()
        # Path(tmp_filepath).rmdir()
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
