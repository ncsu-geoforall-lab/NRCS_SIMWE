# GRASS GIS instructions

These instructions apply when adding, modifying, or explaining GRASS GIS
workflows in this repo (Python scripts, GRASS addons under `tools/`, and
documentation that references GRASS commands).

## Source of truth (use these first)

- `README.md`
  - High-level workflows and the expected script entry points.
- `site-CRS-info.txt`
  - Authoritative list of site names, EPSG codes, and default resolutions.
- `scripts/*.py`
  - Primary automation for creating locations, downloading data, and running
    simulations.
- `addons.txt`
  - List of required GRASS addons used by scripts.
- `tools/`
  - GRASS addon modules maintained in this repo (e.g., `g.ssurgo.query`).

If the repo scripts disagree with general GRASS examples found online, prefer
the patterns already used in `scripts/` and `tools/`.

## Environment assumptions

- GRASS GIS must be installed and available as the `grass` executable.
- Most scripts expect the GRASS database at `$HOME/grassdata`.
- Locations are created from EPSG codes listed in `site-CRS-info.txt`.

## Working with GRASS in Python (repo conventions)

When writing or modifying Python scripts that call GRASS:

1. Ensure the GRASS Python path is added before importing `grass.script`.
   This repo commonly uses:

   ```bash
   grass --config python_path
   ```

2. Use `grass.script` as `gs`, and initialize a session with `gs.setup.init`.
3. Prefer `gs.run_command` for commands and `gs.read_command` / `gs.parse_command`
   when you need output.
4. Always set the computational region (`g.region`) before raster work.
5. Use `overwrite=True` only when intentional; respect `gs.overwrite()` in
   addon modules.

## Locations, mapsets, and naming

- Locations are created by `scripts/create_locations.py` from EPSG codes.
- Scripts commonly run in `PERMANENT` or a named mapset (e.g., `basic60`).
- Keep raster/vector names stable if downstream code expects them.
  Examples used in this repo include: `elevation`, `dx`, `dy`, `depth`,
  `disch`, and SSURGO rasters such as `ssurgo_mukey`.

## What not to do

- Do not assume a GRASS session exists in a plain Python process.
- Do not import `grass.script` before adding the GRASS python path.
- Do not change site names, EPSG codes, or default resolutions without also

  updating `site-CRS-info.txt` and any dependent docs/scripts.
