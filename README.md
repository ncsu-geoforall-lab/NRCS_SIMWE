# NRCS_SIMWE

## Purpose

The purpose of this agreement, between the U.S. Department of Agriculture, Natural Resources Conservation Service (NRCS) and North Carolina State University (Recipient), is to adapt the SIMulation of Water and Erosion (SIMWE) model for the integration of Dynamic Soil Survey data. Proposed work will expand model capabilities, add supporting modules, and incorporate data input flexibility for integrating soil survey data. The updated model will serve as an important component of the future Dynamic Soil Survey at field to watershed scales and minute to monthly time-steps.

## Objectives

- [WIP] Develop pre-processing modules to translate basic soil properties and site conditions into model input parameters.
- [WIP] Perform a sensitivity analysis to identify optimal ranges of and interactions between model input parameters.
- [ ] Explore the capability of the model to accept and utilize time-varying inputs.
- [ ] Expand model capabilities to include multiple and consecutive rainfall events and account for antecedent conditions.
- [ ] Develop multilayer SIMWE model simulations that account for multiple subsurface soil layers.

## Sites

### Clay Center

![claycenter3d](output/clay-center/elevation_3dmap.png)

- [x] Create site projects in GRASS GIS
- [x] Run basic SIMWE simulation

Report: [output/clay-center/report.md](output/clay-center/report.md)

### Coweeta

![coweeta3d](output/coweeta/elevation_3dmap.png)

- [X] Create site projects in GRASS GIS
- [x] Run basic SIMWE simulation

Report: [output/coweeta/report.md](output/coweeta/report.md)

### SFREC

![sfrec3d](output/SFREC/elevation_3dmap.png)

- [X] Create site projects in GRASS GIS
- [x] Run basic SIMWE simulation

Report: [output/SFREC/report.md](output/SFREC/report.md)

### SJER

![sjer3d](output/SJER/elevation_3dmap.png)

- [X] Create site projects in GRASS GIS
- [x] Run basic SIMWE simulation

Report: [output/SJER/report.md](output/SJER/report.md)

### tx069-playas

![tx0693d](output/tx069-playas/elevation_3dmap.png)

- [X] Create site projects in GRASS GIS
- [x] Run basic SIMWE simulation

Report: [output/tx069-playas/report.md](output/tx069-playas/report.md)

## Basic Model Simulations Comparison

![basic_simwe](notebooks/output/depth_fig.png)

## Data

### Shared Goolge Drive

[NRCS_SIMWE/site_data_workflows](https://drive.google.com/drive/folders/1VsauKpPnaPhKcRUykEgmGN7045xuhFu_?usp=drive_link)

## Getting Started

### Set up your Python environment

```bash
# create a virtual environment
$ python3 -m venv venv
# activate the virtual environment
$ source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Install Pre-commit

```bash
# Install pre-commit
(venv) $ pip install pre-commit
# Run pre-commit install to setup the git hook scripts
(venv) $ pre-commit install
```

## Project Setup

1. Create Site Projects in GRASS

    Run the python script `scripts/create_locations.py` to create site projects in GRASS GIS.

    ```bash
    python scripts/create_locations.py
    ```

2. Download Data

    Run the python script `scripts/download_data.py` to download data for the site projects.

    ```bash
    python scripts/download_data.py
    ```

3. Calcuate 1st and 2nd order derivatives

    Run the python script `scripts/geomorphology.py` to calculate 1st and 2nd order derivatives.

    ```bash
    python scripts/calculate_derivatives.py
    ```

## Simulations

Run the python script `scripts/simulation.py` to downlaod data and run the SIMWE model.

```bash
python scripts/simulation.py
```

### Sensitivity Analysis

Run the python script `scripts/sensitivity.py` to perform a sensitivity analysis.

```bash
python scripts/sensitivity.py
```

## Acknowledgements

This project is supported by the U.S. Department of Agriculture, Natural Resources Conservation Service (NRCS) and North Carolina State University.

## Contributors

- Helena Mitasova (North Carolina State University)
- Corey T. White (North Carolina State University)
- Add your name here
