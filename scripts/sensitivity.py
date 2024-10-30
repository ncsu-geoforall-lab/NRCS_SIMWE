import os
import sys
import subprocess


# Create stats for depth and discharge maps for the stochasic simulations
def strds_stats_maps(input_strds, output):
    methods = "average,median,minimum,min_raster,maximum,max_raster,stddev,range"  # noqa: E501
    outputs = ",".join([f"{output}_{m}" for m in methods.split(",")])
    gs.run_command(
        "t.rast.series",
        input=input_strds,
        output=outputs,
        method=methods,
        flags="t",
        nprocs=30,
        overwrite=True,
    )


def envelope_curve():
    pass


def calculate_particle_density(cells, scale_factor):
    """Calculate the particle density"""
    min_particles = 1000
    max_particles = 1e6
    particles = cells * scale_factor
    if particles < min_particles:
        gs.warning(
            _(  # noqa: F821
                f"Number of particles is less than the minimum threshold of {min_particles}"  # noqa: E501
            )
        )
        particles = min_particles

    if particles > max_particles:
        gs.warning(
            _(  # noqa: F821
                f"Number of particles is greater than the maximum threshold of {max_particles}"  # noqa: E501
            )
        )
        particles = max_particles

    return particles


def sensitivity_analysis(elevation, dx, dy, depth, disch):
    """
        Density/Resolution	0.5	1	3	5	10	30
    0.5	0.5x0.5	0.5x1	0.5x3	0.5x5	0.5x10	0.5x30
    1	1x0.5	1x1	1x3	1x5	1x10	1x30
    2	2x0.5	2x1	2x3	2x5	2x10	2x30
    4	4x0.5	4x1	4x3	4x5	4x10	4x30
    8	8x0.5	8x1	8x3	8x5	8x10	8x30
    16	16x0.5	16x1	16x3	16x5	16x10	16x30
    """
    model_spatial_res_params = [1, 3, 5, 10, 30]  # meters
    model_particle_density_scalar_params = [0.5, 1, 2, 4, 8]
    total_runs = len(model_spatial_res_params) * len(
        model_particle_density_scalar_params
    )
    run_n = 0
    print("Running the sensitivity analysis...")
    for res in model_spatial_res_params:
        gs.run_command("g.region", raster=elevation, res=res, flags="a")
        resampled_elevation = f"{elevation}_{res}"

        # Resample Elevation
        gs.run_command(
            "r.resamp.interp",
            input=elevation,
            output=resampled_elevation,
            method="bilinear",
            overwrite=True,
            nprocs=6,
        )

        # Calculate dx and dy
        gs.run_command(
            "r.slope.aspect",
            elevation=resampled_elevation,
            dx="dx",
            dy="dy",
            overwrite=True,
        )

        for scalar in model_particle_density_scalar_params:
            print(f"Progress: {run_n+1}/{total_runs}", end="\r")
            # Calculate the number of particles
            cells = cell_count(resampled_elevation)
            particles = calculate_particle_density(cells, scalar)
            # Run monte carlo simulation of the model
            n_runs = 10
            for i in range(n_runs):

                scalar_str = str(scalar).replace(".", "")
                depth_x = f"{depth}_{res}_{scalar_str}_{i}"
                dish_y = f"{disch}_{res}_{scalar_str}_{i}"
                strds_depth, strds_disch = simwe(
                    resampled_elevation,
                    dx,
                    dy,
                    depth_x,
                    dish_y,
                    particles,
                    res,
                    scalar,
                    random_seed=i,
                )

                strds_stats_maps(strds_depth, f"{strds_depth}_stats")
                strds_stats_maps(strds_disch, f"{strds_disch}_stats")


def simwe(
    elevation, dx, dy, depth, disch, particles, res, scalar, **kwargs
):  # noqa: E501
    """Run the SIMWE model"""
    print("Running the SIMWE model")
    niterations = 30
    random_seed = kwargs.get("random_seed", None)
    OUTPUT_STEP = 5  # minutes
    gs.run_command(
        "r.sim.water",
        elevation=elevation,
        dx=dx,
        dy=dy,
        rain_value=50,  # mm/hr
        infil_value=0.0,  # mm/hr
        man_value=0.1,
        nwalkers=particles,
        niterations=niterations,  # event duration (minutes)
        output_step=OUTPUT_STEP,  # minutes
        depth=depth,  # m
        discharge=disch,  # m3/s
        random_seed=random_seed,  # Selct a distinct random seed
        nprocs=30,
        flags="t",
        overwrite=True,
    )

    # Register the output maps into a space time dataset
    scalar_str = str(scalar).replace(".", "")
    depth_strds_name = f"depth_sum_{res}_{scalar_str}_{random_seed}"
    disch_strds_name = f"disch_sum_{res}_{scalar_str}_{random_seed}"

    gs.run_command(
        "t.create",
        output=depth_strds_name,
        type="strds",
        temporaltype="absolute",
        title="Runoff Depth",
        description="Runoff Depth in [m]",
        overwrite=True,
    )

    # Get the list of depth maps
    depth_list = gs.read_command(
        "g.list", type="raster", pattern=f"{depth}.*", separator="comma"
    ).strip()

    # Register the maps
    gs.run_command(
        "t.register",
        input=depth_strds_name,
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
        output=disch_strds_name,
        type="strds",
        temporaltype="absolute",
        title="Runoff Discharge",
        description="Runoff Discharge in [m3/s]",
        overwrite=True,
    )

    # Get the list of disch maps
    disch_list = gs.read_command(
        "g.list", type="raster", pattern=f"{disch}.*", separator="comma"
    ).strip()

    # Register the maps
    gs.run_command(
        "t.register",
        input=disch_strds_name,
        type="raster",
        start="2024-01-01",
        increment=f"{OUTPUT_STEP} minutes",
        maps=disch_list,
        flags="i",
        overwrite=True,
    )

    return depth_strds_name, disch_strds_name


def cell_count(elevation):
    """Count the number of cells in the elevation raster"""
    univar = gs.parse_command("r.univar", map=elevation, format="json")
    cells = univar[0]["n"]
    print(f"Number of cells: {cells}")
    return cells


def main():

    PROJECT_MAPSET = "sensitivity"

    SITE_PARAMS = [
        {"site": "clay-center", "crs": "32614", "res": "3", "naip": 2021},
        # {"site": "coweeta", "crs": "26917", "res": "10", "naip": 2022},
        # {"site": "SFREC", "crs": "26910", "res": "1", "naip": 2022},
        # {"site": "SJER", "crs": "26911", "res": "1", "naip": 2022},
        # {"site": "tx069-playas", "crs": "32613", "res": "8", "naip": 2022},
    ]

    elevation = "elevation"
    dx = "dx"
    dy = "dy"
    depth = "depth"
    disch = "disch"

    for site in SITE_PARAMS:
        project_name = site["site"]
        print(f"Project Name: {project_name}/{PROJECT_MAPSET}")
        # Initialize the GRASS session
        try:
            gs.setup.init(gisdb, project_name, "PERMANENT")
            gs.run_command("g.mapset", mapset=PROJECT_MAPSET, flags="c")  # noqa: E501
        except Exception as e:
            print(f"Error: {e}")
            exit(1)

        sensitivity_analysis(elevation, dx, dy, depth, disch)

    # Create floor and ceiling maps for the stochasic runs

    # Create stability/disturbance maps for the stochasic runs

    # Create the sensitivity analysis

    # Identify sampling locations for hydrograph generation
    # Ground truthing...

    # TODO
    # https://salib.readthedocs.io/en/latest/user_guide/basics.html#what-is-sensitivity-analysis


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
