#!/usr/bin/env python3

import os
import sys
import subprocess
import matplotlib.pyplot as plt
from PIL import Image


def simwe_to_strds(
    search_pattern: str,
    strds_output: str,
    title: str,
    description: str,
    output_step: int = 10,
) -> str:  # noqa: E501
    """Create a strds data set from simwe output maps"""
    # Register the output maps into a space time dataset
    gs.run_command(
        "t.create",
        output=strds_output,
        type="strds",
        temporaltype="absolute",
        title=title,
        description=description,
        overwrite=True,
    )

    # Get the list of depth maps
    raster_list = gs.read_command(
        "g.list", type="raster", pattern=search_pattern, separator="comma"
    ).strip()

    # Register the maps
    gs.run_command(
        "t.register",
        input=strds_output,
        type="raster",
        start="2024-01-01",
        increment=f"{output_step} minutes",
        maps=raster_list,
        flags="i",
        overwrite=True,
    )

    return strds_output


def ground_water_seepage(
    flow_accum: str, output_streams: str, threshold: int = 150
):  # noqa: E501
    """
    Adds baseflow to streams,
    needs to be run until it reaches steady state
    """
    gs.mapcalc(
        f"{output_streams} = if({flow_accum} > {threshold}, 10, 0)",
        overwrite=True,
    )
    return output_streams


def ground_water_springs(
    flow_accum: str,
    springs: str,
    springs2: str,
    threshold1: int = 150,
    threshold2: int = 250,
    threshold3: int = 300,
):
    """compute source - groundwater springs at first order streams, no rain"""
    gs.mapcalc(
        f"{springs} = if("
        f"{flow_accum} > {threshold1} && {flow_accum} < {threshold2}, "
        "10, 0)",
        overwrite=True,
    )
    gs.mapcalc(
        f"{springs2} = if(({flow_accum} > {threshold2}) & ({flow_accum} "
        f"< {threshold3}), 10, 0)",
        overwrite=True,
    )


def sim_ground_water_seepage(
    elevation,
    dx,
    dy,
    streams,
    depth,
    discharge,
    rain_loaded_streams=None,
    rain=50,
    nwalk=500000,
    niterations=30,
    output_step=10,
):
    """simwe with gw stream seepage and rain"""
    _streams = streams
    # Add rain to the baseflow to streams
    if rain_loaded_streams:
        gs.mapcalc(
            f"{rain_loaded_streams} = {rain} + {streams}", overwrite=True
        )  # noqa: E501
        _streams = rain_loaded_streams

    gs.run_command(
        "r.sim.water",
        elevation=elevation,
        dx=dx,
        dy=dy,
        rain=_streams,  # mm/hr
        depth=depth,  # m
        discharge=discharge,  # m3/s
        infil_value=0.0,  # mm/hr
        man_value=0.1,
        niterations=niterations,  # event duration (minutes)
        output_step=output_step,  # minutes
        nwalkers=nwalk,
        random_seed=3,
        nprocs=30,
        flags="t",
        overwrite=True,
    )


def generate_plots(n_rows, n_cols, plot_params, figure_name):
    fig = plt.figure(figsize=(25, 30))
    fig.subplots_adjust(hspace=0, wspace=0.1)

    for i, params in enumerate(plot_params):
        ax = fig.add_subplot(n_rows, n_cols, i + 1)
        ax.set_axis_off()
        img = Image.open(params["filename"])
        plt.imshow(img)
        ax.set_title(
            params["rast_map"], {"fontsize": 24, "fontweight": "bold"}
        )  # noqa: E501

        # Add section title for each row
        if i % n_cols == 0:
            section_title = f"{params['title']}"
            ax.annotate(
                section_title,
                xy=(0, 0),
                xytext=(0, -50),
                textcoords="offset points",
                ha="center",
                va="top",
                fontsize=24,
                fontweight="bold",
                rotation=90,
            )

    plt.tight_layout()
    plt.savefig(figure_name, bbox_inches="tight", dpi=300)


