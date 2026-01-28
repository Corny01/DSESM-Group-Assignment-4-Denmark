import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

###########################################
# PATHS
###########################################

PP_PATH = "../Data/raw/powerplants/global_power_plant_database.csv"
REGIONS_Path = "../Data/processed/dk_regions_etr.geojson"

OUT_PATH = "../Data/processed/dk_powerplants_with_region.csv"

###########################################
# Load Data
###########################################

powerplants = pd.read_csv(PP_PATH)
powerplants = powerplants[powerplants["country"] == "DNK"].copy()
powerplants = powerplants[~powerplants["primary_fuel"].isin(["Solar", "Wind", "Geothermal"])].copy()

gdf_plants = gpd.GeoDataFrame(
    powerplants,
    geometry=[Point(xy) for xy in zip(powerplants["longitude"], powerplants["latitude"])],
    crs="EPSG:4326",
)
gdf_plants_etr = gdf_plants.to_crs(3035) #as regions are saved in EBSG3035

gdf_regions = gpd.read_file(REGIONS_Path)
gdf_regions = gdf_regions[["NAME_1", "geometry"]]

###########################################
# Join data of powerplants with the region they are located in
###########################################

pp_regions = gpd.sjoin(gdf_plants_etr, gdf_regions, how="left", predicate="within")
pp_regions = pp_regions[[
    "NAME_1",
    "name",
    "gppd_idnr",
    "capacity_mw",
    "primary_fuel"
]]
pp_regions["primary_fuel"] = pp_regions["primary_fuel"].str.lower()

###########################################
# Save data
###########################################

pp_regions.to_csv(OUT_PATH, index=False)