
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Calculate mean NDRE by city and land-cover class
ndre_comparison = (
    df.groupby(["City", "Land_Cover"])["NDRE"]
    .mean()
    .unstack()
    .round(4)
)

print("\nCITY-WISE LAND-COVER NDRE ANALYSIS")
print(ndre_comparison)

# Save results
os.makedirs("outputs/results", exist_ok=True)
ndre_comparison.to_csv(
    "outputs/results/city_landcover_ndre.csv"
)

# Create grouped bar chart
ax = ndre_comparison.plot(
    kind="bar",
    figsize=(11, 6),
    edgecolor="black"
)

ax.set_title("City-wise NDRE Comparison by Land-Cover Class")
ax.set_xlabel("City")
ax.set_ylabel("Mean NDRE")
ax.tick_params(axis="x", rotation=0)
ax.legend(title="Land Cover")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()

plt.savefig(
    "outputs/graphs/city_landcover_ndre.png",
    dpi=300
)

plt.show()

print("\nCity-wise NDRE analysis completed!")
