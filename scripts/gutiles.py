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
