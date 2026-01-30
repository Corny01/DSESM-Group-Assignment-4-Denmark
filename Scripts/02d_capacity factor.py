import atlite
import geopandas as gpd
import pandas as pd
import xarray as xr
from atlite.gis import ExclusionContainer

###########################################
# INPUT
###########################################
year = 2018
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

MAX_OUT = f"../Data/processed/dk_re_max_potentials_by_region_{year}.csv"
CF_OUT = f"../Data/processed/dk_re_cf_timeseries_{year}.csv"

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
time = slice(f"{year}-01-01", f"{year}-12-31") #f"{year+1}-01-01

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

capacity_pv = A_pv.stack(spatial=["y", "x"]) * area * capa_density
cap_pv_total = capacity_pv.sum("spatial")  # MW pre region

capacity_on = A_on.stack(spatial=["y", "x"]) * area * capa_density
cap_on_total = capacity_on.sum("spatial")  # MW # MW pre region

capacity_off = A_off.stack(spatial=["y", "x"]) * area * capa_density
cap_off_total = capacity_off.sum("spatial")  # MW # MW pre region

gen_pv = cutout.pv(matrix=capacity_pv, panel=panel, orientation=orientation,  index=inter_pv.index)
gen_on = cutout.wind(matrix=capacity_on, turbine=turbine_on,  index=inter_on.index)
gen_off = cutout.wind(matrix=capacity_off, turbine=turbine_off,  index=inter_off.index)

cf_pv = gen_pv / cap_pv_total
cf_on = gen_on / cap_on_total
cf_off = gen_off / cap_off_total

###########################################
# Save calculations in csv files
###########################################

#max capacities per region
s_on = cap_on_total.to_pandas()
s_off = cap_off_total.to_pandas()
s_pv = cap_pv_total.to_pandas()

df_pot = pd.DataFrame(index=s_pv.index)
df_pot.index.name = "region"
df_pot["onshore_potential_MW"] = s_on
df_pot["offshore_potential_MW"] = s_off
df_pot["solar_potential_MW"] = s_pv
df_pot = df_pot.reset_index()

df_pot.to_csv(MAX_OUT, index=False)
print("Wrote:", f"region_potentials_{year}.csv")

#capacity factor timeseries
df_cf_on = cf_on.to_pandas()
df_cf_off = cf_off.to_pandas()
df_cf_pv = cf_pv.to_pandas()

df_ts_on = df_cf_on.stack(dropna=False).reset_index()
df_ts_on.columns = ["timestamp", "region", "cf_onshore"]

df_ts_off = df_cf_off.stack(dropna=False).reset_index()
df_ts_off.columns = ["timestamp", "region", "cf_offshore"]

df_ts_pv = df_cf_pv.stack(dropna=False).reset_index()
df_ts_pv.columns = ["timestamp", "region", "cf_pv"]

df_ts = df_ts_pv.merge(df_ts_on, on=["timestamp", "region"], how="outer")
df_ts = df_ts.merge(df_ts_off, on=["timestamp", "region"], how="outer")
df_ts = df_ts.sort_values(["timestamp", "region"]).reset_index(drop=True)

df_ts.to_csv(CF_OUT, index=False)
print("Wrote:", f"capacity_factor_timeseries_{year}.csv")