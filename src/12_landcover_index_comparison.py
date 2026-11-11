
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Calculate mean indices for each land-cover class
class_means = (
    df.groupby("Land_Cover")[["NDVI", "NDRE", "NDWI"]]
    .mean()
    .round(4)
)

print("\nLAND-COVER INDEX COMPARISON")
print(class_means)

# Save results
os.makedirs("outputs/results", exist_ok=True)
class_means.to_csv(
    "outputs/results/landcover_index_comparison.csv"
)

# Create comparison charts
os.makedirs("outputs/graphs", exist_ok=True)

for index in ["NDVI", "NDRE", "NDWI"]:
    plt.figure(figsize=(8, 5))

    class_means[index].plot(
        kind="bar",
        edgecolor="black"
    )

    plt.title(f"{index} Comparison Across Land-Cover Classes")
    plt.xlabel("Land-Cover Class")
    plt.ylabel(index)
    plt.xticks(rotation=0)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    plt.savefig(
        f"outputs/graphs/{index}_landcover_comparison.png",
        dpi=300
    )

    plt.show()

print("\nLand-cover index comparison completed!")

