import atlite
import pypsa
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from urllib.request import urlretrieve

year = 2013

REGIONS_PATH = "../Data/processed/dk_regions_etr.geojson"
EEZ_PATH = "../Data/processed/dk_eez_by_region_etr.geojson"

regions = gpd.read_file(REGIONS_PATH).to_crs(4326)
eez_regions = gpd.read_file(EEZ_PATH).to_crs(4326)

REGION_COL = "region_id"   # <- anpassen
TURBINE_ON  = "Vestas_V112_3MW"   # <- anpassen (atlite Turbinen-Config Name)
TURBINE_OFF = "NREL_ReferenceTurbine_5MW_offshore"   # <- anpassen
PANEL = "CdTe"                     # Standard-Panel config in atlite
ORIENTATION = "latitude_optimal"  # Standard in atlite

minx, miny, maxx, maxy = eez_regions.total_bounds
buffer = 0.25
time = slice(f"{year}-01-01", f"{year+1}-01-01")

cutout = atlite.Cutout(
    path=f"era5-{year}-DK.nc",
    module="era5",
    x=slice(minx - buffer, maxx + buffer),
    y=slice(miny - buffer, maxy + buffer),
    time=time,
)

# Für Wind + PV reicht i.d.R.:
cutout.prepare(features=["wind", "influx", "temperature"])

# --- 1) Layout: flächengewichtete CFs ---
# uniform_density_layout => gleiche installierte Leistung pro Fläche (z.B. 1 MW/km²)
layout = cutout.uniform_density_layout(3.0)

# --- 2) Capacity factor time series pro Region (per_unit=True) ---
# shapes=... baut intern eine indicatormatrix/Flächenanteile je Rasterzelle. :contentReference[oaicite:4]{index=4}
cf_wind_on_ts  = cutout.wind(
    turbine=TURBINE_ON,
    shapes=regions,
    layout=layout,
    per_unit=True,
)

cf_wind_off_ts = cutout.wind(
    turbine=TURBINE_OFF,
    shapes=eez_regions,
    layout=layout,
    per_unit=True,
)

cf_pv_ts = cutout.pv(
    panel=PANEL,
    orientation=ORIENTATION,
    shapes=regions,     # PV typischerweise onshore; falls du PV-offshore willst: eez_shapes
    layout=layout,
    per_unit=True,
)

# --- 3) Jahresmittelwert (Capacity Factor) je Region ---
# Ergebnis: pandas Series je Technologie mit Index=Regionen
cf_wind_on = cf_wind_on_ts.mean("time").to_pandas()
cf_wind_off = cf_wind_off_ts.mean("time").to_pandas()
cf_pv = cf_pv_ts.mean("time").to_pandas()

# --- 4) In ein gemeinsames DataFrame bringen ---
# Land- und EEZ-Indizes können unterschiedlich sein -> Outer Join
df = pd.DataFrame(index=cf_wind_on.index.union(cf_wind_off.index).union(cf_pv.index))
df["wind_onshore_cf"] = cf_wind_on
df["wind_offshore_cf"] = cf_wind_off
df["pv_cf"] = cf_pv
df["year"] = year

# Optional: schöner sortieren
df = df.reset_index().rename(columns={"index": REGION_COL}).sort_values([REGION_COL])

# --- 5) CSV speichern ---
out_csv = f"capacity_factors_{year}.csv"
df.to_csv(out_csv, index=False)
print("Wrote:", out_csv)