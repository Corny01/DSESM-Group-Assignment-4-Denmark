import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Pfade
PP_PATH = "../Data/raw/powerplants/global_power_plant_database.csv"
REGIONS_Path = "../Data/processed/dk_regions.geojson"
OUT_PATH = "../Data/processed/dk_powerplants_with_region.csv"

powerplants = pd.read_csv(PP_PATH)
powerplants = powerplants[powerplants["country"] == "DNK"].copy()
powerplants = powerplants[~powerplants["primary_fuel"].isin(["Solar", "Wind", "Geothermal"])].copy()

gdf_plants = gpd.GeoDataFrame(
    powerplants,
    geometry=[Point(xy) for xy in zip(powerplants["longitude"], powerplants["latitude"])],
    crs="EPSG:4326",
)

gdf_regions = gpd.read_file(REGIONS_Path)

# Annahme: Regionsname steht in der Spalte "region"
# (falls anders, einfach hier anpassen)
gdf_regions = gdf_regions[["NAME_1", "geometry"]]

# 5) Spatial Join: plant -> Region
pp_regions = gpd.sjoin(gdf_plants, gdf_regions, how="left", predicate="within")

pp_regions = pp_regions[[
    "NAME_1",
    "name",
    "gppd_idnr",
    "capacity_mw",
    "primary_fuel"
]]
pp_regions["primary_fuel"] = pp_regions["primary_fuel"].str.lower()

pp_regions.to_csv(OUT_PATH, index=False)
