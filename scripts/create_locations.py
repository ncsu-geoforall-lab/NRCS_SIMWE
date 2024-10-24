import os
import subprocess

BASE_URL = "https://github.com/ncss-tech/SIMWE-coordination/raw/main/sites/"
# Extract the location name and PROJCRS from the data
location_name = None
projcrs = None
gisdb = os.path.join(os.getenv("HOME"), "grassdata")
print(f"GISDBASE: {gisdb}")

with open("site-CRS-info.txt", "r") as file:
    data = file.readlines()
    for line in data:

        location_name, projcrs = line.split(":")

        # Check if location name and PROJCRS were found
        if location_name is None:
            print("Location name not found in the data")
            exit(1)

        if projcrs is None:
            print("CRS: Not found")
            exit(1)

        # Create the GRASS GIS location
        grass_command = f"grass -c EPSG:{projcrs.strip()} '{gisdb}/{location_name}' -e"  # noqa: E501
        print(f"Creating location: {grass_command}")
        process = subprocess.Popen(
            grass_command, shell=True, stdout=subprocess.PIPE
        )  # noqa: E501
        process.wait()
