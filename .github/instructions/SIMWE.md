# SIMWE instructions

These instructions apply when working on SIMWE-related scripts, model
assumptions, parameterization, sensitivity analysis, or documentation for this
repo.

## Source of truth (use these first)

- `README.md`
  - Project purpose and the intended end-to-end workflow.
- `site-CRS-info.txt`
  - Authoritative list of sites and their CRS/resolution settings.
- `scripts/simulation.py`
  - Baseline SIMWE run pattern for this repo.
- `scripts/sensitivity.py`
  - Sensitivity-analysis workflow and conventions for outputs.
- `scripts/download_data.py`
  - How elevation and SSURGO MUKEY rasters are imported.
- `scripts/geomorphology.py`
  - How derivatives and terrain products are computed.

## Model and units (do not guess)

When describing or modifying SIMWE parameters, keep units explicit:

- `r.sim.water` inputs in `scripts/simulation.py` use:
  - `rain_value`: mm/hr
  - `infil_value`: mm/hr
  - `man_value`: Manning's n (unitless)
  - `niterations`: minutes (event duration)
  - `output_step`: minutes
  - `depth`: meters
  - `discharge`: m^3/s

If you are unsure about a unit, confirm via GRASS module docs and/or existing
repo usage before editing.

## Workflow expectations (repo)

The typical sequence for a site is:

1. Create GRASS locations from `site-CRS-info.txt` using
   `scripts/create_locations.py`.
1. Download and import data using `scripts/download_data.py`.
1. Compute geomorphology products using `scripts/geomorphology.py`.
1. Run SIMWE using `scripts/simulation.py`.
1. Optional: run sensitivity workflows using `scripts/sensitivity.py`.

If you change any step outputs or naming conventions, update downstream scripts
that assume those names.

## Output conventions (do not break)

The baseline simulation script typically:

- Sets region from `elevation`.
- Produces derivatives `dx` and `dy`.
- Produces time-stepped outputs `depth.*` and `disch.*`.
- Registers outputs into space-time raster datasets (STRDS):
  - `depth_sum`
  - `disch_sum`

Avoid changing these names unless you also update any consumers.

## What not to do

- Do not change scientific defaults (rain, infiltration, Manning's n, random
  seed) without stating why and what analysis depends on the change.
- Do not present results as calibrated or validated unless the repo provides
  evidence and methods.
