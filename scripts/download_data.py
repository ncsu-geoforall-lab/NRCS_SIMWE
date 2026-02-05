#!/usr/bin/env python3

import os
import sys
import subprocess


BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"


# Define main function
def main():
    project_name = None
    with open("site-CRS-info.txt", "r") as file:
        data = file.readlines()
        for line in data:
            try:
                project_name, projcrs, resolution, naip = line.split(":")
                print(f"Project Name: {project_name}")
                # Initialize the GRASS session
                gs.setup.init(gisdb, project_name, "PERMANENT")
                # Import the elevation raster
                import_elevation(project_name, resolution)
                # Import the SSURGO MUKEY raster
                import_ssurgo_mukey(project_name, resolution)

                # Download NAIP data
                # download_naip(naip)
                # patch_and_composite_naip(naip)

            except ValueError:
                exit(1)


def import_elevation(project, resolution, output_name="elevation"):
    # Download the data
    url = f"{BASE_URL}{project}/grid/elev.tif"
    print("Downloading elevation data from:", url)
    # Import the raster into GRASS GIS
    gs.run_command(
        "r.import",
        input=url,
        output=output_name,
        extent="input",
        resolution="value",
        resolution_value=resolution,
        resample="bicubic",
        title="Elevation",
        overwrite=True,
    )

    # Set the color table
    gs.run_command("r.colors", map=output_name, color="elevation")

    # Return the output raster name
    return output_name


def import_ssurgo_mukey(project, resolution, output_name="ssurgo_mukey"):
    # Download the data
    url = f"{BASE_URL}{project}/grid/ssurgo-mukey.tif"
    print("Downloading ssurgo-mukey data from:", url)
    # Import the raster into GRASS GIS
    gs.run_command(
        "r.import",
        input=url,
        output=output_name,
        extent="input",
        resolution="value",
        resolution_value=resolution,
        resample="nearest",
        title="Gridded Soil Survey Geographic (gSSURGO) Map Unit Key (MUKEY)",
        overwrite=True,
    )

    # Set the color table
    gs.run_command("r.colors", map=output_name, color="random")

    # Doesn't work at the moment
    ##############################
    # Import the soil vector data
    # url = f"{BASE_URL}{project}/vect/ssurgo.shp"
    # print("Downloading soil data from:", url)
    # # Import the vector into GRASS GIS
    # gs.run_command(
    #     "v.in.ogr",
    #     input=url,
    #     output="soil",
    #     overwrite=True,
    # )

    # Return the output raster name
    return output_name


def download_naip(year=2022):
    """Download the NAIP imagery"""
    # Download the data
    print("Downloading NAIP data")
    # Create a new mapset to store raw naip data
    gs.run_command("g.mapset", mapset="naip", flags="c")
    gs.run_command("g.region", raster="elevation", res=1, flags="a")
    # Import the raster into GRASS GIS
    gs.run_command(
        "t.stac.item",
        overwrite=True,
        url="https://planetarycomputer.microsoft.com/api/stac/v1",
        request_method="POST",
        collection_id="naip",
        datetime=year,
        asset_keys="image",
        resolution="value",
        resolution_value=1,
        extent="region",
        nprocs=10,
        flags="d",
        memory=10000,
    )


def patch_and_composite_naip(year=2022):
    gs.run_command("g.region", res=1)
    naip_bands = [(1, "red"), (2, "green"), (3, "blue"), (4, "nir")]
    for band in naip_bands:
        i, band_name = band
        # Get the list of depth maps
        image_list = gs.read_command(
            "g.list", type="raster", pattern=f"*.{i}", separator="comma"
        ).strip()
        patch_name = f"naip_{year}_{band_name}"
        print(f"Creating Patch: {patch_name}")
        gs.run_command(
            "r.patch",
            input=image_list,
            output=patch_name,
            nprocs=1,
            memory=2100,
            overwrite=True,
        )

    gs.run_command(
        "r.composite",
        red=f"naip_{year}_red",
        green=f"naip_{year}_green",
        blue=f"naip_{year}_blue",
        output=f"naip_{year}_rgb",
        overwrite=True,
    )


if __name__ == "__main__":
    # Define the path to the GRASS GIS database
    gisdb = os.path.join(os.getenv("HOME"), "grassdata")

    # Ask GRASS GIS where its Python packages are.
    sys.path.append(
        subprocess.check_output(["grass", "--config", "python_path"], text=True).strip()  # noqa: E501
    )

    import grass.script as gs

    # We need to import gutiles after grass is part of the path
    from gutiles import install_addons

    # Install rquired GRASS addons
    install_addons(addons_file="addons.txt")

    # Execute the main function
    sys.exit(main())
