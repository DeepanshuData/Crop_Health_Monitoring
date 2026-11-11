import pandas as pd
import matplotlib.pyplot as plt
import os

# Load calculated spectral indices
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Select indices
indices = ["NDVI", "NDRE", "NDWI"]

# Calculate mean indices for each city and land-cover class
city_index_mean = df.groupby(
    ["City", "Land_Cover"]
)[indices].mean()

# Display results
print("\nCITY-WISE SPECTRAL INDEX ANALYSIS")
print(city_index_mean.round(4))

# Create output folder
os.makedirs("outputs/graphs", exist_ok=True)

# Generate one graph for each index
for index in indices:

    plt.figure(figsize=(12, 6))

    index_data = city_index_mean[index].unstack()

    index_data.plot(
        kind="bar",
        figsize=(12, 6),
        width=0.8
    )

    plt.title(f"City-wise {index} Comparison")
    plt.xlabel("City")
    plt.ylabel(index + " Value")
    plt.xticks(rotation=0)
    plt.legend(title="Land-Cover Class")
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()

    plt.savefig(
        f"outputs/graphs/city_wise_{index}.png",
        dpi=300
    )

    plt.show()

print("\nCity-wise index graphs generated successfully!")
