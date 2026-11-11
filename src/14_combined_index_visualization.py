
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Calculate city-wise mean indices
city_means = (
    df.groupby("City")[["NDVI", "NDRE", "NDWI"]]
    .mean()
)

print("\nCOMBINED CITY-WISE INDEX VALUES")
print(city_means.round(4))

# Create output directory
os.makedirs("outputs/graphs", exist_ok=True)

# Create combined visualization
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

indices = ["NDVI", "NDRE", "NDWI"]

for ax, index in zip(axes, indices):

    city_means[index].plot(
        kind="bar",
        ax=ax,
        edgecolor="black"
    )

    ax.set_title(f"City-wise {index}")
    ax.set_xlabel("City")
    ax.set_ylabel(index)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)

plt.suptitle(
    "Combined City-wise Spectral Index Comparison",
    fontsize=15
)

plt.tight_layout()

# Save combined graph
plt.savefig(
    "outputs/graphs/combined_city_index_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print("\nCombined index visualization completed!")

