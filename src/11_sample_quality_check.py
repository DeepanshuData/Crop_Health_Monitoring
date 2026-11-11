import pandas as pd

# Load dataset with calculated spectral indices
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Display water samples
water_samples = df[df["Land_Cover"] == "Water"].copy()

print("\nWATER SAMPLE QUALITY CHECK")
print(
    water_samples[
        ["City", "Area_m2", "NDVI", "NDRE", "NDWI"]
    ].round(4).to_string(index=False)
)

# Flag potentially unusual water samples
water_samples["Quality_Flag"] = "Review"

# Basic screening conditions, not definitive classification rules
water_samples.loc[
    (water_samples["NDWI"] > 0) &
    (water_samples["NDVI"] < 0.1),
    "Quality_Flag"
] = "Consistent with open-water response"

print("\nWATER SAMPLE SCREENING")
print(
    water_samples[
        ["City", "NDVI", "NDRE", "NDWI", "Quality_Flag"]
    ].round(4).to_string(index=False)
)

# Display samples requiring further investigation
print("\nSAMPLES REQUIRING REVIEW")
print(
    water_samples[
        water_samples["Quality_Flag"] == "Review"
    ][["City", "Area_m2", "NDVI", "NDRE", "NDWI"]]
    .round(4)
    .to_string(index=False)
)

print("\nSample quality screening completed!")

