#!/usr/bin/env python3

import os
import sys
import subprocess
import matplotlib.pyplot as plt
from PIL import Image


BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"
PROJECT_MAPSET = "basic"
SITE_PARAMS = [
    {"site": "clay-center", "crs": "32614", "res": "3", "naip": 2021},
    {"site": "coweeta", "crs": "26917", "res": "10", "naip": 2022},
    {"site": "SFREC", "crs": "26910", "res": "1", "naip": 2022},
    {"site": "SJER", "crs": "26911", "res": "1", "naip": 2022},
    {"site": "tx069-playas", "crs": "32613", "res": "8", "naip": 2022},
]
OUTPUT_DIR = "output"


# Define main function
def main():
    overview_plot_params = []
    for params in SITE_PARAMS:
        site = params["site"]
        gs.setup.init(gisdb, site, PROJECT_MAPSET)
        print(f"Processing site: {site}")
        output_dir = os.path.join(OUTPUT_DIR, site)
        if not os.path.exists(output_dir):
            os.makedirs(os.path.join(OUTPUT_DIR, site))

        elevation_fig_params = create_elevation_fig(params, output_dir)
        overview_plot_params.append(elevation_fig_params)

        elev_hist_fig_params = create_elevation_hist_fig(params, output_dir)
        overview_plot_params.append(elev_hist_fig_params)

        slope_fig_params = create_slope_fig(params, output_dir)
        overview_plot_params.append(slope_fig_params)

        aspect_fig_params = create_aspect_fig(params, output_dir)
        overview_plot_params.append(aspect_fig_params)

        geomorphon_fig_params = create_geomorphon_fig(params, output_dir)
        overview_plot_params.append(geomorphon_fig_params)

        tcurv_fig_params = create_tcurv_fig(params, output_dir)
        overview_plot_params.append(tcurv_fig_params)

        pcurv_fig_params = create_pcurv_fig(params, output_dir)
        overview_plot_params.append(pcurv_fig_params)

        naip_fig_params = create_naip_fig(params, output_dir)
        overview_plot_params.append(naip_fig_params)

        ndvi_fig_params = create_ndvi_fig(params, output_dir)
        overview_plot_params.append(ndvi_fig_params)

        ssurgo_mukey_fig_params = create_ssurgo_mukey(params, output_dir)
        overview_plot_params.append(ssurgo_mukey_fig_params)

    output_fig = os.path.join(OUTPUT_DIR, "sites_elevation_fig3.png")
    generate_plots(5, 10, overview_plot_params, output_fig)

    # create_model_run("basic", "depth", True)
    create_model_run("basic", "disch")


