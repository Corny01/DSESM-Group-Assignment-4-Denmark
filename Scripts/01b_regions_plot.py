import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

###########################################
# PATHS
###########################################

REPPOINTS_CSV = "../Data/processed/region_centroids.csv"
REGIONS_GEOJSON = "../Data/processed/dk_regions.geojson"
EEZ_BY_REGION_GEOJSON = "../Data/processed/dk_eez_by_region.geojson"
EEZ_PATH = "../Data/raw/marineregions/eez_v11.gpkg"

PLOT_PATH = "../plots_and_figures/regions_and_eez_by_region_split.png"

###########################################
# Load Data
###########################################

regions_etr2 = gpd.read_file(REGIONS_GEOJSON)
eez = gpd.read_file(EEZ_PATH)
eez_by_region_etr = gpd.read_file(EEZ_BY_REGION_GEOJSON)
rep_points_df = pd.read_csv(REPPOINTS_CSV, index_col=[0])

rep_points_gdf = gpd.GeoDataFrame(
    rep_points_df,
    geometry=gpd.points_from_xy(rep_points_df["lon"], rep_points_df["lat"]),
    crs="EPSG:3035"
)
rep_points_gdf = rep_points_gdf.drop(columns=["lon", "lat"])

###########################################
# Plot regions and split EEZ
###########################################
PLOT_CRS = "EPSG:3035"

regions_plot = regions_etr2.to_crs(PLOT_CRS).copy()
eez_total_plot = eez.to_crs(PLOT_CRS).copy()
eez_by_region_plot = eez_by_region_etr.to_crs(PLOT_CRS).copy()

fig, ax = plt.subplots(figsize=(11, 11))

COLORS = {
    "Nordjylland": "#4E79A7",
    "Midtjylland": "#F28E2B",
    "Syddanmark": "#59A14F",
    "Sjælland": "#E15759",
    "Hovedstaden_West": "#B07AA1",
    "Hovedstaden_East": "#9C755F",
}
regions_plot["color"] = regions_plot["NAME_1"].map(COLORS)
eez_by_region_plot["color"] = eez_by_region_plot["NAME_1"].map(COLORS)

STYLE = {
    # color intensity
    "alpha_regions": 0.85,
    "alpha_eez": 0.4,

    # borders
    "lw_regions": 1.2,
    "lw_eez": 0.0,
    "edgecolor_regions": "black",
    "edgecolor_eez": "none",

    # representative points
    "pt_size": 30,
    "pt_color": "black",

    # Labels
    "label_fontsize": 9,
    "label_fontweight": "normal",
    "label_dx": 3000,
    "label_dy": 3000,
    "label_ha": "left",
    "label_va": "bottom",

    # Label Box
    "label_box": True,
    "label_box_fc": "white",
    "label_box_alpha": 0.6,
    "label_box_ec": "none",
}

eez_by_region_plot.plot(
    ax=ax,
    color=eez_by_region_plot["color"],
    alpha=STYLE["alpha_eez"],
    edgecolor=STYLE["edgecolor_eez"],
    linewidth=STYLE["lw_eez"],
    zorder=2
)

regions_plot.plot(
    ax=ax,
    color=regions_plot["color"],
    alpha=STYLE["alpha_regions"],
    edgecolor=STYLE["edgecolor_regions"],
    linewidth=STYLE["lw_regions"],
    zorder=3
)

rep_points_gdf.plot(
    ax=ax,
    color=STYLE["pt_color"],
    markersize=STYLE["pt_size"],
    zorder=4
)

for region, row in rep_points_gdf.iterrows():
    ax.text(
        row.geometry.x + STYLE["label_dx"],
        row.geometry.y + STYLE["label_dy"],
        region,
        fontsize=STYLE["label_fontsize"],
        fontweight=STYLE["label_fontweight"],
        ha=STYLE["label_ha"],
        va=STYLE["label_va"],
        zorder=5,
    )

ax.set_title("Denmark regions incl. EEZ zones")
ax.set_aspect("equal")

plt.tight_layout()
plt.savefig(PLOT_PATH, dpi=300, bbox_inches="tight")
plt.close(fig)