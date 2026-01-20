import pandas as pd
RE_PATH = "../Data/test/dk_res_potential_example_year.csv"
re_generators = pd.read_csv(RE_PATH, parse_dates=["timestamp_utc"])
re_generators = re_generators.set_index(["timestamp_utc", "region"]).sort_index()
re_cap_by_region = pd.DataFrame(
    {
        "onshore": re_generators["onshore_capacity_factor"],
        "offshore": re_generators["offshore_capacity_factor"],
        "solar": re_generators["solar_capacity_factor"],
    },
    index=re_generators.index
)
renewables = re_cap_by_region.columns
print(re_cap_by_region.head())