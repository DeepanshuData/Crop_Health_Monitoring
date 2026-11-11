
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Calculate mean indices by city and land-cover class
combined_analysis = (
    df.groupby(["City", "Land_Cover"])[["NDVI", "NDRE", "NDWI"]]
    .mean()
    .round(4)
)

print("\nCOMBINED CITY-WISE LAND-COVER INDEX ANALYSIS")
print(combined_analysis)

# Save combined statistical results
os.makedirs("outputs/results", exist_ok=True)

combined_analysis.to_csv(
    "outputs/results/combined_landcover_index_analysis.csv"
)

# Create output graph directory
os.makedirs("outputs/graphs", exist_ok=True)

# Create three comparison charts
fig, axes = plt.subplots(1, 3, figsize=(19, 7))

indices = ["NDVI", "NDRE", "NDWI"]

for ax, index in zip(axes, indices):

    plot_data = combined_analysis[index].unstack()

    plot_data.plot(
        kind="bar",
        ax=ax,
        edgecolor="black"
    )

    ax.set_title(f"{index} by City and Land Cover")
    ax.set_xlabel("City")
    ax.set_ylabel(index)
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Land Cover")
    ax.grid(axis="y", alpha=0.3)

plt.suptitle(
    "Combined Spectral Index Analysis Across Five Cities",
    fontsize=15
)

plt.tight_layout()

# Save combined visualization
plt.savefig(
    "outputs/graphs/combined_landcover_index_analysis.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print("\nCombined land-cover index analysis completed!")

