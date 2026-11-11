import pandas as pd
import os

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Sentinel-2 spectral bands
spectral_bands = [
    "B2", "B3", "B4", "B5", "B6",
    "B7", "B8", "B8A", "B11", "B12"
]

# Calculate statistics by land-cover class
statistics = df.groupby("Land_Cover")[spectral_bands].agg(
    ["mean", "std", "min", "max"]
)

# Display statistics
print("\nCLASS-WISE SPECTRAL STATISTICS")
print(statistics.round(4))

# Create results folder if it does not exist
os.makedirs("outputs/results", exist_ok=True)

# Save statistics to CSV
statistics.to_csv("outputs/results/class_statistics.csv")

print("\nStatistics saved successfully!")
