import pandas as pd
import matplotlib.pyplot as plt
import os

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Sentinel-2 spectral bands
spectral_bands = [
    "B2", "B3", "B4", "B5", "B6",
    "B7", "B8", "B8A", "B11", "B12"
]

# Calculate mean reflectance by land-cover class
class_mean = df.groupby("Land_Cover")[spectral_bands].mean()

# Create heatmap
plt.figure(figsize=(12, 5))

plt.imshow(class_mean, aspect="auto", cmap="YlGnBu")

# Add band labels
plt.xticks(
    range(len(spectral_bands)),
    spectral_bands
)

# Add land-cover labels
plt.yticks(
    range(len(class_mean.index)),
    class_mean.index
)

# Add color bar
plt.colorbar(label="Mean Surface Reflectance")

plt.title("Spectral Reflectance Heatmap")
plt.xlabel("Sentinel-2 Spectral Bands")
plt.ylabel("Land-Cover Classes")

plt.tight_layout()

# Save graph
os.makedirs("outputs/graphs", exist_ok=True)

plt.savefig(
    "outputs/graphs/spectral_heatmap.png",
    dpi=300
)

plt.show()

print("Spectral heatmap generated successfully!")
