
import pandas as pd
import os

# Load spectral index dataset
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Define spectral indices
indices = ["NDVI", "NDRE", "NDWI"]

# Calculate class-wise statistical summary
summary = (
    df.groupby("Land_Cover")[indices]
    .agg(["count", "mean", "std", "min", "max"])
    .round(4)
)

print("\nFINAL CLASS-WISE STATISTICAL SUMMARY")
print(summary)

# Save class-wise summary
os.makedirs("outputs/results", exist_ok=True)

summary.to_csv(
    "outputs/results/final_class_statistical_summary.csv"
)

# Calculate city-wise statistics
city_summary = (
    df.groupby("City")[indices]
    .agg(["mean", "std", "min", "max"])
    .round(4)
)

print("\nFINAL CITY-WISE STATISTICAL SUMMARY")
print(city_summary)

# Save city-wise summary
city_summary.to_csv(
    "outputs/results/final_city_statistical_summary.csv"
)

print("\nFinal statistical summary completed!")

