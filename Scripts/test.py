import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import shapely
from shapely.geometry import LineString
from shapely.ops import split
import matplotlib.pyplot as plt

# ------------------ PATHS ------------------
GADM_PATH = "../Data/raw/gadm/gadm_410-levels-ADM_1-DNK.gpkg"
EEZ_PATH = "../Data/raw/marineregions/eez_v11.gpkg"

OUT_DIR = "../Data/processed"
PLOT_PATH = "../plots_and_figures/regions_and_eez_by_region_split.png"

REPPOINTS_CSV = f"{OUT_DIR}/region_centroids.csv"  # Dateiname kann bleiben; Inhalt = rep points
REGIONS_GEOJSON = f"{OUT_DIR}/dk_regions.geojson"
EEZ_DK_GEOJSON = f"{OUT_DIR}/dk_eez.geojson"
EEZ_BY_REGION_GEOJSON = f"{OUT_DIR}/dk_eez_by_region.geojson"

# ------------------ MANUAL SPLIT PARAM ------------------
# Longitude (EPSG:4326). Wähle so, dass Bornholm rechts davon liegt.
SPLIT_LON = 13.4

# ------------------ LOAD ------------------
regions = gpd.read_file(GADM_PATH)
eez = gpd.read_file(EEZ_PATH)

eez_dk = eez.loc[eez["ISO_TER1"] == "DNK"].copy()
eez_dk = eez_dk.to_crs(regions.crs)

###########################################
# split Hovedstaden by a fixed longitude
###########################################

#load geometry of hovedstaden
regions_wgs = regions.to_crs(epsg=4326) #epsg4326 to use longitude to split
filter_hov = regions_wgs["NAME_1"] == "Hovedstaden"
hov_geom = regions_wgs.loc[filter_hov, "geometry"].iloc[0] #.iloc[0] to get one geometry not a series with one geometry

#create splitting line
minx, miny, maxx, maxy = regions_wgs.total_bounds
meridian = LineString([(SPLIT_LON, miny - 1.0), (SPLIT_LON, maxy + 1.0)]) #create dividing line; +/-1 degree buffer to avoid enumeration mistakes

#split
hov_splitted = split(hov_geom, meridian) #creates collection of geometries

#save splitted geometry as new regions
hov_regions = list(hov_splitted.geoms) #list of geometries in unknown order
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
    "lon": rep_points.x,
    "lat": rep_points.y,
})
rep_points_df.to_csv(REPPOINTS_CSV, index=False)

###########################################
# Split EEZ by region into Voronoi-cells based on representative points
###########################################
eez_etr = eez_dk.to_crs(epsg=3035) #projection with true distances needed as Voronoi is based on distances

clipper_geom = eez_etr.geometry.union_all().envelope.buffer(1000) #set boundaries of Voronoi cells including buffer
clipper = gpd.GeoDataFrame(geometry=[clipper_geom], crs=eez_etr.crs)

vor_polys = rep_points.voronoi_polygons() #create Voronoi-cells
vor_gdf = gpd.GeoDataFrame(
    {"NAME_1": regions_etr2["NAME_1"].values},
    geometry=vor_polys,
    crs=regions_etr2.crs,
)

vor_gdf = gpd.overlay(vor_gdf, clipper, how="intersection")
eez_split = gpd.overlay(eez_etr, vor_gdf, how="intersection")
eez_by_region_etr = eez_split.dissolve(by="NAME_1").reset_index()

eez_by_region_etr.to_crs(epsg=3035)[["NAME_1", "geometry"]].to_file(
    EEZ_BY_REGION_GEOJSON,
    driver="GeoJSON"
)

###########################################
# Plot regions and splitted EEZ
###########################################
PLOT_CRS = "EPSG:3035"

regions_plot = regions_.to_crs(PLOT_CRS).copy()
eez_total_plot = eez_dk.to_crs(PLOT_CRS).copy()
eez_by_region_plot = eez_by_region_etr.to_crs(PLOT_CRS).copy()

# --- Ensure consistent region naming key ---
# regions_plot: NAME_1 exists
# eez_by_region_plot: NAME_1 should exist (from your dissolve)
if "NAME_1" not in regions_plot.columns:
    raise ValueError("regions2 braucht eine Spalte NAME_1.")
if "NAME_1" not in eez_by_region_plot.columns:
    raise ValueError("eez_by_region braucht eine Spalte NAME_1.")

# --- Build a stable color map for ALL regions (incl. both Hovedstaden parts) ---
region_names = sorted(regions_plot["NAME_1"].unique())

# A "more matching" palette: use tab10/tab20 depending on count.
# For 6 regions: tab10 is very consistent/pleasant.
cmap = plt.get_cmap("tab10" if len(region_names) <= 10 else "tab20")
color_map = {name: cmap(i % cmap.N) for i, name in enumerate(region_names)}

# Add color columns
regions_plot["color"] = regions_plot["NAME_1"].map(color_map)

# --- Make EEZ-by-region inherit the exact same color by joining on NAME_1 ---
eez_by_region_plot = eez_by_region_plot.merge(
    regions_plot[["NAME_1", "color"]],
    on="NAME_1",
    how="left",
    validate="many_to_one"
)

# If any EEZ region didn't note a color (name mismatch), give a visible fallback and warn
missing = eez_by_region_plot["color"].isna()
if missing.any():
    missing_names = eez_by_region_plot.loc[missing, "NAME_1"].unique().tolist()
    print("⚠️ EEZ-Regionen ohne Farbzuteilung (Name mismatch):", missing_names)
    eez_by_region_plot.loc[missing, "color"] = [(0.6, 0.6, 0.6, 1.0)] * missing.sum()

# --- Representative points: ONLY from land regions (not EEZ) ---
rep_pts = regions_plot.geometry.representative_point()
rep_gdf = gpd.GeoDataFrame(
    {"NAME_1": regions_plot["NAME_1"].values},
    geometry=rep_pts,
    crs=PLOT_CRS
)

# --- Plot ---
fig, ax = plt.subplots(figsize=(11, 11))

# 1) total EEZ as very light background (optional)
eez_total_plot.plot(ax=ax, color="lightgrey", alpha=0.12, edgecolor="none", zorder=1)

# 2) EEZ by region, same color but lighter
eez_by_region_plot.plot(
    ax=ax,
    color=eez_by_region_plot["color"],
    alpha=0.25,
    edgecolor="none",
    zorder=2
)

# 3) regions filled with same color (stronger) + boundary
regions_plot.plot(
    ax=ax,
    color=regions_plot["color"],
    alpha=0.80,
    edgecolor="black",
    linewidth=1.1,
    zorder=3
)

# 4) rep points + labels
rep_gdf.plot(ax=ax, color="black", markersize=18, zorder=4)
for x, y, name in zip(rep_gdf.geometry.x, rep_gdf.geometry.y, rep_gdf["NAME_1"]):
    ax.text(x, y, name, fontsize=9, ha="left", va="bottom", zorder=5)

ax.set_title("Denmark regions (colored) + EEZ zones (same color, lighter)")
ax.set_axis_off()
ax.set_aspect("equal")

plt.tight_layout()
plt.savefig(PLOT_PATH, dpi=300, bbox_inches="tight")
plt.close(fig)

print(f"✅ Plot gespeichert unter: {PLOT_PATH}")
