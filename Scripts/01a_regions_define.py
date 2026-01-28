import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import LineString
from shapely.ops import split

###########################################
# INPUT
###########################################
SPLIT_LON = 13.4 #degree of longitude that splits the region Hovedstaden -> 13.4 approximately retrieved by google earth

###########################################
# PATHS
###########################################
GADM_PATH = "../Data/raw/gadm/gadm_410-levels-ADM_1-DNK.gpkg"
EEZ_PATH = "../Data/raw/marineregions/eez_v11.gpkg"

OUT_DIR = "../Data/processed"

REPPOINTS_CSV_etr = f"{OUT_DIR}/region_centroids_etr.csv"
REPPOINTS_CSV_wsg = f"{OUT_DIR}/region_centroids_wsg.csv"
REGIONS_GEOJSON = f"{OUT_DIR}/dk_regions_etr.geojson"
EEZ_BY_REGION_GEOJSON = f"{OUT_DIR}/dk_eez_by_region_etr.geojson"

###########################################
# Load Data
###########################################
regions = gpd.read_file(GADM_PATH)
eez = gpd.read_file(EEZ_PATH)

eez_dk = eez.loc[eez["ISO_TER1"] == "DNK"].copy()
eez_dk = eez_dk.to_crs(regions.crs)

###########################################
# Split Hovedstaden by a fixed longitude
###########################################

#load geometry of hovedstaden
regions_wgs = regions.to_crs(epsg=4326) #epsg4326 to use longitude to split
filter_hov = regions_wgs["NAME_1"] == "Hovedstaden"
hov_geom = regions_wgs.loc[filter_hov, "geometry"].iloc[0] #.iloc[0] to get one geometry not a series with one geometry

#create splitting line
minx, miny, maxx, maxy = regions_wgs.total_bounds
meridian = LineString([(SPLIT_LON, miny - 1.0), (SPLIT_LON, maxy + 1.0)]) #create dividing line; +/-1 degree buffer to avoid enumeration mistakes

#split
hov_split = split(hov_geom, meridian) #creates collection of geometries

#save split geometry as new regions
hov_regions = list(hov_split.geoms) #list of geometries in unknown order
western_geoms = []
eastern_geoms = []
for g in hov_regions: #sort geometries from collection based on representative point to eastern or western of the splitting line
    x = g.representative_point().x
    if x < SPLIT_LON:
        western_geoms.append(g)
    else:
        eastern_geoms.append(g)

hov_west = shapely.union_all(western_geoms)   # combine geometries of one side of the splitting line to one region
hov_east = shapely.union_all(eastern_geoms)

regions_others = regions_wgs.loc[~filter_hov].copy() #regions without hovedstaden
hov_row = regions_wgs.loc[filter_hov].iloc[0].copy()

west_row = hov_row.copy() #create row in right structure to include into regions gdf
west_row["NAME_1"] = "Hovedstaden_West"
west_row["geometry"] = hov_west

east_row = hov_row.copy() #create row in right structure to include into regions gdf
east_row["NAME_1"] = "Hovedstaden_East"
east_row["geometry"] = hov_east

regions_wgs2 = pd.concat( #combine regions into one gdf
    [regions_others, gpd.GeoDataFrame([west_row, east_row], crs=regions_wgs.crs)],
    ignore_index=True
)
regions_etr2 = regions_wgs2.to_crs(epsg=3035)
regions_etr2.to_file(REGIONS_GEOJSON, driver="GeoJSON")

###########################################
# Calculate representative points
###########################################

rep_points = regions_etr2.representative_point()
rep_points_df = pd.DataFrame({
    "region": regions_wgs2["NAME_1"],
    "x": rep_points.x,
    "y": rep_points.y,
})
rep_points_df.to_csv(REPPOINTS_CSV_etr, index=False)

rep_points_wsg = rep_points.to_crs(4326)
rep_points_df_wsg = pd.DataFrame({
    "region": regions_wgs2["NAME_1"],
    "lon": rep_points_wsg.x,
    "lat": rep_points_wsg.y,
})
rep_points_df_wsg.to_csv(REPPOINTS_CSV_wsg, index=False)

###########################################
# Split EEZ by region into Voronoi-cells based on representative points and join with correct region
###########################################
rep_points_etr = rep_points.to_crs(epsg=3035) #projection with true distances needed as Voronoi is based on distances
rep_points_gdf = gpd.GeoDataFrame( #to join the Voronoi-cells with correct region
    regions_etr2[["NAME_1"]].copy(),
    geometry=rep_points_etr,
    crs=regions_etr2.crs
)

vor_polys = rep_points_etr.voronoi_polygons() #create Voronoi-cells
vor_gdf = gpd.GeoDataFrame(geometry=vor_polys) #to join the Voronoi-cells with correct region
vor_with_name = gpd.sjoin( #join Voronoi-cells with region
    vor_gdf,
    rep_points_gdf[["NAME_1", "geometry"]],
    how="left",
    predicate="contains"
)
vor_with_name = vor_with_name[["NAME_1", "geometry"]]

###########################################
# Clip EEZ and cut out land mass
###########################################

eez_etr = eez_dk.to_crs(epsg=3035) #projection with true distances needed as Voronoi is based on distances
clipper_geom = eez_etr.geometry.union_all().envelope.buffer(1000) #set boundaries of Voronoi cells including buffer
clipper = gpd.GeoDataFrame(geometry=[clipper_geom], crs=eez_etr.crs)

vor_clipped = gpd.overlay(vor_with_name, clipper, how="intersection")
eez_split = gpd.overlay(eez_etr,  vor_clipped,   how="intersection")

eez_by_region_etr = eez_split.dissolve(by="NAME_1").reset_index()

###########################################
# Save EEZ divided into regions
###########################################

eez_by_region_etr.to_crs(epsg=3035)[["NAME_1", "geometry"]].to_file(
    EEZ_BY_REGION_GEOJSON,
    driver="GeoJSON"
)

