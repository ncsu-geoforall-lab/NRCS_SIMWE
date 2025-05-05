#!/usr/bin/env python3

############################################################################
#
# MODULE:       v.in.sda.soils
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Get Spatial Data from Soil Data Access
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

# module
# description: Import SSURGO spatial features from Soil Data Access (SDA)
# keyword: vector
# keyword: import
# keyword: soils
# keyword: SSURGO
# end

# option G_OPT_V_OUTPUT
# description: Output vector map name
# end

# option
# key: where
# type: string
# description: SQL WHERE clause for SDA query (e.g. areasymbol = 'NC001')
# required: no
# guisection: Query
# end

# option
# key: bbox
# type: string
# description: Bounding box for spatial query (xmin,ymin,xmax,ymax)
# required: no
# guisection: Query
# end

# option
# key: format
# type: string
# options: geojson, gml
# description: Output format for SDA data (GeoJSON or GML)
# answer: geojson
# required: no
# guisection: Output
# end


import tempfile
import requests
import grass.script as gs


def build_query_url(where=None, bbox=None, fmt="geojson"):
    base_url = "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest"
    if bbox:
        xmin, ymin, xmax, ymax = bbox.split(",")
        sql = f"""
        SELECT mupolygon.mupolygonkey, mupolygon.areasymbol, mupolygon.musym, mupolygon.muname, mupolygon.geom
        FROM mupolygon
        WHERE mupolygon.geom.STIntersects(
            geometry::STGeomFromText(
                'POLYGON(({xmin} {ymin}, {xmin} {ymax}, {xmax} {ymax}, {xmax} {ymin}, {xmin} {ymin}))', 4326
            )
        ) = 1
        """
    elif where:
        sql = f"""
        SELECT mupolygon.mupolygonkey, mupolygon.areasymbol, mupolygon.musym, mupolygon.muname, mupolygon.geom
        FROM mupolygon
        WHERE {where}
        """
    else:
        gs.fatal("You must specify either a SQL WHERE clause or a bounding box.")

    return base_url, sql


def fetch_sda_geojson(sql):
    headers = {"Content-Type": "application/json"}
    payload = {"query": sql, "format": "geojson"}
    r = requests.post(
        "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest",
        json=payload,
        headers=headers,
    )
    r.raise_for_status()
    return r.text


def write_tempfile(content):
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".geojson", mode="w")
    tmpfile.write(content)
    tmpfile.close()
    return tmpfile.name


def main():
    output = options["output"]
    where = options["where"]
    bbox = options["bbox"]
    fmt = options["format"]

    base_url, sql = build_query_url(where=where, bbox=bbox, fmt=fmt)

    gs.message("Querying SDA...")
    geojson = fetch_sda_geojson(sql)
    gs.message("SDA query successful, importing...")

    geojson_file = write_tempfile(geojson)

    gs.run_command("v.import", input=geojson_file, output=output, overwrite=True)

    gs.message(f"SSURGO data imported to vector map <{output}>")


if __name__ == "__main__":
    options, flags = gs.parser()
    main()
