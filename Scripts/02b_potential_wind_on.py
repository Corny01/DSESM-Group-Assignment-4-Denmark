import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from rasterio.features import shapes
from shapely.geometry import shape
from atlite.gis import ExclusionContainer, shape_availability
from rasterio.plot import show

###########################################
# PATHS
###########################################

DK_PATH = "../Data/processed/dk_regions_etr.geojson"
LC_PATH = "../Data/raw/copernicus/PROBAV_LC100_global_v3.0.1_2019-nrt_Discrete-Classification-map_EPSG-4326-DK.tif"
PA_PATH = "../Data/raw/wdpa/WDPA_Oct2022_Public_shp-DNK.tif"
AP_PATH = "../Data/raw/ne_10m_airports.gpkg"
R_PATH = "../Data/raw/ne_10m_roads.gpkg"

output_path = "../plots_and_figures/eligible_onshore_wind_areas_DK.png"
output_shape_path = "../Data/processed/eligibility/eligible_wind_on_areas_DK.gpkg"

###########################################
# Load data and define excluder
###########################################

roads = gpd.read_file(R_PATH)
major_roads = roads[roads["scalerank"].between(1, 4)].copy() #filter for main roads

excluder = ExclusionContainer(crs=3035, res=100)
DK = gpd.read_file(DK_PATH)
DK_shape = DK.to_crs(excluder.crs).geometry
major_roads = major_roads.to_crs(excluder.crs).geometry

excluder.add_geometry(AP_PATH, buffer=10000)
excluder.add_geometry(major_roads, buffer=300)

codes_to_exclude = [90, 80, 200]
excluder.add_raster(LC_PATH, codes=codes_to_exclude, crs=3035, buffer=800, nodata=48)
excluder.add_raster(LC_PATH, codes=50, crs=3035, buffer=1000, nodata=48)
excluder.add_raster(PA_PATH)
#excluder for elevation not needed as highest point in Denmark is about 170m

###########################################
# Calculate available area and save es shape
###########################################

band, transform = shape_availability(DK_shape, excluder)

geoms = []
for geom, value in shapes(band.astype(np.uint8), transform=transform):
    if value == 1:
        geoms.append(shape(geom))

available_areas = gpd.GeoDataFrame(
    geometry=geoms,
    crs=excluder.crs
)

available_areas.to_file(
    output_shape_path,
    layer="eligible_wind_on_areas",
    driver="GPKG"
)

###########################################
# Plot
###########################################

fig, ax = plt.subplots(figsize=(7, 14))
DK_shape.plot(ax=ax, color="none")
show(band, transform=transform, cmap="Greens", ax=ax);
ax.set_title("Eligible onshore Wind Energy Areas in Denmark")
ax.set_xlabel("Easting (m) – EPSG:3035")
ax.set_ylabel("Northing (m) – EPSG:3035")

plt.savefig(
    output_path,
    dpi=600,
    bbox_inches="tight",
    pad_inches=0.05
)