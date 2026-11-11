import pandas as pd
import matplotlib.pyplot as plt
import os

# Load dataset containing calculated indices
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Indices to visualize
indices = ["NDVI", "NDRE", "NDWI"]

# Calculate mean index values by land-cover class
index_mean = df.groupby("Land_Cover")[indices].mean()

# Create output folder
os.makedirs("outputs/graphs", exist_ok=True)

# Create separate graph for each index
for index in indices:

    plt.figure(figsize=(8, 5))

    index_mean[index].plot(
        kind="bar",
        width=0.6
    )

    plt.title(f"{index} Comparison Across Land-Cover Classes")
    plt.xlabel("Land-Cover Class")
    plt.ylabel(index + " Value")
    plt.xticks(rotation=0)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()

    plt.savefig(
        f"outputs/graphs/{index}_comparison.png",
        dpi=300
    )

    plt.show()

print("\nAll index comparison graphs generated successfully!")

