#!/usr/bin/env python3

import os
import sys
import subprocess


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
                elevation_data = "elevation"
                geomorphology(elevation_data)
            except ValueError:
                exit(1)


def geomorphology(elevation_data):
    """Calculate Geomorphology"""
    print("Calculating geomorphology...")
    # Set region
    gs.run_command("g.region", raster=elevation_data, flags="ap")
    # Calculate geomorphological features
    calculate_geomorphon(elevation_data)
    # Calculate partial derivatives
    calculate_partial_derivites(elevation_data)
    # Calculate hillshade
    calculate_hillshade(elevation_data)


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
    print("Calculating partial derivatives, slope, aspect, and curvatures")
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


def calculate_hillshade(elevation, hillshade="hillshade"):
    """Calculate the hillshade"""
    print("Calculating hillshade")
    gs.run_command(
        "r.relief",
        input=elevation,
        output=hillshade,
        zscale=1,
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
