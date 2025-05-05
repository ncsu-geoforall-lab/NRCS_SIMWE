#!/usr/bin/env python3

############################################################################
#
# MODULE:       soillib
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Soil property definitions and conversion factors
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import grass.script as gs


def region_to_wgs84_decimal_degrees_bbox():
    """convert region bbox to wgs84 decimal degrees bbox"""
    region = gs.parse_command("g.region", quiet=True, flags="ubg")
    bbox = [
        float(c)
        for c in [region["ll_w"], region["ll_s"], region["ll_e"], region["ll_n"]]
    ]
    return bbox


SOIL_PROPERTIES = {
    "bdod": {
        "description": "Bulk density of the fine earth fraction",
        "mapped_units": "cg/cm^3",
        "conversion_factor": 100,
        "conventional_units": "kg/dm^3",
    },
    "cec": {
        "description": "Cation Exchange Capacity of the soil",
        "mapped_units": "mmol(c)/kg",
        "conversion_factor": 10,
        "conventional_units": "cmol(c)/kg",
    },
    "cfvo": {
        "description": "Volumetric fraction of coarse fragments (> 2 mm)",
        "mapped_units": "cm^3/dm^3 (vol per mil)",
        "conversion_factor": 10,
        "conventional_units": "cm^3/100cm^3 (vol%)",
    },
    "clay": {
        "description": "Proportion of clay particles (< 0.002 mm) in the fine earth fraction",
        "mapped_units": "g/kg",
        "conversion_factor": 10,
        "conventional_units": "g/100g (%)",
    },
    "nitrogen": {
        "description": "Total nitrogen (N)",
        "mapped_units": "cg/kg",
        "conversion_factor": 100,
        "conventional_units": "g/kg",
    },
    "phh2o": {
        "description": "Soil pH",
        "mapped_units": "pH*10",
        "conversion_factor": 10,
        "conventional_units": "pH",
    },
    "sand": {
        "description": "Proportion of sand particles (> 0.05 mm) in the fine earth fraction",
        "mapped_units": "g/kg",
        "conversion_factor": 10,
        "conventional_units": "g/100g (%)",
    },
    "silt": {
        "description": "Proportion of silt particles (>= 0.002 mm and <= 0.05 mm) in the fine earth fraction",
        "mapped_units": "g/kg",
        "conversion_factor": 10,
        "conventional_units": "g/100g (%)",
    },
    "soc": {
        "description": "Soil organic carbon content in the fine earth fraction",
        "mapped_units": "dg/kg",
        "conversion_factor": 10,
        "conventional_units": "g/kg",
    },
    "ocd": {
        "description": "Organic carbon density",
        "mapped_units": "hg/m^3",
        "conversion_factor": 10,
        "conventional_units": "kg/m^3",
    },
    "ocs": {
        "description": "Organic carbon stocks (0-30cm depth interval only)",
        "mapped_units": "t/ha",
        "conversion_factor": 10,
        "conventional_units": "kg/m^2",
    },
    "wv0010": {
        "description": "Volumetric Water Content at 10kPa",
        "mapped_units": "0.1 v% or 1 mm/m",
        "conversion_factor": 10,
        "conventional_units": "volume (%)",
    },
    "wv0033": {
        "description": "Volumetric Water Content at 33kPa",
        "mapped_units": "0.1 v% or 1 mm/m",
        "conversion_factor": 10,
        "conventional_units": "volume (%)",
    },
    "wv1500": {
        "description": "Volumetric Water Content at 1500kPa",
        "mapped_units": "0.1 v% or 1 mm/m",
        "conversion_factor": 10,
        "conventional_units": "volume (%)",
    },
}
