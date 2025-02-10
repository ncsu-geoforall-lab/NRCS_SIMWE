import os
import sys
import subprocess
import time

# import concurrent.futures


# Constants
N_RUNS = 10  # How many times to run SIMWE with a different random seed
OUTPUT_STEP = 10  # SIMWE time step in minutes
NITERATIONS = 120  # Number of iterations for the SIMWE model
BASIN_THRESHOLD = 30000  # Threshold for extracting the largest basin
PROJECT_MAPSET = "sensitivity_7"
OUTPUT_DIR = "output"

# Sensitivity Analysis Parameters
SPATIAL_RESOLUTIONS = [1, 3, 10, 30]  # meters
PARTICLE_DENSITY_SCALARS = [0.25, 0.5, 1, 2]  # cells x scalar = particles

SITE_PARAMS = [
    {"site": "clay-center", "crs": "32614", "res": "3", "naip": 2021},
    {"site": "SJER", "crs": "26911", "res": "1", "naip": 2022},
    {"site": "coweeta", "crs": "26917", "res": "10", "naip": 2022},
    {"site": "SFREC", "crs": "26910", "res": "1", "naip": 2022},
    {"site": "tx069-playas", "crs": "32613", "res": "8", "naip": 2022},
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
        nprocs=6,
        overwrite=True,
    )


def create_static_map(site, res, scalar, step, method):
    dem_map = gj.Map(
        use_region=True,
        height=600,
        width=600,
        filename=f"./output/{site}/{PROJECT_MAPSET}/{site}_depth_{res}_{scalar}_s_{step}_{method}.png",  # noqa: E501
    )
    relief_map = f"elevation_{res}_relief"
    dem_map.d_shade(
        color=f"depth_{res}_{scalar}_s_{step}_{method}",
        shade=relief_map,
        brighten=30,
        overwrite=True,
    )
    dem_map.d_legend(
        raster=f"depth_{res}_{scalar}_s_{step}_{method}",
        at=(5, 50, 5, 9),
        flags="b",
    )
    dem_map.d_barscale(at=(35, 7), flags="n")
    dem_map.show()


def create_output_timeseries_gif(site, res, scalar, method):
    ts_map = gj.TimeSeriesMap()
    ts_map.add_raster_series(f"depth_{res}_{scalar}_s_{method}")
    ts_map.d_legend()
    ts_map.show()
    ts_map.save(
        f"./output/{site}/{PROJECT_MAPSET}/{site}_depth_{res}_{scalar}_s_{method}.gif"  # noqa: E501
    )


def filter_depth_maps(strds_name, output):
    # Create new rasters filtering areas where depth is less than 0.01 m
    # for raster in depth_list.split(","):
    _output = f"{output}_01m"

    gs.run_command(
        "t.rast.mapcalc",
        input=strds_name,
        output=_output,
        basename=_output,
        expression=f"{output} = if({strds_name} >= 0.01, {strds_name}, null())",  # noqa: E501
        overwrite=True,
    )


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


def threshold_label(threshold):
    if 1000 <= threshold < 1000000:
        return f"{threshold/1000:g}k"
    return str(threshold)


def extract_basins(elevation, threshold, **kwargs):
    """Extract basins from the elevation raster"""

    threshold_str = threshold_label(threshold)
    res = kwargs.get("res", 1)

    basins = f"basins{threshold_str}_{res}"
    # flowaccum = f"flowaccum{threshold_str}_{res}"
    drain_dir = f"drain_dir{threshold_str}_{res}"
    streams = f"streams{threshold_str}_{res}"
    gs.run_command(
        "r.watershed",
        elevation=elevation,
        threshold=threshold,
        # accumulation=flowaccum,
        drainage=drain_dir,
        basin=basins,
        overwrite=True,
        memory=10000,
    )

    gs.run_command(
        "r.stream.extract",
        elevation=elevation,
        threshold=threshold,
        stream_vector=streams,
        overwrite=True,
    )
    gs.run_command(
        "r.to.vect", input=basins, output=basins, type="area", overwrite=True
    )
    json_data = gs.parse_command(
        "r.report",
        map=basins,
        units="kilometers,cells,percent",
        sort="desc",
        format="json",
        flags="n",
    )
    output_basin = f"{basins}_largest"
    if json_data["categories"] and len(json_data["categories"]) > 0:
        largest_basin = json_data["categories"][0]
        output_basin = f"{basins}_largest"
        expression = f"{output_basin} = if({basins} == {largest_basin['category']}, 1, null())"  # noqa: E501
        gs.run_command("r.mapcalc", expression=expression, overwrite=True)  # noqa: E501
    else:
        print(
            f"No basins found with threshold {threshold} and resolution {res}"
        )  # noqa: F821

        # No run as of sensitivity_7 but this is used in the watershed analysis
        # where the largest basin is used to set the region of the elevation
        # layer because the threshold was to big.
        # output_basin = f"{basins}_largest"
        # expression = f"{output_basin} = if({elevation}, 1, null())"  # noqa: E501
        # gs.run_command("r.mapcalc", expression=expression, overwrite=True)  # noqa: E501

    return output_basin


