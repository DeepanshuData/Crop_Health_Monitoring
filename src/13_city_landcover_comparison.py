
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Create output folders
os.makedirs("outputs/results", exist_ok=True)
os.makedirs("outputs/graphs", exist_ok=True)

# Calculate mean indices by city and land-cover class
city_comparison = (
    df.groupby(["City", "Land_Cover"])[["NDVI", "NDRE", "NDWI"]]
    .mean()
    .round(4)
)

print("\nCITY-WISE LAND-COVER INDEX COMPARISON")
print(city_comparison)

# Save results
city_comparison.to_csv(
    "outputs/results/city_landcover_index_comparison.csv"
)

# Generate one graph per index
for index in ["NDVI", "NDRE", "NDWI"]:

    plot_data = city_comparison[index].unstack()

    plot_data.plot(
        kind="bar",
        figsize=(11, 6),
        edgecolor="black"
    )

    plt.title(f"City-wise {index} Comparison")
    plt.xlabel("City")
    plt.ylabel(index)
    plt.xticks(rotation=0)
    plt.legend(title="Land Cover")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    plt.savefig(
        f"outputs/graphs/city_landcover_{index}.png",
        dpi=300
    )

    plt.show()

print("\nCity-wise land-cover comparison completed!")

