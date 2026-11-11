
import pandas as pd
import matplotlib.pyplot as plt

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Sentinel-2 bands in wavelength order
spectral_bands = [
    "B2", "B3", "B4", "B5", "B6",
    "B7", "B8", "B8A", "B11", "B12"
]

# Calculate average reflectance by land-cover class
class_mean = df.groupby("Land_Cover")[spectral_bands].mean()

# Create spectral signature graph
plt.figure(figsize=(12, 6))

for land_cover in class_mean.index:
    plt.plot(
        spectral_bands,
        class_mean.loc[land_cover],
        marker="o",
        linewidth=2,
        label=land_cover
    )

# Graph labels and formatting
plt.title("Spectral Signatures of Three Land-Cover Classes")
plt.xlabel("Sentinel-2 Spectral Bands")
plt.ylabel("Mean Surface Reflectance")
plt.legend()
plt.grid(True, linestyle="--", alpha=0.5)

plt.tight_layout()

# Save graph
plt.savefig(
    "outputs/graphs/spectral_signature.png",
    dpi=300
)

# Display graph
plt.show()

