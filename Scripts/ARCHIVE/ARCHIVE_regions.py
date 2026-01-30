import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

# paths
GADM_PATH = "../../Data/raw/gadm/gadm_410-levels-ADM_1-DNK.gpkg"
EEZ_PATH = "../../Data/raw/marineregions/eez_v11.gpkg"

OUT_DIR = "../../Data/processed"
PLOT_PATH = "../../plots_and_figures/regions_and_eez_by_region.png"

CENTROIDS_CSV = f"{OUT_DIR}/region_centroids.csv"
REGIONS_GEOJSON = f"{OUT_DIR}/dk_regions.geojson"
EEZ_DK_GEOJSON = f"{OUT_DIR}/dk_eez.geojson"
EEZ_BY_REGION_GEOJSON = f"{OUT_DIR}/dk_eez_by_region.geojson"

#costs data
regions = gpd.read_file(GADM_PATH)
eez = gpd.read_file(EEZ_PATH)
eez_dk = eez.loc[eez["ISO_TER1"] == "DNK"].copy()
eez_dk = eez_dk.to_crs(regions.crs)

#calculating centroids
regions_m = regions.to_crs(epsg=3035)
regions["centroid"] = regions_m.centroid.to_crs(epsg=4326)

centroids = pd.DataFrame({
    "region": regions["NAME_1"],
    "lon": regions["centroid"].x,
    "lat": regions["centroid"].y,
})
centroids.to_csv(CENTROIDS_CSV, index=False)

#saving GeoJSON files
regions_out = regions[["NAME_1", "geometry"]].copy()
regions_out.to_file(REGIONS_GEOJSON, driver="GeoJSON")
eez_dk.to_file(EEZ_DK_GEOJSON, driver="GeoJSON")

# splitting EEZ
eez_m = eez_dk.to_crs(epsg=3035)

# Clipper, damit Voronoi endlich wird (Envelope der EEZ + Buffer)
clipper_geom = eez_m.geometry.union_all().envelope.buffer(200_000)  # 200 km
clipper = gpd.GeoDataFrame(geometry=[clipper_geom], crs=eez_m.crs)

# Voronoi-Polygone aus repräsentativen Punkten der Regionen
region_pts = regions_m.geometry.representative_point()
vor_polys = region_pts.voronoi_polygons()

vor_gdf = gpd.GeoDataFrame(
    {"NAME_1": regions_m["NAME_1"].values},
    geometry=vor_polys,
    crs=regions_m.crs,
)

# Voronoi beschneiden und dann EEZ damit schneiden
vor_gdf = gpd.overlay(vor_gdf, clipper, how="intersection")
eez_split = gpd.overlay(eez_m, vor_gdf, how="intersection")

# optional: pro Region zusammenfassen
eez_by_region = eez_split.dissolve(by="NAME_1").reset_index()

# Export (als WGS84)
eez_by_region.to_crs(epsg=4326)[["NAME_1", "geometry"]].to_file(
    EEZ_BY_REGION_GEOJSON,
    driver="GeoJSON"
)


# Plot

fig, ax = plt.subplots(figsize=(8, 10))

# colors for regions
region_names = regions["NAME_1"].unique()
n_regions = len(region_names)
cmap = plt.get_cmap("tab20", n_regions)
color_map = {
    name: cmap(i) for i, name in enumerate(region_names)
}

# EEZ-segments
eez_by_region_plot = eez_by_region.to_crs(regions.crs)
eez_by_region_plot["color"] = eez_by_region_plot["NAME_1"].map(color_map)

eez_by_region_plot.plot(
    ax=ax,
    color=eez_by_region_plot["color"],
    alpha=0.35,
    edgecolor="none",
    zorder=1
)

# regions
regions_plot = regions.copy()
regions_plot["color"] = regions_plot["NAME_1"].map(color_map)

regions_plot.plot(
    ax=ax,
    facecolor=regions_plot["color"],
    edgecolor="black",
    linewidth=0.9,
    alpha=0.85,
    zorder=2
)

# Centroids
ax.scatter(
    centroids["lon"],
    centroids["lat"],
    s=90,
    color="white",
    zorder=5
)
ax.scatter(
    centroids["lon"],
    centroids["lat"],
    s=30,
    color="black",
    zorder=6
)

# Labels
for _, row in centroids.iterrows():
    ax.text(
        row["lon"],
        row["lat"] + 0.08,  # leicht nach oben versetzt
        row["region"],
        fontsize=8,
        ha="center",
        va="bottom",
        zorder=7,
        bbox=dict(
            facecolor="white",
            edgecolor="none",
            alpha=0.75,
            boxstyle="round,pad=0.2"
        )
    )

# Layout
ax.set_title("Denmark: Regions and EEZ split by nearest region", fontsize=13)
ax.set_axis_off()
plt.tight_layout()

plt.savefig(
    PLOT_PATH,
    dpi=600,
    bbox_inches="tight",
    pad_inches=0.05
)
plt.show()


