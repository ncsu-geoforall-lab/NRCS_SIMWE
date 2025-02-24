#!/usr/bin/env python3

############################################################################
#
# MODULE:        gutiles.py
# AUTHOR:       Corey T. White
# PURPOSE:      Utility functions for GRASS GIS
# COPYRIGHT:    (C) 2025 OpenPlains Inc. and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import grass.script as gs
import grass.script.core as gcore


def calculate_memory_per_process(max_nprocs=None, reserved_ram=1024):
    """
    Calculate memory allocated per process based on total system RAM,
    the amount reserved for system stability, and the number of
    available CPU cores.

    Parameters:
    - max_nprocs (int, optional): Maximum number of processes to allow.
    - reserved_ram (int): Amount of RAM in MB to reserve for the system.
        Default is 1024 MB (1 GB).

    Returns:
    - memory_per_process (int): Allocated memory per process in MB.
    """
    import psutil
    import os

    # Get total system RAM in MB
    total_ram_mb = psutil.virtual_memory().total / (1024**2)

    # Calculate memory available for allocation, subtracting reserved RAM
    memory_to_allocate = total_ram_mb - reserved_ram

    # Get the number of CPU cores available to the process,
    # minus one for system stability
    total_processes = max(1, len(os.sched_getaffinity(0)) - 1)

    # Check that the total number of processes does not
    # exceed user specified amount
    if max_nprocs and isinstance(max_nprocs, int):
        total_processes = min(total_processes, max_nprocs)

    # Calculate memory per process using integer division
    memory_per_process = memory_to_allocate // total_processes

    return total_processes, memory_per_process


def check_addon_installed(addon: str, fatal=True) -> bool:
    """Check if a GRASS GIS addon is installed"""
    if not gcore.find_program(addon, "--help"):
        call = gcore.fatal if fatal else gcore.warning
        call(
            _(  # noqa: F821
                "Addon {a} is not installed. Please install it using g.extension."  # noqa: E501
            ).format(a=addon)
        )
        return False
    return True


def install_addons(addons_file: str) -> None:
    """
    Install GRASS GIS addons from a list of addon names.

    Parameters:
    - addons_file (str): File containing a list of addon names.

        t.stac
        r.mapcalc.tiled
        r.tri
    """

    try:
        with open(addons_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if check_addon_installed(line, fatal=False):
                    print(f"Addon {line} is already installed.")
                    continue

                print(f"Installing: {line}")
                try:
                    gs.run_command(
                        "g.extension", extension=line, operation="add"
                    )  # noqa: E501
                except Exception as e:
                    print(f"Error installing addon {line}: {e}")

    except Exception as e:
        print(f"Error reading addons file: {e}")
