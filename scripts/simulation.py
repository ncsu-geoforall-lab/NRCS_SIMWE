#!/usr/bin/env python3

import os
import sys
import subprocess


BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"
PROJECT_MAPSET = "basic60"


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
                gs.setup.init(gisdb, project_name, PROJECT_MAPSET)
                # Import the elevation raster
                elevation_data = "elevation"
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
    # simwe(elevation_data, "dx", "dy", "depth", "disch")
    simwe(elevation_data, "dx", "dy", "depth", "disch", niterations=60)


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
    gs.run_command("r.colors", map=slope, color="sepia", flags="e")
    gs.run_command("r.colors", map=pcurv, color="curvature")
    gs.run_command("r.colors", map=tcurv, color="curvature")


def simwe(elevation, dx, dy, depth, disch, **kwargs):
    """Run the SIMWE model"""
    print("Running the SIMWE model")
    niterations = kwargs.get("niterations", 10)
    OUTPUT_STEP = 2  # minutes
    gs.run_command(
        "r.sim.water",
        elevation=elevation,
        dx=dx,
        dy=dy,
        rain_value=50,  # mm/hr
        infil_value=0.0,  # mm/hr
        man_value=0.1,
        niterations=niterations,  # event duration (minutes)
        output_step=OUTPUT_STEP,  # minutes
        depth=depth,  # m
        discharge=disch,  # m3/s
        random_seed=3,
        nprocs=30,
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

    # Register the output maps into a space time dataset
    gs.run_command(
        "t.create",
        output="disch_sum",
        type="strds",
        temporaltype="absolute",
        title="Runoff Discharge",
        description="Runoff Discharge in [m3/s]",
        overwrite=True,
    )

    # Get the list of disch maps
    disch_list = gs.read_command(
        "g.list", type="raster", pattern="disch.*", separator="comma"
    ).strip()

    # Register the maps
    gs.run_command(
        "t.register",
        input="disch_sum",
        type="raster",
        start="2024-01-01",
        increment=f"{OUTPUT_STEP} minutes",
        maps=disch_list,
        flags="i",
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
