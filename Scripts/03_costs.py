import pandas as pd
from pypsa.common import annuity

###########################################
# INPUT
###########################################

year = 2030

###########################################
# PATHS
###########################################

PP_PATH = "../Data/raw/powerplants/global_power_plant_database.csv"
TECH_PATH = f"../Data/raw/costs/costs_{year}.csv"
OUT_PATH = f"../Data/processed/costs_{year}.csv"

###########################################
# Load + convert data and fill null values
###########################################

costs = pd.read_csv(TECH_PATH, index_col=[0, 1])
costs.loc[costs.unit.str.contains("/kW"), "value"] *= 1e3
costs.unit = costs.unit.str.replace("/kW", "/MW")

defaults = {
    "FOM": 0,
    "VOM": 0,
    "efficiency": 1,
    "fuel": 0,
    "investment": 0,
    "lifetime": 25,
    "CO2 intensity": 0,
    "discount rate": 0.07,
}
costs = costs.value.unstack().fillna(defaults)

###########################################
# Calculate marginal and capital costs for each technology
###########################################

#costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]
#costs.at["CCGT", "fuel"] = costs.at["gas", "fuel"]
#costs.at["OCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]
#costs.at["CCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]

annuity(0.07, 20)
costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]
annuity_factor = annuity(costs["discount rate"], costs["lifetime"])
costs["capital_cost"] = (annuity_factor + costs["FOM"] / 100) * costs["investment"]

###########################################
# Save data
###########################################

costs.to_csv(OUT_PATH)