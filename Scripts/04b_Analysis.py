import pypsa
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

NETWORK = "../results/n_ZE0_CY2030_WY2018_NUC0_NRcapex2500_CRF_s0_CRF_on0_CRF_off0_PRF_s0_PRF_on0_PRF_off0_L2000.nc"
FOLDER = NETWORK.replace("../results/", "").removesuffix(".nc")

n = pypsa.Network(NETWORK)

# ---------- scenario folder + filename tag ----------
outdir = Path("../results") / FOLDER
outdir.mkdir(parents=True, exist_ok=True)

tag = FOLDER

costs_total = n.objective / 1e9 # in billion €
pd.DataFrame(
    {"total_system_cost_billion_EUR": [costs_total]}
).to_csv(outdir / f"costs_total_{tag}.csv", index=False)

# ---------- 1) total system cost split by technology ----------
system_cost_by_tech = n.statistics.system_cost(groupby="carrier").div(1e6).round(2) # Million €
capex_by_tech = n.statistics.capex(groupby="carrier").div(1e6).round(2) # Million €
opex_by_tech = n.statistics.opex(groupby="carrier").div(1e6).round(2) # Million €
tsc = (
    pd.concat(
        {
            "capex in Million €": capex_by_tech,
            "opex in Million €": opex_by_tech,
            "total in Million €": system_cost_by_tech,
        },
        axis=1,
    )
)
tsc.to_csv(outdir / f"capex_by_carrier_{tag}.csv")

# ---------- 2) capacities built per technology ----------
opt_cap = n.statistics.optimal_capacity(groupby="carrier").div(1e3).round(2) # GW
inst_cap = n.statistics.installed_capacity(groupby="carrier").div(1e3).round(2) # GW
cap = (
    pd.concat(
        {
            "installed capacity in GW": opt_cap,
            "optimal capacity in GW": inst_cap,
            "added capacity in GW": opt_cap-inst_cap,
        },
        axis=1,
    )
)
cap.to_csv(outdir / f"installed_capacity_by_carrier_{tag}.csv")

opt_cap_bus = n.statistics.optimal_capacity(groupby=["bus", "carrier"]).div(1e3).round(2) # GW
inst_cap_bus = n.statistics.installed_capacity(groupby=["bus", "carrier"]).div(1e3).round(2) # GW
cap_bus = (
    pd.concat(
        {
            "installed capacity in GW": opt_cap_bus,
            "optimal capacity in GW": inst_cap_bus,
            "added capacity in GW": opt_cap_bus-inst_cap_bus,
        },
        axis=1,
    )
)
cap_bus.to_csv(outdir / f"optimal_capacity_by_bus_carrier_{tag}.csv")

# ---------- 3) electricity mix ----------
gen_p_by_carrier = n.statistics.energy_balance().sort_values().div(1e6).round(2)  # TWh
total_gen = gen_p_by_carrier.sum(axis=1) if isinstance(gen_p_by_carrier, pd.DataFrame) else gen_p_by_carrier
electricity_mix = gen_p_by_carrier.div(total_gen.replace(0, np.nan), axis=0).fillna(0.0)
energy_balance = (
    pd.concat(
        {
            "production in TWh": gen_p_by_carrier,
            "share in %": (gen_p_by_carrier / total_gen) * 100,
        },
        axis=1,
    )
)
energy_balance.to_csv(outdir / f"energy_balance_{tag}.csv")

# ---------- LCOE ----------
demand = n.snapshot_weightings.generators @ n.loads_t.p_set.sum(axis=1)
LCOE = tsc.sum(axis=1).sum() * 1e9 / demand.sum()
pd.DataFrame(
    {"LCOE_EUR_per_MWh": [LCOE]}
).to_csv(outdir / f"LCOE_{tag}.csv", index=False)

# ---------- 4) CO2 shadow price ----------
co2_shadow_price = n.global_constraints["mu"]
co2_shadow_price.to_csv(outdir / f"co2_shadow_price_{tag}.csv")

# ---------- 5) price duration curves (per region) ----------
ax = n.buses_t.marginal_price.plot(figsize=(12, 5))
ax.set_ylabel("Electricity Price [€/MWh]")
ax.set_xlabel("Time")

plt.tight_layout()
plt.savefig(outdir / f"prices_{tag}.png", dpi=300)
plt.close()

mp = n.buses_t.marginal_price  # Zeit × Bus

