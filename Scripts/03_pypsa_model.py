import pypsa
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pypsa.common import annuity
import plotly.io as pio
import plotly.offline as py

pd.options.plotting.backend = "plotly"

PP_PATH = "../Data/processed/dk_powerplants_with_region.csv"  # die Datei aus der vorherigen Aufgabe
COSTS_PATH = "../Data/processed/costs.csv"
C_PATH ="../Data/processed/region_centroids.csv"
LOAD_PATH = "../Data/processed/load_regions.csv"

generators = pd.read_csv(PP_PATH)
cap_by_region_fuel = (
    generators.groupby(["NAME_1", "primary_fuel"], as_index=True)["capacity_mw"]
      .sum()
      .to_frame(name="capacity_mw")
)

centroids = pd.read_csv(C_PATH)
costs = pd.read_csv(COSTS_PATH, index_col=[0])
regions = centroids.region
conventionals = generators["primary_fuel"].unique().tolist()

loads = pd.read_csv(LOAD_PATH, parse_dates=["time"])
loads = loads.set_index("time")

neighbors = [
    ("Nordjylland", "Midtjylland"),
    ("Midtjylland", "Syddanmark"),
    ("Syddanmark", "Sjælland"),
    ("Sjælland", "Hovedstaden"),
    ("Sjælland", "Midtjylland"),
    ("Midtjylland", "Hovedstaden"),
]
gcent = gpd.GeoDataFrame(
    centroids,
    geometry=gpd.points_from_xy(centroids["lon"], centroids["lat"]),
    crs="EPSG:4326",
)
gcent_m = gcent.to_crs("EPSG:3035").set_index("region")
COST_PER_KM = 0
len_factor = 1.5

e_to_p_ratio_battery = [2, 4, 6]
e_to_p_ratio_hydrogen = [168, 336, 672]

n = pypsa.Network()
n.set_snapshots(loads.index)

all_carriers = sorted(set(conventionals + ["transmission", "AC", "battery storage", "hydrogen storage underground"]))
n.add("Carrier", all_carriers)

for _,row in centroids.iterrows():
    n.add(
        "Bus",
        name=row["region"],
        x=row["lon"],
        y=row["lat"],
        carrier="AC"
    )

for c in conventionals:
    for r in regions:
        if (r, c) not in cap_by_region_fuel.index:
            continue
        n.add(
            "Generator",
            f"{r}_{c}",
            bus=r,
            carrier=c,
            p_max_pu=cap_by_region_fuel.at[(r, c), "capacity_mw"],
            capital_cost=costs.at[c, "capital_cost"],
            marginal_cost=costs.at[c, "marginal_cost"],
            efficiency=costs.at[c, "efficiency"],
            p_nom_extendable=True,
        )

for region in loads.columns:
    if region == "DK":
        continue  #not for the national value

    n.add(
        "Load",
        name=f"load_{region}",
        bus=region,
        p_set=loads[region],
    )

for r0, r1 in neighbors:
    p0 = gcent_m.loc[r0, "geometry"]
    p1 = gcent_m.loc[r1, "geometry"]
    length_km = p0.distance(p1) * len_factor / 1000.0
    capital_cost = COST_PER_KM * length_km

    n.add(
        "Link",
        f"{r0}_{r1}",
        bus0=r0,
        bus1=r1,
        carrier="transmission",
        p_nom_max=2000,
        efficiency=1.0,
        capital_cost=capital_cost,
    )

for e in e_to_p_ratio_battery:
    for r in regions:
        n.add(
            "StorageUnit",
            f"Battery_{r}_{e}",
            bus=r,
            carrier="battery storage",
            max_hours=e,
            capital_cost=costs.at["battery inverter", "capital_cost"]
                         + e * costs.at["battery storage", "capital_cost"],
            efficiency_store=costs.at["battery inverter", "efficiency"],
            efficiency_dispatch=costs.at["battery inverter", "efficiency"],
            p_nom_extendable=True,
            cyclic_state_of_charge=True,
        )

for e in e_to_p_ratio_hydrogen:
    for r in regions:
        n.add(
            "StorageUnit",
            f"HydrogenStorage_{r}_{e}",
            bus=r,
            carrier="hydrogen storage underground",
            max_hours=e,
            capital_cost=costs.at["electrolysis", "capital_cost"]
                        + costs.at["fuel cell", "capital_cost"]
                        + e * costs.at["hydrogen storage underground", "capital_cost"],
            efficiency_store=costs.at["electrolysis", "efficiency"],
            efficiency_dispatch=costs.at["fuel cell", "efficiency"],
            p_nom_extendable=True,
            cyclic_state_of_charge=True,
        )
n.optimize(log_to_console=False)

#n.loads_t.p_set.plot(labels=dict(value="Load (MW)")).show()

colors = {
    'biomass': "green",
    'gas': "tomato",
    'coal': "dimgrey",
    'oil': "black",
    "AC": "crimson",
    "transmission": "crimson",
    "battery storage": "yellow",
    "hydrogen storage underground": "blue"
}
n.add("Carrier", colors.keys(), color=colors.values(), overwrite=True)
#n.generators.p_nom_opt.div(1e3)  # GW
#n.statistics.energy_balance.iplot().show()
#capacities = n.generators.groupby(["bus", "carrier"]).p_nom_opt.sum()
#bus_size = capacities.groupby(level=0).sum()
#m = n.explore(bus_size=bus_size / 3)
#m.to_html("network_map.html")