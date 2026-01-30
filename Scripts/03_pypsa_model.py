import pypsa
import pandas as pd
import geopandas as gpd

###########################################
# INPUT
###########################################
boolean_conventionals_extendable = 1 #yes=1; no=0
boolean_zero_emission = 1 #yes=1; no=0

max_power_links = pd.DataFrame(
    {
        "Nordjylland_Midtjylland": 2000, #in MW per link
        "Nordjylland_Hovedstaden_West": 2000,
        "Nordjylland_Sjælland": 2000,
        "Midtjylland_Syddanmark": 2000,
        "Midtjylland_Sjælland": 2000,
        "Syddanmark_Sjælland": 2000,
        "Sjælland_Hovedstaden_West": 2000,
        "Sjælland_Hovedstaden_East": 2000,
        "Hovedstaden_West_Hovedstaden_East": 2000,
    },
    index=[0]
)

cost_projection_year = 2030 #choose from years 2020, 2025, 2030, 2035, 2040, 2045, 2050
cost_reduction_factor = pd.DataFrame(
    {
        "coal": 0, #in % #-> check for capex
        "oil": 0, #-> check for capex
        "gas": 0, #-> zu OCGT ändern
        "biomass": 0, #-> check for capex
        "solar": 0,
        "onwind": 0,
        "offwind": 0,
        "battery inverter": 0,
        "battery storage": 0,
        "electrolysis": 0,
        "hydrogen storage underground": 0,
        "fuel cell": 0,
        "HVAC overhead": 0,
        "HVDC submarine": 0
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
# Name sceario
###########################################

scenario = (
    f"ZE{boolean_zero_emission}"
    f"_CY{cost_projection_year}"
    f"_WY{weather_year}"
    f"_NUC{boolean_nuclear_plants}"
    f"_NRcapex{int(nuclear_capex)}"
    f"_CRF_s{int(cost_reduction_factor.at[0,'solar'])}"
    f"_CRF_on{int(cost_reduction_factor.at[0,'onwind'])}"
    f"_CRF_off{int(cost_reduction_factor.at[0,'offwind'])}"
    f"_PRF_s{int(RE_potential_reduction_factor.at[0,'solar'])}"
    f"_PRF_on{int(RE_potential_reduction_factor.at[0,'onwind'])}"
    f"_PRF_off{int(RE_potential_reduction_factor.at[0,'offwind'])}"
    f"_L{int(max_power_links.iloc[0].mean())}"
)
###########################################
# PATHS
###########################################

PP_PATH = "../Data/processed/dk_powerplants_with_region.csv"
COSTS_PATH = f"../Data/processed/costs_{cost_projection_year}.csv"
C_PATH ="../Data/processed/region_centroids_wsg.csv"
LOAD_PATH = "../Data/processed/load_regions.csv"
RE_PATH = "../Data/processed/dk_re_cf_timeseries_2013.csv"
RE_P_PATH ="../Data/processed/dk_re_max_potentials_by_region_2013.csv"

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

re_generators = pd.read_csv(RE_PATH, parse_dates=["timestamp"])
re_generators = re_generators.set_index(["timestamp", "region"]).sort_index()
re_cap_by_region = pd.DataFrame(
    {
        "onwind": re_generators["cf_onshore"],
        "offwind": re_generators["cf_offshore"],
        "solar": re_generators["cf_pv"],
    },
    index=re_generators.index
)

renewables = list(re_cap_by_region)

re_cap_by_region = re_cap_by_region.unstack("region")
re_cap_by_region.index.name = "time"
re_cap_by_region = re_cap_by_region.reindex(loads.index)

re_potential = pd.read_csv(RE_P_PATH)
re_potential = re_potential.set_index("region")
re_potential.columns = renewables

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

links_type = pd.DataFrame(
    {
        "Nordjylland_Midtjylland": "HVAC overhead",
        "Nordjylland_Hovedstaden_West": "HVDC submarine",
        "Nordjylland_Sjælland": "HVDC submarine",
        "Midtjylland_Syddanmark": "HVAC overhead",
        "Midtjylland_Sjælland": "HVDC submarine",
        "Syddanmark_Sjælland": "HVAC overhead",
        "Sjælland_Hovedstaden_West": "HVAC overhead",
        "Sjælland_Hovedstaden_East": "HVDC submarine",
        "Hovedstaden_West_Hovedstaden_East": "HVDC submarine",
    },
    index=[0]
)
gcent = gpd.GeoDataFrame(
    centroids,
    geometry=gpd.points_from_xy(centroids["lon"], centroids["lat"]),
    crs="EPSG:4326",
)
gcent_m = gcent.to_crs("EPSG:3035").set_index("region")
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
            continue  # skip non-existing generators
        n.add(
            "Generator",
            f"{r}_{c}",
            bus=r,
            carrier=c,
            p_nom_min =cap_by_region_fuel.at[(r, c), "capacity_mw"],
            capital_cost=costs.at[c, "capital_cost"] * (1-cost_reduction_factor[c].loc[0]),
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
            p_max_pu=re_cap_by_region[(re, r)],
            capital_cost=costs.at[re, "capital_cost"] * (1-cost_reduction_factor[re].loc[0]),
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
    if links_type[f"{r0}_{r1}"].iloc[0] == "HVAC overhead":
        capital_cost = costs.at["HVAC overhead", "capital_cost"] * length_km * (1-cost_reduction_factor["HVAC overhead"].loc[0])
    else:
        capital_cost = costs.at["HVDC submarine", "capital_cost"] * length_km * (1-cost_reduction_factor["HVDC submarine"].loc[0])

    n.add(
        "Link",
        f"{r0}_{r1}",
        bus0=r0,
        bus1=r1,
        carrier="transmission",
        p_nom_max=max_power_links[f"{r0}_{r1}"].iloc[0],
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
            capital_cost=costs.at["battery inverter", "capital_cost"] * (1-cost_reduction_factor["battery inverter"].loc[0])
                         + e * costs.at["battery storage", "capital_cost"] * (1-cost_reduction_factor["battery storage"].loc[0]),
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
            capital_cost=costs.at["electrolysis", "capital_cost"] * (1-cost_reduction_factor["electrolysis"].loc[0])
                        + costs.at["fuel cell", "capital_cost"] * (1-cost_reduction_factor["fuel cell"].loc[0])
                        + e * costs.at["hydrogen storage underground", "capital_cost"] * (1-cost_reduction_factor["hydrogen storage underground"].loc[0]),
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

n.optimize(assign_all_duals=True, log_to_console=False, solver_name='gurobi')
n.export_to_netcdf(f"../results/n_extendable_{scenario}.nc")