# Price Duration Curves für alle Busse
pdc_df = pd.DataFrame(
    {
        bus: mp[bus].sort_values(ascending=False).reset_index(drop=True).values
        for bus in mp.columns
    }
)

pdc_df.index = np.linspace(0, 100, len(pdc_df))

ax = pdc_df.plot(figsize=(12, 5))
ax.set_xlabel("Percentage of time [%]")
ax.set_ylabel("Electricity Price [€/MWh]")
ax.set_title("Price Duration Curves (all buses)")
ax.legend(title="Bus", fontsize=8, ncol=2)

plt.tight_layout()
plt.savefig(outdir / f"pdc_all_buses_{tag}.png", dpi=300)
plt.close()

# ---------- 6) average electricity prices per region ----------
avg_prices = n.buses_t.marginal_price.mean().to_frame("avg_price_EUR_per_MWh")
avg_prices.to_csv(outdir / f"avg_prices_by_bus_{tag}.csv")

avg_prices_bus_carrier = n.statistics.prices(groupby="bus_carrier", round=2)
avg_prices_bus_carrier.to_csv(outdir / f"avg_prices_by_bus_carrier_{tag}.csv")

# ---------- 7) curtailment rate ----------
curt = n.statistics.curtailment(groupby="carrier").div(1e6)  # TWh

gen_by_carrier_energy = gen_p_by_carrier.sum()
curt_pct = 100 * curt.squeeze() / gen_by_carrier_energy

curtailment = (
    pd.concat(
        {
            "energy potential not used in GWh": curt,
            "share in %": curt_pct,
        },
        axis=1,
    )
)

curtailment.to_csv(outdir / f"curtailment_by_carrier_{tag}.csv")

# ---------- 8) storage filling levels ----------
soc = n.storage_units_t.state_of_charge.div(1e3).round(2)  # GWh
soc_daily = soc.resample("D").mean().round(2)
ax = soc_daily.plot(figsize=(12, 5))   # <- kein labels=

ax.set_xlabel("Time")
ax.set_ylabel("State of charge [GWh]")
ax.set_title("Daily average state of charge")

plt.tight_layout()
plt.savefig(outdir / f"soc_daily_{tag}.png", dpi=600)
plt.close()

#Example weeks
start_low = "2013-01-01"
end_low = "2013-01-07"
start_high = "2013-06-01"
end_high = "2013-06-07"

ax = n.buses_t.marginal_price.loc[start_low:end_low].plot(
    figsize=(12, 5),
    label="pc_low"
)
n.buses_t.marginal_price.loc[start_high:end_high].plot(
    ax=ax,
    label="pc_high"
)
ax.set_ylabel("Electricity Price [€/MWh]")
ax.legend()
plt.tight_layout()
plt.savefig(outdir / f"week_analysis_pc_{tag}.png", dpi=600)
plt.close()

curt_low = n.statistics.curtailment(groupby="carrier").loc[start_low:end_low].div(1e6)  # TWh
curt_high = n.statistics.curtailment(groupby="carrier").loc[start_high:end_high].div(1e6)  # TWh
gen_by_carrier_energy = gen_p_by_carrier.sum()
curt_low_pct = 100 * curt_low.squeeze() / gen_by_carrier_energy
curt_high_pct = 100 * curt_high.squeeze() / gen_by_carrier_energy
curtailment_comp = (
    pd.concat(
        {
            "low energy potential not used in GWh": curt_low,
            "low share in %": curt_low_pct,
            "high energy potential not used in GWh": curt_high,
            "high share in %": curt_high_pct,
        },
        axis=1,
    )
)

curtailment_comp.to_csv(outdir / f"week_analysis_curtailment_by_carrier_{tag}.csv")

links_low = n.links_t.p0.loc[start_low:end_low]
links_high = n.links_t.p0.loc[start_high:end_high]
p_links = n.links.p_nom_opt
links_low_pct = 100 * links_low.squeeze() / p_links
links_high_pct = 100 * links_high.squeeze() / p_links
links_comp = (
    pd.concat(
        {
            "low re: link utilization in %": links_low_pct,
            "high re: link utilization in %": links_high_pct,
        },
        axis=1,
    )
)

ax = links_comp.plot(figsize=(12, 5))

ax.set_xlabel("Time")
ax.set_ylabel("Link utilization [%]")
ax.set_title("Link utilization: low RE vs high RE")
ax.legend(fontsize=8, ncol=2)

plt.tight_layout()
plt.savefig(outdir / f"week_analysis_link_utilization_{tag}.png", dpi=300)
plt.close()