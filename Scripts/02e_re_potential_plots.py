import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ----------------------------
# Paths (adjust if needed)
# ----------------------------
CF_PATH = "../Data/processed/dk_re_cf_timeseries_2013.csv"
PMAX_PATH = "../Data/processed/dk_re_max_potentials_by_region_2013.csv"
LOADS_PATH = "../Data/processed/load_regions.csv"

PLOT_DIR = Path("../plots_and_figures/Renewable_potential")
PLOT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# 1) Read inputs
# ----------------------------
cf = pd.read_csv(CF_PATH, parse_dates=["timestamp"])
pmax = pd.read_csv(PMAX_PATH)
loads = pd.read_csv(LOADS_PATH, parse_dates=["time"])

cf["region"] = cf["region"].astype(str)
pmax["region"] = pmax["region"].astype(str)

# Align time index
cf = cf.sort_values(["timestamp", "region"])
loads = loads.sort_values("time").set_index("time")

# Map potentials onto CF rows
pot = pmax.set_index("region")

cf["pmax_onshore_MW"]  = cf["region"].map(pot["onshore_potential_MW"])
cf["pmax_offshore_MW"] = cf["region"].map(pot["offshore_potential_MW"])
cf["pmax_pv_MW"]       = cf["region"].map(pot["solar_potential_MW"])

# ----------------------------
# 2) Compute generation (MW) per region & timestamp
# ----------------------------
cf["gen_onshore_MW"]  = cf["cf_onshore"]  * cf["pmax_onshore_MW"]
cf["gen_offshore_MW"] = cf["cf_offshore"] * cf["pmax_offshore_MW"]
cf["gen_pv_MW"]       = cf["cf_pv"]       * cf["pmax_pv_MW"]

# Wide time series: index=time, columns=region
gen_onshore  = cf.pivot(index="timestamp", columns="region", values="gen_onshore_MW").sort_index()
gen_offshore = cf.pivot(index="timestamp", columns="region", values="gen_offshore_MW").sort_index()
gen_pv       = cf.pivot(index="timestamp", columns="region", values="gen_pv_MW").sort_index()

# ----------------------------
# 3) Plot: production time series for all regions in one graph, per technology (with legend)
# ----------------------------
plt.figure(figsize=(12, 5))
for col in gen_onshore.columns:
    plt.plot(gen_onshore.index, gen_onshore[col], label=str(col))
plt.title("Onshore wind generation (MW) by region")
plt.xlabel("Time")
plt.ylabel("MW")
plt.legend(ncol=2, fontsize=8)
plt.tight_layout()
plt.savefig(PLOT_DIR / "onshore_generation_timeseries.png", dpi=300)
plt.close()

plt.figure(figsize=(12, 5))
for col in gen_offshore.columns:
    plt.plot(gen_offshore.index, gen_offshore[col], label=str(col))
plt.title("Offshore wind generation (MW) by region")
plt.xlabel("Time")
plt.ylabel("MW")
plt.legend(ncol=2, fontsize=8)
plt.tight_layout()
plt.savefig(PLOT_DIR / "offshore_generation_timeseries.png", dpi=300)
plt.close()

plt.figure(figsize=(12, 5))
for col in gen_pv.columns:
    plt.plot(gen_pv.index, gen_pv[col], label=str(col))
plt.title("Solar PV generation (MW) by region")
plt.xlabel("Time")
plt.ylabel("MW")
plt.legend(ncol=2, fontsize=8)
plt.tight_layout()
plt.savefig(PLOT_DIR / "pv_generation_timeseries.png", dpi=300)
plt.close()

# ----------------------------
# 4) Denmark total generation (stacked by technology) + load line
# ----------------------------
dk_onshore  = gen_onshore.sum(axis=1)
dk_offshore = gen_offshore.sum(axis=1)
dk_pv       = gen_pv.sum(axis=1)

dk_gen = pd.DataFrame(
    {"PV": dk_pv, "Onshore wind": dk_onshore, "Offshore wind": dk_offshore}
).sort_index()

# Align with load time index
dk_load = loads["DK"].reindex(dk_gen.index)

plt.figure(figsize=(12, 5))
plt.stackplot(
    dk_gen.index,
    dk_gen["PV"].values,
    dk_gen["Onshore wind"].values,
    dk_gen["Offshore wind"].values,
    labels=["PV", "Onshore wind", "Offshore wind"],
)
plt.plot(dk_gen.index, dk_load.values, label="Load (DK)")
plt.title("Denmark generation (stacked) and load")
plt.xlabel("Time")
plt.ylabel("MW")
plt.legend(loc="upper right", fontsize=9)
plt.tight_layout()
plt.savefig(PLOT_DIR / "denmark_generation_stacked_with_load.png", dpi=300)
plt.close()

# ----------------------------
# 5) Residual load = Load - (PV + Onshore + Offshore)
# ----------------------------
residual_load = dk_load - dk_gen.sum(axis=1)

plt.figure(figsize=(12, 5))
plt.plot(residual_load.index, residual_load.values, label="Residual load (DK)")
plt.axhline(0, linewidth=1)
plt.title("Residual load in Denmark (Load - Renewable generation)")
plt.xlabel("Time")
plt.ylabel("MW")
plt.legend(loc="upper right", fontsize=9)
plt.tight_layout()
plt.savefig(PLOT_DIR / "denmark_residual_load.png", dpi=300)
plt.close()

print(f"Saved plots to: {PLOT_DIR.resolve()}")