def plot_envelope_curve(df_samples):
    """Plot the envelope curve"""
    import seaborn as sns
    import matplotlib.pyplot as plt

    f, ax = plt.subplots(figsize=(11, 9))
    sns.lineplot(data=df_samples, x="step", y="core")
    sns.lineplot(data=df_samples, x="step", y="mean", dashes=True)
    sns.lineplot(data=df_samples, x="step", y="envelope")
    plt.legend(["Core", "Envelope", "mean"])
    plt.show()


def get_simwe_time_steps(search_pattern):
    """Returns a list of time steps from the SIMWE output as"""
    print(f"Search Pattern: {search_pattern}")
    timestep_list = gs.read_command(
        "g.list",
        type="raster",
        pattern=search_pattern,
        separator="comma",
    ).strip()

    time_steps = [str(t.split(".")[-1]) for t in timestep_list.split(",")]

    def filter_subset(x):
        if "_01m" not in x:
            return x

    time_steps_filtered = filter(lambda x: filter_subset(x), time_steps)
    return sorted(list(set(time_steps_filtered)))


def envelope_curve(site, simtype, res, scalar):  # noqa: E501

    # Methods used by r.series
    methods = "average,median,minimum,min_raster,maximum,max_raster,stddev,range"  # noqa: E501
    scalar_str = str(scalar).replace(".", "")
    time_steps = get_simwe_time_steps(f"{simtype}_{res}_{scalar_str}_*.*")
    print(f"Time Steps: {time_steps}")
    # Iterate over the time steps from simwe output
    for step in time_steps:

        # Get list of maps for the current time step
        search_pattern = f"{simtype}_{res}_{scalar_str}_*.{step}"
        depth_list = gs.read_command(
            "g.list",
            type="raster",
            pattern=search_pattern,
            separator="comma",  # noqa: E501
        ).strip()

        # Calculate the envelop for depth maps
        series_outputs = ",".join(
            [
                f"{simtype}_{res}_{scalar_str}_s_{step}_{m}"
                for m in methods.split(",")  # noqa: E501
            ]
        )
        if depth_list:
            print(f"Output step {step} has {len(depth_list.split(','))} maps")
            gs.run_command(
                "r.series",
                input=depth_list,
                output=series_outputs,
                method=methods,
                overwrite=True,
            )

            # Update the color tables to simwe
            depth_simwe_methods = "average,median,minimum,maximum"
            depth_series_outputs = ",".join(
                [
                    f"{simtype}_{res}_{scalar_str}_s_{step}_{m}"
                    for m in depth_simwe_methods.split(",")
                ]
            )
            # Just use the first runs color map
            last_depth_time_step = depth_list.split(",")[-1]
            gs.run_command(
                "r.colors",
                map=depth_series_outputs,
                raster=last_depth_time_step,
            )

            # Update the color tables to magma
            depth_magma_methods = "min_raster,max_raster"
            depth_series_outputs = ",".join(
                [
                    f"depth_{res}_{scalar_str}_s_{step}_{m}"
                    for m in depth_magma_methods.split(",")
                ]
            )
            gs.run_command(
                "r.colors", map=depth_series_outputs, color="magma", flags="e"
            )  # noqa: E501

            for method in methods.split(","):
                create_static_map(site, res, scalar_str, step, method)

    # Create the time series of aggregated depth maps
    for method in methods.split(","):
        depth_list_avg = gs.read_command(
            "g.list",
            type="raster",
            pattern=f"{simtype}_{res}_{scalar_str}_s_*_{method}",
            separator="comma",  # noqa: E501
        ).strip()

        strds_name = f"{simtype}_{res}_{scalar_str}_s_{method}"
        gs.run_command(
            "t.create",
            output=strds_name,
            type="strds",
            temporaltype="absolute",
            title=f"{method} Runoff {simtype}",
            description=f"Runoff {simtype} in [m]",
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

        # create_output_timeseries_gif(site, res, scalar, method)
        # df_samples = sample_random_point_envelope(1, time_steps)
        # plot_envelope_curve(df_samples)


def calculate_particle_density(cells, scale_factor):
    """Calculate the particle density"""
    min_particles = 100
    max_particles = 7000000
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


def sensitivity_analysis(project_name, elevation, dx, dy, depth, disch):
    """
        Density/Resolution	0.5	1	3	5	10	30
    0.5	0.5x0.5	0.5x1	0.5x3	0.5x5	0.5x10	0.5x30
    1	1x0.5	1x1	1x3	1x5	1x10	1x30
    2	2x0.5	2x1	2x3	2x5	2x10	2x30
    4	4x0.5	4x1	4x3	4x5	4x10	4x30
    8	8x0.5	8x1	8x3	8x5	8x10	8x30
    16	16x0.5	16x1	16x3	16x5	16x10	16x30
    """

    total_runs = len(SPATIAL_RESOLUTIONS) * len(PARTICLE_DENSITY_SCALARS)
    run_n = 0
    print("Running the sensitivity analysis...")
    output_file = f"./output/{project_name}/{PROJECT_MAPSET}/sensitivity_analysis_1.csv"  # noqa: E501
    # Open csv file for writing
    with open(output_file, "w") as f:
        # Write CSV header
        f.write("site_name,resolution,scalar,cells,particles,run_n,run_time\n")
        f.flush()
        # Iterate over the model resolution parameters
        for res in SPATIAL_RESOLUTIONS:
            run_n += 1
            try:
                gs.run_command("r.mask", flags="r")
            except Exception as e:
                print(e)
                pass

            gs.run_command(
                "g.region", raster=elevation, res=res, flags="a", quiet=True
            )  # noqa: E501
            resampled_elevation = f"{elevation}_{res}"

            # Resample Elevation
            gs.run_command(
                "r.resamp.interp",
                input=elevation,
                output=resampled_elevation,
                method="bilinear",
                overwrite=True,
                nprocs=24,
                quiet=True,
            )

            basin = extract_basins(resampled_elevation, BASIN_THRESHOLD)

            # Set the region to the extent of the largest basin
            gs.run_command(
                "g.region",
                raster=basin,
                zoom=basin,
                res=res,
                flags="a",
                quiet=True,  # noqa: E501
            )

            # Calculate dx and dy
            gs.run_command(
                "r.slope.aspect",
                elevation=resampled_elevation,
                dx="dx",
                dy="dy",
                overwrite=True,
                quiet=True,
            )

            gs.run_command(
                "r.relief",
                input=resampled_elevation,
                output=f"{resampled_elevation}_relief",
                overwrite=True,
            )

            # Iterate over the particle density scalar parameters
            for scalar in PARTICLE_DENSITY_SCALARS:
                run_n += 1
                print(f"Progress: {run_n}/{total_runs}", end="\r")
                # Calculate the number of particles
                cells = cell_count(basin)
                particles = calculate_particle_density(cells, scalar)
                print(
                    f"Resolution: {res}, Cells: {cells}, Particles: {particles}"  # noqa: E501
                )

                # Run monte carlo simulation of the model
                n_runs = 10
                for i in range(n_runs):
                    gs.run_command("r.mask", raster=basin, overwrite=True)
                    scalar_str = str(scalar).replace(".", "")
                    depth_x = f"{depth}_{res}_{scalar_str}_{i}"
                    dish_y = f"{disch}_{res}_{scalar_str}_{i}"
                    error = f"error_{res}_{scalar_str}_{i}"
                    strds_depth, strds_disch, run_time = simwe(
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

                    f.write(
                        f"{project_name},{res},{scalar},{cells},{particles},{i},{run_time}\n"  # noqa: E501
                    )
                    f.flush()

                    # Remove mask or else r.series will fail to use parallel
                    # processing and then throw an error.
                    gs.run_command("r.mask", flags="r")

                    # Calculate the statistics of the depth and discharge maps
                    strds_stats_maps(strds_depth, f"{strds_depth}_stats")
                    strds_stats_maps(strds_disch, f"{strds_disch}_stats")

                envelope_curve(project_name, "depth", res, scalar)
                envelope_curve(project_name, "disch", res, scalar)


def simwe(
    elevation, dx, dy, depth, disch, particles, res, scalar, error, **kwargs
):  # noqa: E501
    """Run the SIMWE model"""
    random_seed = kwargs.get("random_seed", None)
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
        niterations=NITERATIONS,  # event duration (minutes)
        output_step=OUTPUT_STEP,  # minutes
        depth=depth,  # m
        discharge=disch,  # m3/s
        random_seed=random_seed,  # Selct a distinct random seed
        error=error,  # m
        nprocs=1,
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

    return depth_strds_name, disch_strds_name, elapsed_time


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

        # output_dir_base = "output"
        output_dir = os.path.join(OUTPUT_DIR, project_name, PROJECT_MAPSET)
        print(
            f"Output Directory: {output_dir}, exists: {os.path.exists(output_dir)}"  # noqa: E501
        )  # noqa: E501
        if not os.path.exists(output_dir):
            print("Creating output directory...")
            os.makedirs(output_dir)

        sensitivity_analysis(project_name, elevation, dx, dy, depth, disch)

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
