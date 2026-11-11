
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Calculate mean NDWI by city and land-cover class
ndwi_comparison = (
    df.groupby(["City", "Land_Cover"])["NDWI"]
    .mean()
    .unstack()
    .round(4)
)

print("\nCITY-WISE LAND-COVER NDWI ANALYSIS")
print(ndwi_comparison)

# Save results
os.makedirs("outputs/results", exist_ok=True)

ndwi_comparison.to_csv(
    "outputs/results/city_landcover_ndwi.csv"
)

# Create grouped bar chart
ax = ndwi_comparison.plot(
    kind="bar",
    figsize=(11, 6),
    edgecolor="black"
)

ax.set_title("City-wise NDWI Comparison by Land-Cover Class")
ax.set_xlabel("City")
ax.set_ylabel("Mean NDWI")
ax.tick_params(axis="x", rotation=0)
ax.legend(title="Land Cover")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()

# Save graph
os.makedirs("outputs/graphs", exist_ok=True)

plt.savefig(
    "outputs/graphs/city_landcover_ndwi.png",
    dpi=300
)

plt.show()

print("\nCity-wise NDWI analysis completed!")