def create_elevation_fig(site_params, output_dir):
    """Create the elevation figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Elevation"
    out_file = os.path.join(output_dir, "elev.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_shade(color="elevation", shade="hillshade")
    dem_map.d_legend(
        raster="elevation", at=(5, 50, 5, 9), flags="b", units="m"
    )  # noqa: E501
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    elevation = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return elevation


def create_elevation_hist_fig(site_params, output_dir):
    """Create the elevation histogram figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Elevation histogram"
    out_file = os.path.join(output_dir, "elev_hist.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_histogram(map="elevation")
    dem_map.show()
    elevation = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return elevation


def create_geomorphon_fig(site_params, output_dir):
    """Create the elevation figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Geomorphon"
    out_file = os.path.join(output_dir, "geomorphon.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_shade(color="geomorphon", shade="hillshade")
    dem_map.d_legend(raster="geomorphon", at=(5, 50, 5, 9), flags="b")
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    elevation = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return elevation


def create_tcurv_fig(site_params, output_dir):
    """Create the tcurv figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Profile curvature"
    out_file = os.path.join(output_dir, "tcurv.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_shade(color="tcurv", shade="hillshade")
    dem_map.d_legend(raster="tcurv", at=(5, 50, 5, 9), flags="b")
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    elevation = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return elevation


def create_pcurv_fig(site_params, output_dir):
    """Create the tcurv figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Planform curvature"
    out_file = os.path.join(output_dir, "pcurv.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_shade(color="pcurv", shade="hillshade")
    dem_map.d_legend(raster="pcurv", at=(5, 50, 5, 9), flags="b")
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    elevation = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return elevation


def create_slope_fig(site_params, output_dir):
    """Create the slope figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Slope"
    out_file = os.path.join(output_dir, "slope.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_rast(map="slope")
    dem_map.d_legend(raster="slope", at=(5, 50, 5, 9), flags="b", units="m")
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    output = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return output


def create_aspect_fig(site_params, output_dir):
    """Create the aspect figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "Aspect"
    out_file = os.path.join(output_dir, "aspect.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_rast(map="aspect")
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    output = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return output


def create_naip_fig(site_params, output_dir):
    """Create the naip figure"""
    site = site_params["site"]
    res = site_params["res"]
    naip_year = site_params["naip"]
    map_name = f"NAIP - {naip_year}"
    out_file = os.path.join(output_dir, "naip.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    # dem_map.d_shade(color=f"naip_{naip_year}_rgb@naip", shade="aspect")
    dem_map.d_rast(map=f"naip_{naip_year}_rgb@naip")
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    output = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return output


def create_ssurgo_mukey(site_params, output_dir):
    """Create the ssurgo mukey figure"""
    site = site_params["site"]
    res = site_params["res"]
    map_name = "SSURGO MUKEY"
    out_file = os.path.join(output_dir, "mukey.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_shade(color="ssurgo_mukey", shade="hillshade")
    dem_map.d_barscale(at=(35, 7), flags="n")
    dem_map.show()
    output = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}m",
    }  # noqa: E501
    return output


def create_ndvi_fig(site_params, output_dir):
    site = site_params["site"]
    res = site_params["res"]
    naip_year = site_params["naip"]
    map_name = f"NDVI - {naip_year}"
    ndvi = f"naip_{naip_year}_ndvi"
    gs.run_command("g.region", raster=f"naip_{naip_year}_rgb@naip")
    gs.run_command(
        "i.vi",
        viname="ndvi",
        red=f"naip_{naip_year}.red@naip",
        nir=f"naip_{naip_year}.nir@naip",
        output=ndvi,
        overwrite=True,
    )

    gs.run_command("r.colors", map=ndvi, color="ndvi")

    gs.run_command("g.region", raster="elevation")

    out_file = os.path.join(output_dir, "ndvi.png")
    dem_map = gj.Map(use_region=True, height=600, width=600, filename=out_file)
    dem_map.d_shade(color=ndvi, shade="hillshade")
    # dem_map.d_rast(map=ndvi)
    dem_map.d_barscale(at=(5, 7), flags="n")
    dem_map.show()
    output = {
        "filename": out_file,
        "rast_map": map_name,
        "title": f"{site} {res}",
    }  # noqa: E501
    return output


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
    plt.show()


def create_model_run(mapset="basic", simtype="depth", gif=False):
    sim_plot_params = []
    sim_values = [str(i).zfill(2) for i in range(2, 11, 2)]
    for site_param in SITE_PARAMS:
        site = site_param["site"]
        output_dir = os.path.join(OUTPUT_DIR, site, mapset)
        if not os.path.exists(output_dir):
            os.makedirs(os.path.join(OUTPUT_DIR, site, mapset))
        out_file = os.path.join(output_dir, f"{simtype}_simulation.png")

        for i in sim_values:
            map_name = f"{simtype}.{i}"
            filename = os.path.join(output_dir, f"{simtype}_{i}.png")
            gj.init(gisdb, site, mapset)
            map_obj = gj.Map(
                filename=filename, use_region=True, height=600, width=600
            )  # noqa: E501
            # map_obj.d_rast(map=map_name)
            map_obj.d_shade(color=map_name, shade="hillshade")
            map_obj.d_legend(raster=map_name, at=(5, 50, 5, 9), flags="b")
            map_obj.d_barscale(at=(35, 7), flags="n")
            map_obj.show()
            title = "Depth (m)" if simtype == "depth" else "Discharge (m3/s)"
            output_params = {
                "filename": filename,
                "title": f"{site} {title}",
                "rast_map": f"{i} minutes",
            }
            sim_plot_params.append(output_params)

        # Create GIF
        if gif:
            depth_sum_ts_map = gj.TimeSeriesMap(
                height=600, width=600, use_region=True
            )  # noqa: E501
            depth_sum_ts_map.add_raster_series("depth_sum")
            depth_sum_ts_map.d_legend()
            depth_sum_ts_map.render()
            out_file = os.path.join(output_dir, f"{simtype}_simulation.gif")
            depth_sum_ts_map.save(out_file)

    generate_plots(5, 5, sim_plot_params, out_file)


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
    import grass.jupyter as gj

    # Execute the main function
    sys.exit(main())
