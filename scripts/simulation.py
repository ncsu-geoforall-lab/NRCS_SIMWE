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
                simulate(project_name, elevation_data)
            except ValueError:
                exit(1)


def simulate(project_name, elevation_data):
    """Run the simulation"""
    print("Running simulation...")
    gs.run_command("g.mapset", mapset=PROJECT_MAPSET, flags="c")
    # Set region
    gs.run_command("g.region", raster=elevation_data, flags="ap")
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
        resolution_value=3,
        resample="bicubic",
        title="Elevation",
        overwrite=True,
    )

    # Return the output raster name
    return output_name


def calculate_partial_derivites(elevation, dx="dx", dy="dy", aspect="aspect"):
    """Calculate the partial derivatives"""
    print("Calculating partial derivatives")
    gs.run_command(
        "r.slope.aspect",
        elevation=elevation,
        dx=dx,
        dy=dy,
        aspect=aspect,
        nprocs=4,
        overwrite=True,
    )


def simwe(elevation, dx, dy, depth, disch):
    """Run the SIMWE model"""
    print("Running the SIMWE model")
    gs.run_command(
        "r.sim.water",
        elevation=elevation,
        dx=dx,
        dy=dy,
        rain_value=50,  # mm/hr
        infil_value=0.0,  # mm/hr
        man_value=0.1,
        niterations=10,  # minutes
        output_step=2,  # minutes
        depth=depth,  # m
        discharge=disch,  # m3/s
        random_seed=3,
        nprocs=4,
        flags="t",
        overwrite=True,
    )


# Define entry point
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
