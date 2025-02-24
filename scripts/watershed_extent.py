import os
import sys
import subprocess
import json

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


def threshold_label(threshold: int) -> str:
    """Return a string label for the threshold."""
    if 1000 <= threshold < 1000000:
        return f"{threshold/1000:g}k"
    return str(threshold)


def watershed_extent_stats(basins: str) -> list[dict]:
    """Return the statistics for the watershed extents."""
    # Get the average basin extent
    json_data: json = gs.parse_command(
        "r.report",
        map=basins,
        units="kilometers,cells,percent",
        sort="desc",
        format="json",
        flags="",
    )

    print(json_data)

    basin_stats: list[dict] = json_data["categories"]

    return basin_stats


def basin_exists(basin: str) -> bool:
    """Check if the basin exists."""
    files_exist = (
        gs.find_file(basin, element="raster", mapset=PROJECT_MAPSET)["name"]
        != ""  # noqa: E501
    )
    print(f"Checking if basin {basin} exists: {files_exist}")
    return files_exist


def basin_exists_update(options: dict[str, str]) -> str:
    """Check if the basin exists."""
    basin = options["basin"]
    res = options["res"]
    default_region = f"elevation_{res}"
    files_exist = (
        gs.find_file(basin, element="raster", mapset=PROJECT_MAPSET)["name"]
        != ""  # noqa: E501
    )
    print(f"Checking if basin {basin} exists: {files_exist}")
    if files_exist:
        return basin
    print(f"Basin {basin} does not exist, creating it...")
    gs.run_command("g.region", raster=default_region, flags="pa")
    expression = f"{basin} = if({default_region}, 1, null())"
    gs.run_command("r.mapcalc", expression=expression, overwrite=True)
    return default_region


def watershed_extent_overlap() -> tuple[str, str]:
    """
    Return the overlap between the basins generated at different
    resolutions.
    """

    # Get list of the largest basins for each resolution
    threshold_str = threshold_label(BASIN_THRESHOLD)
    basins_series = [
        f"basins{threshold_str}_{res}_largest" for res in SPATIAL_RESOLUTIONS
    ]  # noqa: E501
    basins_series_clean = list(
        map(
            lambda largest_basin: basin_exists_update(
                {"basin": largest_basin, "res": largest_basin.split("_")[-2]}
            ),
            basins_series,
        )
    )  # noqa: E501
    # Count the number of basins that overlap
    gs.run_command(
        "g.region", raster=f"elevation_{1}", flags="pa"
    )  # Set region to highest resolution  # noqa: E501

    count_raster = f"basins_overlap_{threshold_str}"
    gs.run_command(
        "r.series",
        input=basins_series_clean,
        output=count_raster,
        method="count",
        nprocs=4,
        overwrite=True,
    )

    # Calculate the percentage of overlap
    percent_overlap = f"{count_raster}_pct"
    series_len = len(basins_series_clean)
    gs.mapcalc(
        f"{percent_overlap} = float({count_raster}) / float({series_len})",
        overwrite=True,
    )
    return (count_raster, percent_overlap)


def watershed_overlap_map(overlap_raster: str, filename: str) -> str:
    """Create the map of overlapping basins."""
    # relief_map = f"elevation_{res}_relief"
    overlap_map = gj.Map(
        use_region=True,
        height=600,
        width=600,
        filename=filename,
    )

    overlap_map.d_rast(map=overlap_raster)
    # overlap_map.d_shade(
    #     color=overlap_raster,
    #     shade=relief_map,
    #     brighten=30,
    #     overwrite=True,
    # )
    overlap_map.d_legend(
        # title=f"Percentage of Overlap",
        raster=overlap_raster,
        at=(5, 35, 84, 91),
        flags="b",
        fontsize=14,
    )
    overlap_map.d_barscale(at=(1, 5), flags="n")


def main():
    """Main function to run the watershed extent analysis."""
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

        threshold_str = threshold_label(BASIN_THRESHOLD)
        # print(gs.list_grouped(type="raster", pattern="basins*")[PROJECT_MAPSET])  # noqa: E501

        overlap_count, pct_overlap = watershed_extent_overlap()
        overlap_count_filename = (
            f"{output_dir}/{project_name}_basin_overlap.png"  # noqa: E501
        )
        pct_overlap_filename = (
            f"{output_dir}/{project_name}_basin_pct_overlap.png"  # noqa: E501
        )
        watershed_overlap_map(overlap_count, overlap_count_filename)
        watershed_overlap_map(pct_overlap, pct_overlap_filename)

        tmp_watershed_stats = []

        for res in SPATIAL_RESOLUTIONS:
            basins = f"basins{threshold_str}_{res}"
            # drain_dir = f"drain_dir{threshold_str}_{res}"
            # streams = f"streams{threshold_str}_{res}"
            print(f"Processing {project_name}: {basins}")
            if basin_exists(basins):
                print(f"Basin Exists: {basins}")
                # Set the computational region and calculate the basin stats
                gs.run_command("g.region", raster=basins, flags="a")
                basin_stats = watershed_extent_stats(basins)
                print(f"{basin_stats=}")
                for basin in basin_stats:
                    basin["resolution"] = res
                    basin["site"] = project_name
                    basin["threshold"] = BASIN_THRESHOLD
                tmp_watershed_stats.extend(basin_stats)

        # Write the watershed statistics to a file
        output_filename = f"{output_dir}/watershed_stats.json"
        with open(output_filename, "w") as f:
            json.dump(tmp_watershed_stats, f, indent=2)


if __name__ == "__main__":
    # Define the GRASS GIS database directory
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
