import atlite
import pypsa
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from urllib.request import urlretrieve
import xarray as xr
import logging
from atlite.gis import ExclusionContainer

###########################################
# INPUTolygone zu einer MultiGeometry zusammenfassen (reduziert overlay-komplexität stark
###########################################
year = 2013
buffer = 0.25
capa_density = 3 #density of power in MW per square kilometer

REGION_COL = "NAME_1"
turbine_on = "Vestas_V112_3MW"
turbine_off = "NREL_ReferenceTurbine_5MW_offshore"
panel = "CdTe"
orientation = "latitude_optimal"

###########################################
# PATHS
###########################################

REGIONS_PATH = "../Data/processed/dk_regions_etr.geojson"
EEZ_PATH = "../Data/processed/dk_eez_by_region_etr.geojson"
AVAIL_PV_PATH = "../Data/processed/eligibility/eligible_pv_areas_DK.gpkg"
AVAIL_ON_PATH = "../Data/processed/eligibility/eligible_wind_on_areas_DK.gpkg"
AVAIL_OFF_PATH = "../Data/processed/eligibility/eligible_wind_off_areas_DK.gpkg"

###########################################
# Loading and preprocessing of data
###########################################

regions = gpd.read_file(REGIONS_PATH).to_crs(4326)
eez_regions = gpd.read_file(EEZ_PATH).to_crs(4326)

avail_pv = gpd.read_file(AVAIL_PV_PATH).to_crs(4326)
avail_on = gpd.read_file(AVAIL_ON_PATH).to_crs(4326)
avail_off = gpd.read_file(AVAIL_OFF_PATH).to_crs(4326)

###########################################
# Cutout erstellen
###########################################

#set boundaries for cutout
minx1, miny1, maxx1, maxy1 = regions.total_bounds
minx2, miny2, maxx2, maxy2 = eez_regions.total_bounds

minx, miny = min(minx1, minx2), min(miny1, miny2)
maxx, maxy = max(maxx1, maxx2), max(maxy1, maxy2)

#set timeseries
time = slice(f"{year}-01-01", f"{year+1}-01-01")

#cutout whole area
cutout = atlite.Cutout(
    path=f"era5-{year}-DK.nc",
    module="era5",
    x=slice(minx - buffer, maxx + buffer),
    y=slice(miny - buffer, maxy + buffer),
    time=time,
)
cutout.prepare(features=["wind", "influx", "temperature"])

###########################################
# Availibility matrices
###########################################

dummy_excluder = ExclusionContainer(crs=3035, res=100)

#PV
inter_pv = gpd.overlay(
    regions[[REGION_COL, "geometry"]].reset_index(drop=True),
    avail_pv[["geometry"]],
    how="intersection",
    keep_geom_type=True,
)
inter_pv = inter_pv.dissolve(by=REGION_COL)
shapes_pv = inter_pv.geometry
A_pv = cutout.availabilitymatrix(shapes_pv, excluder=dummy_excluder)

#Onshore wind
inter_on = gpd.overlay(
    regions[[REGION_COL, "geometry"]].reset_index(drop=True),
    avail_on[["geometry"]],
    how="intersection",
    keep_geom_type=True,
)
inter_on = inter_on.dissolve(by=REGION_COL)
shapes_on = inter_on.geometry
A_on = cutout.availabilitymatrix(shapes_on, excluder=dummy_excluder)

#Offshore wind
inter_off = gpd.overlay(
    eez_regions[[REGION_COL, "geometry"]].reset_index(drop=True),
    avail_off[["geometry"]],
    how="intersection",
    keep_geom_type=True,
)
inter_off = inter_off.dissolve(by=REGION_COL)
shapes_off = inter_off.geometry
A_off = cutout.availabilitymatrix(shapes_off, excluder=dummy_excluder)

###########################################
# Calculate maximum capacities per technology and region
###########################################

area = cutout.grid.set_index(["y", "x"]).to_crs(3035).area / 1e6  # km^2
area = xr.DataArray(area, dims=("spatial",))

capacity_on = A_on.stack(spatial=["y", "x"]) * area * capa_density
cap_on_total = capacity_on.sum("spatial")  # MW pro Region

capacity_pv = A_pv.stack(spatial=["y", "x"]) * area * capa_density
cap_pv_total = capacity_pv.sum("spatial")  # MW pro Region

capacity_off = A_off.stack(spatial=["y", "x"]) * area * capa_density
cap_off_total = capacity_off.sum("spatial")  # MW pro Region
print(cap_pv_total)
print(cap_on_total)
print(cap_off_total)
"""
layout_on = A_on * area_km2 * capa_density
layout_pv = A_pv * area_km2 * capa_density
layout_off = A_off * area_km2 * capa_density

cap_on_mw = layout_on.sum("spatial")
cap_pv_mw = layout_pv.sum("spatial")
cap_off_mw = layout_off.sum("spatial")
print(cap_on_mw, cap_pv_mw, cap_off_mw)

gen_on = cutout.wind(turbine=turbine_on,  layout=layout_on)
gen_off = cutout.wind(turbine=turbine_off, layout=layout_off)
gen_pv = cutout.pv(panel=panel, orientation=orientation, layout=layout_pv)

# CF; Regionen mit cap=0 geben NaN (sauberer als 0/0)
cf_on = gen_on / cap_on_mw
cf_off = gen_off / cap_off_mw
cf_pv = gen_pv / cap_pv_mw
"""