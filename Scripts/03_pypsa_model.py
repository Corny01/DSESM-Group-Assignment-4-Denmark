import pypsa
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pypsa.common import annuity
import plotly.io as pio
import plotly.offline as py

###########################################
# INPUT
###########################################
boolean_zero_emission = 0 #yes=1; no=0

max_power_links = pd.DataFrame(
    {
        "Nordjylland_Midtjylland": 2000, #in MW per link
        "Midtjylland_Syddanmark": 2000,
        "Syddanmark_Sjælland": 2000,
        "Sjælland_Hovedstaden": 2000,
        "Sjælland_Midtjylland": 2000,
        "Midtjylland_Hovedstaden": 2000,
    },
    index=[0]
)

cost_projection_year = 2030 #choose from years 2020, 2025, 2030, 2035, 2040, 2045, 2050
cost_reduction_factor = pd.DataFrame(
    {
        "coal": 0, #in %
        "oil": 0,
        "gas": 0,
        "biomass": 0,
        "solar": 0,
        "onwind": 0,
        "offwind": 0,
    },
    index=[0]
)

RE_potential_reduction_factor = pd.DataFrame( #reducec amximum potential for one technologyin all regions
    {
        "solar": 0, #in %
        "onwind": 0,
        "offwind": 0,
    },
    index=[0]
)

boolean_nuclear_plants = 0 #yes=1; no=0
nuclear_capex = 2500    #capex of nuclear plants in €/kW

weather_year = 2018 #choose from

###########################################
# PATHS
###########################################

PP_PATH = "../Data/processed/dk_powerplants_with_region.csv"  # die Datei aus der vorherigen Aufgabe
COSTS_PATH = f"../Data/processed/costs_{cost_projection_year}.csv"
C_PATH ="../Data/processed/region_centroids_wsg.csv"
LOAD_PATH = "../Data/processed/load_regions.csv"
RE_PATH = "../Data/test/dk_res_potential_example_year.csv" #testing data -> insert weather_year
RE_P_PATH ="../Data/test/dk_res_max_potential_by_region.csv" #testing data

###########################################
# Loading and preprocessing of data
###########################################

########################    BUSES_CARRIERS     ########################

loads = pd.read_csv(LOAD_PATH, parse_dates=["time"])
loads = loads.set_index("time")

conv_generators = pd.read_csv(PP_PATH)
cap_by_region_fuel = (
    conv_generators.groupby(["NAME_1", "primary_fuel"], as_index=True)["capacity_mw"]
      .sum()
      .to_frame(name="capacity_mw")
)
conventionals = conv_generators["primary_fuel"].unique().tolist()

########################  TESTING_DATA   ########################

re_generators = pd.read_csv(RE_PATH, parse_dates=["timestamp"])
re_generators = re_generators.set_index(["timestamp", "region"]).sort_index()
re_cap_by_region = pd.DataFrame(
    {
        "onwind": re_generators["cf_onshore"],
        "offwind": re_generators["cf_offshore"],
        "solar": re_generators["cf_solar"],
    },
    index=re_generators.index
)
renewables = list(re_cap_by_region.columns)

re_potential = pd.read_csv(RE_P_PATH)
re_potential = re_potential.set_index("region")
re_potential.columns = renewables

########################  TESTING_DATA   ########################

carriers = sorted(set(conventionals + renewables + ["transmission", "AC", "battery storage", "hydrogen storage underground"]))

centroids = pd.read_csv(C_PATH)
regions = centroids.region
costs = pd.read_csv(COSTS_PATH, index_col=[0])

########################    LINKS     ########################
neighbors = [
    ("Nordjylland", "Midtjylland"),
    ("Nordjylland", "Hovedstaden_West"),
    ("Nordjylland", "Sjælland"),
    ("Midtjylland", "Syddanmark"),
    ("Midtjylland", "Sjælland"),
    ("Syddanmark", "Sjælland"),
    ("Sjælland", "Hovedstaden_West"),
    ("Sjælland", "Hovedstaden_East"),
    ("Hovedstaden_West", "Hovedstaden_East"),
]
gcent = gpd.GeoDataFrame(
    centroids,
    geometry=gpd.points_from_xy(centroids["lon"], centroids["lat"]),
    crs="EPSG:4326",
)
gcent_m = gcent.to_crs("EPSG:3035").set_index("region")
COST_PER_KM = 0
len_factor = 1.5

########################    BATTERIES     ########################
e_to_p_ratio_battery = [2, 4, 6]
e_to_p_ratio_hydrogen = [168, 336, 672]

##################################################################
#######################    PYPSA_MODEL     #######################
##################################################################

n = pypsa.Network()
n.set_snapshots(loads.index)

n.add(
    "Carrier",
    carriers,
    color=[
        "green",
        "tomato",
        "dimgrey",
        "black",
        "rosybrown",
        "pink",
        "violet",
        "crimson",
        "crimson",
        "yellow",
        "blue"
    ],
    co2_emissions=[
        costs.at[c, "CO2 intensity"] if c in costs.index else 0 for c in carriers
    ],
)

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
            continue #just add existing generators
        n.add(
            "Generator",
            f"{r}_{c}",
            bus=r,
            carrier=c,
            p_nom =cap_by_region_fuel.at[(r, c), "capacity_mw"],
            capital_cost=costs.at[c, "capital_cost"],
            marginal_cost=costs.at[c, "marginal_cost"],
            efficiency=costs.at[c, "efficiency"],
            p_nom_extendable=True,
        )

for re in renewables:
    for r in regions:
        n.add(
            "Generator",
            f"{r}_{re}",
            bus=r,
            carrier=re,
            p_nom_max=re_potential.loc[r, re],
            #p_max_pu=re_cap_by_region.loc[(slice(None), r), re].droplevel("region"),
            capital_cost=costs.at[re, "capital_cost"],
            marginal_cost=costs.at[re, "marginal_cost"],
            efficiency=costs.at[re, "efficiency"],
            p_nom_extendable=True,
        )

for region in loads.columns:
    if region == "DK":
        continue  #skip sum over all regions

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
        p_nom_extendable=True,
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

if boolean_zero_emission == 1:
    n.add(
        "GlobalConstraint",
        "emission_limit",
        carrier_attribute="co2_emissions",
        sense="<=",
        constant=0,
    )

n.optimize(log_to_console=False, solver_name='gurobi')