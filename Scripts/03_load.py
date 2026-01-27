import pandas as pd

###########################################
# PATHS
###########################################

LD_PATH = "../Data/raw/load/load.csv"
OUT_PATH = "../Data/processed/load_regions.csv"

###########################################
# Load data
###########################################

load_total = pd.read_csv("../Data/raw/load/load.csv")
load_total["time"] = pd.to_datetime(load_total["time"])
load_total = load_total.set_index("time")
load_dk = load_total.loc[:, ["DK"]].copy()

###########################################
# Population Data from https://www.statbank.dk/INDAMP01
###########################################
population_total = {
    "Midtjylland": 1313596,
    "Nordjylland": 589148,
    "Sjælland":    835024,
    "Syddanmark":  1220763,
    "Hovedstaden_West": 1822659 - 39715,
    "Hovedstaden_East": 39715,
}

total_population = sum(population_total.values())

###########################################
# Divide load by region based on share of total population
###########################################

shares = {
    region: pop / total_population
    for region, pop in population_total.items()
}

for region, share in shares.items():
    load_dk[region] = load_dk["DK"] * share

load_dk.to_csv(OUT_PATH)




