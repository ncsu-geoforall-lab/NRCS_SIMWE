import os
import sys
import subprocess
import time

# Constants
N_RUNS = 10  # How many times to run SIMWE with a different random seed
OUTPUT_STEP = 5  # SIMWE time step in minutes
PROJECT_MAPSET = "sensitivity"

SITE_PARAMS = [
    {"site": "clay-center", "crs": "32614", "res": "3", "naip": 2021},
    # {"site": "coweeta", "crs": "26917", "res": "10", "naip": 2022},
    # {"site": "SFREC", "crs": "26910", "res": "1", "naip": 2022},
    # {"site": "SJER", "crs": "26911", "res": "1", "naip": 2022},
    # {"site": "tx069-playas", "crs": "32613", "res": "8", "naip": 2022},
]


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


def create_static_map(site, step, method):
    dem_map = gj.Map(
        use_region=True,
        height=600,
        width=600,
        filename=f"output/{site}_depth_1_1_s_{step}_{method}.png",
    )
    dem_map.d_shade(
        color=f"depth_1_1_s_{step}_{method}", shade="relief", brighten=30
    )  # noqa: E501
    dem_map.d_legend(
        raster=f"depth_1_1_s_{step}_{method}", at=(5, 50, 5, 9), flags="b"
    )  # noqa: E501
    dem_map.d_barscale(at=(35, 7), flags="n")
    dem_map.show()


def create_output_timeseries_gif(site, method):
    ts_map = gj.TimeSeriesMap()
    ts_map.add_raster_series(f"depth_1_1_s_{method}")
    ts_map.d_legend()
    ts_map.show()
    ts_map.save(f"output/{site}_depth_1_1_s_{method}.gif")


def sample_random_point_envelope(n, time_steps):
    import pandas as pd

    tmp_data = []
    gs.run_command("v.random", output="random_points", npoints=n, seed=7)
    for step in time_steps:
        json_output = gs.parse_command(
            "r.what",
            points="random_points",
            map=f"depth_1_1_s_{step}_median,depth_1_1_s_{step}_minimum,depth_1_1_s_{step}_maximum",  # noqa: E501
            format="json",
        )
        new_json = {
            "step": int(step),
            "core": json_output[0][f"depth_1_1_s_{step}_minimum"]["value"],
            "envelope": json_output[0][f"depth_1_1_s_{step}_maximum"]["value"],
            "median": json_output[0][f"depth_1_1_s_{step}_median"]["value"],
        }
        tmp_data.append(new_json)

    df = pd.DataFrame(tmp_data)
    return df


def plot_envelope_curve(df_samples):
    """Plot the envelope curve"""
    import seaborn as sns
    import matplotlib.pyplot as plt

    f, ax = plt.subplots(figsize=(11, 9))
    sns.lineplot(data=df_samples, x="step", y="core")
    sns.lineplot(data=df_samples, x="step", y="median", dashes=True)
    sns.lineplot(data=df_samples, x="step", y="envelope")
    plt.legend(["Core", "Envelope", "Median"])
    plt.show()


def envelope_curve(site, time_steps=["05", "10", "15", "25", "30"]):
    # Get flow likihood

    for step in time_steps:
        search_pattern = f"depth_1_1_*.{step}"
        depth_list_05 = gs.read_command(
            "g.list",
            type="raster",
            pattern=search_pattern,
            separator="comma",  # noqa: E501
        ).strip()

        for raster in depth_list_05.split(","):
            output = f"{raster}_01m"
            gs.run_command(
                "r.mapcalc",
                expression=f"{output} = if({raster} >= 0.01, {raster}, null())",  # noqa: E501
            )

            search_pattern = f"depth_1_1_*.{step}_01m"
            depth_list_05 = gs.read_command(
                "g.list",
                type="raster",
                pattern=search_pattern,
                separator="comma",  # noqa: E501
            ).strip()
            method = "maximum"
            gs.run_command(
                "r.series",
                input=depth_list_05,
                output=f"depth_1_1_s_{step}_{method}",
                method=method,
            )

            gs.run_command(
                "r.colors",
                map=f"depth_1_1_s_{step}_{method}",
                raster=f"depth_1_1_1.{step}",
            )
            # gs.run_command(
            #   "r.colors",
            # map=f"depth_1_1_s_{step}_{method}",
            # color="magma",
            # flags="e"
            # )
            create_static_map(site, step, method)

    depth_list_avg = gs.read_command(
        "g.list",
        type="raster",
        pattern=f"depth_1_1_s_*_{method}",
        separator="comma",  # noqa: E501
    ).strip()

    strds_name = f"depth_1_1_s_{method}"
    gs.run_command(
        "t.create",
        output=strds_name,
        type="strds",
        temporaltype="absolute",
        title=f"{method} Runoff Depth",
        description="Runoff Depth in [m]",
        overwrite=True,
    )

    gs.run_command(
        "t.register",
        input=strds_name,
        type="raster",
        start="2024-01-01",
        increment=f"{OUTPUT_STEP} minutes",
        maps=depth_list_avg,
        flags="i",
        overwrite=True,
    )

    create_output_timeseries_gif(site, method, time_steps)
    df_samples = sample_random_point_envelope(1, time_steps)
    plot_envelope_curve(df_samples)


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
                error = f"error_{res}_{scalar_str}_{i}"
                strds_depth, strds_disch = simwe(
                    resampled_elevation,
                    dx,
                    dy,
                    depth_x,
                    dish_y,
                    particles,
                    res,
                    scalar,
                    error,
                    random_seed=i,
                )

                strds_stats_maps(strds_depth, f"{strds_depth}_stats")
                strds_stats_maps(strds_disch, f"{strds_disch}_stats")


def simwe(
    elevation, dx, dy, depth, disch, particles, res, scalar, error, **kwargs
):  # noqa: E501
    """Run the SIMWE model"""
    niterations = 30
    random_seed = kwargs.get("random_seed", None)
    OUTPUT_STEP = 5  # minutes
    print(
        f"""
        Running the SIMWE model: Res:{res}, Scalar:{scalar}, Seed:{random_seed}
    """
    )
    start_time = time.time()
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
        error=error,  # m
        nprocs=30,
        flags="t",
        overwrite=True,
    )
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time} seconds")
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
    import grass.jupyter as gj

    # Execute the main function
    sys.exit(main())
