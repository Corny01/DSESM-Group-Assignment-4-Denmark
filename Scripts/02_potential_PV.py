import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from atlite.gis import ExclusionContainer, shape_availability
from rasterio.plot import show

#paths
DK_PATH = "../Data/processed/dk_regions.geojson"
LC_PATH = "../Data/raw/copernicus/PROBAV_LC100_global_v3.0.1_2019-nrt_Discrete-Classification-map_EPSG-4326-DK.tif"
PA_PATH = "../Data/raw/wdpa/WDPA_Oct2022_Public_shp-DNK.tif"

output_path = "../plots_and_figures/eligible_pv_areas_DK.png"

#define excluder and shape
excluder = ExclusionContainer(crs=3035, res=100)
DK = gpd.read_file(DK_PATH)
DK_shape = DK.to_crs(excluder.crs).geometry

#excluding raster data
codes_to_exclude = [111, 113, 112, 114, 115, 116, 121, 123, 122, 125, 126, 70, 80, 200]
excluder.add_raster(LC_PATH, codes=codes_to_exclude, crs=3035, buffer=0, nodata=48)
excluder.add_raster(PA_PATH)

#
band, transform = shape_availability(DK_shape, excluder)

#figure
fig, ax = plt.subplots(figsize=(4, 8))
DK_shape.plot(ax=ax, color="none")
show(band, transform=transform, cmap="Greens", ax=ax);
ax.set_title("Eligible PV Energy Areas in Denmark")
ax.set_xlabel("Easting (m) – EPSG:3035")
ax.set_ylabel("Northing (m) – EPSG:3035")

plt.savefig(
    output_path,
    dpi=600,
    bbox_inches="tight",
    pad_inches=0.05
)