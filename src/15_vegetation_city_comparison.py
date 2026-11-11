
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load spectral index data
df = pd.read_csv("outputs/results/spectral_indices.csv")

# Select only vegetation samples
vegetation = df[df["Land_Cover"] == "Vegetation"].copy()

# Calculate mean indices for each city
vegetation_means = (
    vegetation.groupby("City")[["NDVI", "NDRE"]]
    .mean()
    .round(4)
)

print("\nVEGETATION-ONLY CITY COMPARISON")
print(vegetation_means)

# Save results
os.makedirs("outputs/results", exist_ok=True)
vegetation_means.to_csv(
    "outputs/results/vegetation_city_comparison.csv"
)

# Create comparison graph
ax = vegetation_means.plot(
    kind="bar",
    figsize=(10, 6),
    edgecolor="black"
)

ax.set_title("Vegetation Index Comparison Across Cities")
ax.set_xlabel("City")
ax.set_ylabel("Index Value")
ax.tick_params(axis="x", rotation=0)
ax.grid(axis="y", alpha=0.3)
ax.legend(title="Spectral Index")

plt.tight_layout()

plt.savefig(
    "outputs/graphs/vegetation_city_comparison.png",
    dpi=300
)

plt.show()

print("\nVegetation city comparison completed!")

