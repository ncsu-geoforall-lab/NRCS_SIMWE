#!/usr/bin/env python3

import os
import sys
import subprocess


BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"
PROJECT_MAPSET = "basic60"

RAIN_PER_MM_HR = 50  # mm/hr
RAIN_INTENSITY_IN_HR = 4.34  # inches per hour
RAIN_DURATION_MIN = 46.97  # minutes


# Define main function
def main():
    project_name = None
    with open("site-CRS-info.txt", "r") as file:
        data = file.readlines()
        for line in data:
            try:
                project_name, projcrs, resolution, naip = line.split(":")[:4]
                print(f"Project Name: {project_name}")
                # Initialize the GRASS session
                gs.setup.init(gisdb, project_name, PROJECT_MAPSET)
                # Import the elevation raster
                elevation_data = "elevation"
                simulate(project_name, elevation_data)
            except ValueError:
                exit(1)


def prepare_soil_data(project_name):
    gs.run_command(
        "r.in.ssurgo",
        soils="soil_areas_sda",
        hydgrp="hydgrp_sda",
        ksat_l="ksat_l_sda",
        ksat_r="ksat_r_sda",
        ksat_h="ksat_h_sda",
        mukey="mukey_sda",
        hzdept_r=0,
        hzdepb_r=100,
        desgnmaster="A",
        nprocs=30,
    )

    m = gj.Map(
        use_region=True,
        filename=f"../output/{project_name}/{PROJECT_MAPSET}/ksat_r_sda.png",
    )
    m.d_shade(shade="relief", color="ksat_r_sda")
    m.d_legend(raster="ksat_r_sda", title="Ksat (mm/hr)", flags="db")
    m.show()

    # Curvnumber
    gs.run_command(
        "r.curvenumber",
        landcover="nlcd_2024",
        soil="hydgrp_sda",
        landcover_source="nlcd",
        output="curvenumber",
    )

    # Watershed analysis
    gs.run_command(
        "r.watershed",
        elevation="elevation",
        drainage="flow_direction",
        accumulation="accumulation",
        stream="stream",
        basin="basins",
        threshold=10,
    )

    # Time of concentration
    gs.run_command(
        "r.timeofconcentration",
        elevation="elevation",
        direction="flow_direction",
        stream="stream",
        length_min=100,  # minimum length of flow path
        tc="time_concentration",
    )

    intensity_mm_hr = RAIN_INTENSITY_IN_HR * 25.4
    duration_hr = RAIN_DURATION_MIN / 60.0
    rain_mm = intensity_mm_hr * duration_hr

    print(f"Storm duration: {duration_hr:.4f} hr")
    print(f"Rainfall intensity: {intensity_mm_hr:.3f} mm/hr")
    print(f"Rain depth: {rain_mm:.3f} mm")
    gs.run_command(
        "r.mapcalc",
        expression=f"rain = {rain_mm}",  # mm of precipitation
    )


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
    # Define the GRASS GIS database directory
    gisdb = os.path.join(os.getenv("HOME"), "grassdata")

    # Ask GRASS GIS where its Python packages are.
    sys.path.append(
        subprocess.check_output(["grass", "--config", "python_path"], text=True).strip()  # noqa: E501
    )

    import grass.script as gs
    import grass.jupyter as gj

    # Execute the main function
    sys.exit(main())