def create_model_run(output_dir, site, mapset, search_pattern, title):
    sim_plot_params = []
    # sim_values = [str(i).zfill(2) for i in range(2, 61, 2)]

    pattern = search_pattern
    data_list = (
        gs.read_command(
            "g.list", type="raster", pattern=pattern, separator="comma"
        )  # noqa: E501
        .strip()
        .split(",")
    )
    print(data_list)

    out_file = os.path.join(output_dir, f"{title}_simulation.png")

    for i in data_list:
        map_name = i
        filename = os.path.join(output_dir, f"{i.replace('.', '_')}.png")
        gj.init(gisdb, site, mapset)
        map_obj = gj.Map(
            filename=filename, use_region=True, height=600, width=600
        )  # noqa: E501
        # map_obj.d_rast(map=map_name)
        _map_name = f"{map_name}@{mapset}"
        map_obj.d_shade(color=_map_name, shade="hillshade")
        map_obj.d_legend(raster=_map_name, at=(5, 50, 5, 9), flags="b")
        map_obj.d_barscale(at=(35, 7), flags="n")
        map_obj.show()
        # title = "Depth (m)" if simtype == "depth" else "Discharge (m3/s)"
        output_params = {
            "filename": filename,
            "title": f"{site} {title}",
            "rast_map": f"{i.split('.')[-1]} minutes",
        }
        sim_plot_params.append(output_params)

    generate_plots(1, 5, sim_plot_params, out_file)


def create_figures(output_directory, mapset, site):
    output_dir = os.path.join(output_directory, site, mapset)
    if not os.path.exists(output_dir):
        os.makedirs(os.path.join(output_directory, site, mapset))

    create_model_run(
        output_dir,
        site,
        mapset,
        "depth_rain_gw.*",
        "Simulated groundwater seepage in streams during rainfall (Depth)",
    )
    create_model_run(
        output_dir,
        site,
        mapset,
        "disch_rain_gw.*",
        "Simulated groundwater seepage in streams during rainfall (Discharge)",
    )

    create_model_run(
        output_dir,
        site,
        mapset,
        "depth_gw.*",
        "Simulated groundwater seepage in streams no rainfall (Depth)",
    )
    create_model_run(
        output_dir,
        site,
        mapset,
        "disch_gw.*",
        "Simulated groundwater seepage in streams no rainfall (Discharge)",
    )

    create_model_run(
        output_dir,
        site,
        mapset,
        "depth_springs.*",
        "Simulated groundwater seepage, springs only (Depth)",
    )
    create_model_run(
        output_dir,
        site,
        mapset,
        "disch_springs.*",
        "Simulated groundwater seepage, springs only (Discharge)",
    )


