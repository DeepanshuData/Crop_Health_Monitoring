
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Calculate mean NDVI by city and land-cover class
ndvi_comparison = (
    df.groupby(["City", "Land_Cover"])["NDVI"]
    .mean()
    .unstack()
    .round(4)
)

print("\nCITY-WISE LAND-COVER NDVI ANALYSIS")
print(ndvi_comparison)

# Save results
os.makedirs("outputs/results", exist_ok=True)
ndvi_comparison.to_csv(
    "outputs/results/city_landcover_ndvi.csv"
)

# Create grouped bar chart
ax = ndvi_comparison.plot(
    kind="bar",
    figsize=(11, 6),
    edgecolor="black"
)

ax.set_title("City-wise NDVI Comparison by Land-Cover Class")
ax.set_xlabel("City")
ax.set_ylabel("Mean NDVI")
ax.tick_params(axis="x", rotation=0)
ax.legend(title="Land Cover")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()

plt.savefig(
    "outputs/graphs/city_landcover_ndvi.png",
    dpi=300
)

plt.show()

print("\nCity-wise NDVI analysis completed!")

