import geopandas as gpd
import matplotlib.pyplot as plt
from atlite.gis import ExclusionContainer, shape_availability
from rasterio.plot import show

###########################################
# PATHS
###########################################

EEZ_PATH = "../Data/processed/dk_eez_by_region_etr.geojson"
DK_PATH = "../Data/raw/gadm/gadm_410-levels-ADM_1-DNK.gpkg"
PA_PATH = "../Data/raw/wdpa/WDPA_Oct2022_Public_shp-DNK.tif"
EV_PATH = "../Data/raw/gebco/GEBCO_2014_2D-DK.nc"

output_path = "../plots_and_figures/eligible_offshore_wind_areas_DK.png"

###########################################
# Load data and define excluder
###########################################

excluder = ExclusionContainer(crs=3035, res=100)
EEZ = gpd.read_file(EEZ_PATH)
EEZ_shape = EEZ.to_crs(excluder.crs).geometry

excluder.add_raster(PA_PATH)
excluder.add_geometry(DK_PATH, buffer=10000)
excluder.add_raster(EV_PATH, codes=lambda x: x<-50, crs=4326)

###########################################
# Plot
###########################################

band, transform = shape_availability(EEZ_shape, excluder)
fig, ax = plt.subplots(figsize=(4, 8))
EEZ_shape.plot(ax=ax, color="none")
show(band, transform=transform, cmap="Greens", ax=ax)
ax.set_title("Eligible offshore Wind Energy Areas in Denmark")
ax.set_xlabel("Easting (m) – EPSG:3035")
ax.set_ylabel("Northing (m) – EPSG:3035")

plt.savefig(
    output_path,
    dpi=600,
    bbox_inches="tight",
    pad_inches=0.05
)
