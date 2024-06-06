#!/usr/bin/env python3

import os
import sys
import subprocess


BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"
PROJECT_MAPSET = "basic"


# Define main function
def main():
    project_name = None
    with open("site-CRS-info.txt", "r") as file:
        data = file.readlines()
        for line in data:
            try:
                project_name, projcrs, resolution = line.split(":")
                print(f"Project Name: {project_name}")
                # Initialize the GRASS session
                gs.setup.init(gisdb, project_name, "PERMANENT")
                # Import the elevation raster
                elevation_data = import_elevation(project_name, resolution)
                # Import the SSURGO MUKEY raster
                import_ssurgo_mukey(project_name, resolution)
                # download_naip(project_name)
                simulate(project_name, elevation_data)
            except ValueError:
                exit(1)


# def calculate_geomorphology(elevation_data):
#     """Calculate geomorphological features"""
#     # Calculate the geomorphon
#     calculate_geomorphon(elevation_data)
#     calculate_partial_derivites(elevation_data)


def simulate(project_name, elevation_data):
    """Run the simulation"""
    print("Running simulation...")
    gs.run_command("g.mapset", mapset=PROJECT_MAPSET, flags="c")
    # Set region
    gs.run_command("g.region", raster=elevation_data, flags="ap")
    # Calculate geomorphological features
    calculate_geomorphon(elevation_data)
    # Calculate partial derivatives
    calculate_partial_derivites(elevation_data)
    # Run the SIMWE model
    simwe(elevation_data, "dx", "dy", "depth", "disch")


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

    # Import the soil vector data
    url = f"{BASE_URL}{project}/vect/ssurgo.shp"
    print("Downloading soil data from:", url)
    # Import the vector into GRASS GIS
    gs.run_command(
        "v.in.ogr",
        input=url,
        output="soil",
        overwrite=True,
    )

    # Return the output raster name
    return output_name


def calculate_geomorphon(elevation, geomorphon="geomorphon"):
    """Calculate the geomorphon"""
    print("Calculating geomorphon")
    gs.run_command(
        "r.geomorphon",
        elevation=elevation,
        forms=geomorphon,
        search=3,
        overwrite=True,
    )


def calculate_partial_derivites(elevation, dx="dx", dy="dy", **kwargs):
    """Calculate the partial derivatives"""
    print("Calculating partial derivatives")
    slope = kwargs.get("slope", "slope")
    aspect = kwargs.get("aspect", "aspect")
    pcurv = kwargs.get("pcurv", "pcurv")
    tcurv = kwargs.get("tcurv", "tcurv")
    gs.run_command(
        "r.slope.aspect",
        elevation=elevation,
        dx=dx,
        dy=dy,
        aspect=aspect,
        pcurvature=pcurv,
        tcurvature=tcurv,
        slope=slope,
        nprocs=6,
        overwrite=True,
    )

    # Set the color tables
    gs.run_command("r.colors", map=aspect, color="aspectcolr")
    gs.run_command("r.colors", map=slope, color="sepia")
    gs.run_command("r.colors", map=pcurv, color="curvature")
    gs.run_command("r.colors", map=tcurv, color="curvature")


def simwe(elevation, dx, dy, depth, disch):
    """Run the SIMWE model"""
    print("Running the SIMWE model")
    OUTPUT_STEP = 2  # minutes
    gs.run_command(
        "r.sim.water",
        elevation=elevation,
        dx=dx,
        dy=dy,
        rain_value=50,  # mm/hr
        infil_value=0.0,  # mm/hr
        man_value=0.1,
        niterations=10,  # minutes
        output_step=OUTPUT_STEP,  # minutes
        depth=depth,  # m
        discharge=disch,  # m3/s
        random_seed=3,
        nprocs=4,
        flags="t",
        overwrite=True,
    )

    # Register the output maps into a space time dataset
    gs.run_command(
        "t.create",
        output="depth_sum",
        type="strds",
        temporaltype="absolute",
        title="Runoff Depth",
        description="Runoff Depth in [m]",
        overwrite=True,
    )

    # Get the list of depth maps
    depth_list = gs.read_command(
        "g.list", type="raster", pattern="depth.*", separator="comma"
    ).strip()

    # Register the maps
    gs.run_command(
        "t.register",
        input="depth_sum",
        type="raster",
        start="2024-01-01",
        increment=f"{OUTPUT_STEP} minutes",
        maps=depth_list,
        flags="i",
        overwrite=True,
    )


def download_naip(year=2022):
    """Download the NAIP imagery"""
    # Download the data
    print("Downloading NAIP data")
    # Create a new mapset to store raw naip data
    gs.run_command("g.mapset", mapset="naip", flags="c")
    # Import the raster into GRASS GIS
    gs.run_command(
        "t.stac.import",
        overwrite=True,
        url="https://planetarycomputer.microsoft.com/api/stac/v1",
        request_method="POST",
        collections="naip",
        datetime=year,
        asset_keys="image",
        resolution="value",
        resolution_value=1,
        extent="region",
        nprocs=10,
        memory=36000,
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

        gs.run_command(
            "r.patch",
            input=image_list,
            output=f"naip_{year}.{band_name}",
            nprocs=4,
            memory=2100,
            overwrite=True,
        )

    gs.run_command(
        "r.composite",
        red=f"naip_{year}.red",
        green=f"naip_{year}.green",
        blue=f"naip_{year}.blue",
        output=f"naip_{year}_rgb",
        overwrite=True,
    )


if __name__ == "__main__":
    gisbase = subprocess.check_output(
        ["grass", "--config", "path"], text=True
    ).strip()  # noqa: E501
    os.environ["GISBASE"] = gisbase
    # Set up GRASS GIS environment variables
    gisbase = os.getenv("GISBASE")
    gisdb = os.path.join(os.getenv("HOME"), "grassdata")

    # Ask GRASS GIS where its Python packages are.
    sys.path.append(
        subprocess.check_output(
            ["grass", "--config", "python_path"], text=True
        ).strip()  # noqa: E501
    )

    import grass.script as gs

    # Execute the main function
    sys.exit(main())