def main():
    PROJECT_MAPSET = "ground_water2"
    elevation = "elevation"
    dx = "dx"
    dy = "dy"
    rain = 10
    flow_accum = "accum_10K"
    base_streams_level = "base_stream_level"
    rain_loaded_streams = "rain_loaded_streams"
    springs = "springs"
    springs2 = "springs2"

    project_name = None
    with open("site-CRS-info.txt", "r") as file:
        data = file.readlines()
        for line in data:
            try:
                project_name, projcrs, resolution, naip = line.split(":")
                print(f"Project Name: {project_name}/{PROJECT_MAPSET}")
                # Initialize the GRASS session
                try:
                    gs.setup.init(gisdb, project_name, "PERMANENT")
                    gs.run_command(
                        "g.mapset", mapset=PROJECT_MAPSET, flags="c"
                    )  # noqa: E501
                except Exception as e:
                    print(f"Error: {e}")
                    exit(1)

                print(f"Setting Region: res={resolution}")

                gs.run_command(
                    "g.region", raster=elevation, res=resolution, flags="ap"
                )  # noqa: E501

                print("Calculating partial derivatives")
                gs.run_command(
                    "r.slope.aspect",
                    elevation=elevation,
                    dx=dx,
                    dy=dy,
                    nprocs=6,
                    overwrite=True,
                )

                gs.run_command(
                    "r.relief",
                    input=elevation,
                    output="hillshade",
                    zscale=1,
                    overwrite=True,
                )

                print("Calculating flow accumulation")
                gs.run_command(
                    "r.watershed",
                    elevation=elevation,
                    basin="basin_10k",
                    accumulation=flow_accum,
                    threshold=10000,
                    overwrite=True,
                )

                print("Calculating base line streams level")
                base_streams_level = ground_water_seepage(
                    flow_accum,
                    output_streams="base_stream_level",
                    threshold=150,  # noqa: E501
                )

                print("Calculating spring seepage")
                ground_water_springs(
                    flow_accum,
                    springs=springs,
                    springs2=springs2,
                    threshold1=150,
                    threshold2=250,
                    threshold3=300,
                )

                # Simulate groundwater seepage in streams during rainfall
                print("Simulating rain and baseline streams")
                sim_ground_water_seepage(
                    elevation=elevation,
                    dx=dx,
                    dy=dy,
                    streams=base_streams_level,
                    rain_loaded_streams=rain_loaded_streams,
                    depth="depth_rain_gw",
                    discharge="disch_rain_gw",
                    rain=rain,
                    nwalk=500000,
                    niterations=20,
                    output_step=4,
                )

                # Simulate groundwater seepage in streams no rainfall
                print("Simulating groundwater seepage in streams no rainfall")
                sim_ground_water_seepage(
                    elevation=elevation,
                    dx=dx,
                    dy=dy,
                    streams=base_streams_level,
                    depth="depth_gw",
                    discharge="disch_gw",
                    rain=rain,
                    nwalk=500000,
                    niterations=20,
                    output_step=4,
                )

                # "springs" only
                print("Simulating springs only")
                sim_ground_water_seepage(
                    elevation=elevation,
                    dx=dx,
                    dy=dy,
                    streams=springs,
                    depth="depth_springs",
                    discharge="disch_springs",
                    rain=rain,
                    nwalk=500000,
                    niterations=20,
                    output_step=4,
                )
                simwe_to_strds(
                    search_pattern="depth_rain_gw.*",
                    strds_output="depth_rain_gw_sum",
                    title="Runoff Depth",
                    description="Runoff Depth in [m]",
                    output_step=4,
                )
                simwe_to_strds(
                    search_pattern="disch_rain_gw.*",
                    strds_output="disch_rain_gw_sum",
                    title="Runoff Discharge",
                    description="Runoff Discharge in [m3/s]",
                    output_step=4,
                )
                simwe_to_strds(
                    search_pattern="depth_gw.*",
                    strds_output="depth_gw_sum",
                    title="Runoff Depth",
                    description="Runoff Depth in [m]",
                    output_step=4,
                )
                simwe_to_strds(
                    search_pattern="disch_gw.*",
                    strds_output="disch_gw_sum",
                    title="Runoff Discharge",
                    description="Runoff Discharge in [m3/s]",
                    output_step=4,
                )
                simwe_to_strds(
                    search_pattern="depth_springs.*",
                    strds_output="depth_springs_sum",
                    title="Runoff Depth",
                    description="Runoff Depth in [m]",
                    output_step=4,
                )
                simwe_to_strds(
                    search_pattern="disch_springs.*",
                    strds_output="disch_springs_sum",
                    title="Runoff Discharge",
                    description="Runoff Discharge in [m3/s]",
                    output_step=4,
                )
                create_figures("output", PROJECT_MAPSET, project_name)  # noqa: E501
            except ValueError:
                exit(1)


if __name__ == "__main__":
    # Define the path to the GRASS GIS database
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
