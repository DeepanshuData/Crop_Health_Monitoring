import pandas as pd
import numpy as np
import os

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Calculate NDVI
df["NDVI"] = (
    (df["B8"] - df["B4"]) /
    (df["B8"] + df["B4"])
)

# Calculate NDRE
df["NDRE"] = (
    (df["B8A"] - df["B5"]) /
    (df["B8A"] + df["B5"])
)

# Calculate NDWI
df["NDWI"] = (
    (df["B3"] - df["B8"]) /
    (df["B3"] + df["B8"])
)

# Display calculated indices
print("\nSPECTRAL INDICES")
print(df[["City", "Land_Cover", "NDVI", "NDRE", "NDWI"]].round(4))

# Calculate average indices by land-cover class
index_mean = df.groupby("Land_Cover")[
    ["NDVI", "NDRE", "NDWI"]
].mean()

print("\nAVERAGE INDICES BY LAND-COVER CLASS")
print(index_mean.round(4))

# Create results folder
os.makedirs("outputs/results", exist_ok=True)

# Save results
df.to_csv(
    "outputs/results/spectral_indices.csv",
    index=False
)

index_mean.to_csv(
    "outputs/results/mean_spectral_indices.csv"
)

print("\nSpectral indices calculated and saved successfully!")
