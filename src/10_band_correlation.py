import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Select Sentinel-2 spectral bands
spectral_bands = [
    "B2", "B3", "B4", "B5", "B6",
    "B7", "B8", "B8A", "B11", "B12"
]

# Calculate correlation matrix
correlation = df[spectral_bands].corr()

# Display correlation matrix
print("\nSPECTRAL BAND CORRELATION")
print(correlation.round(3))

# Create heatmap
plt.figure(figsize=(10, 8))

plt.imshow(
    correlation,
    cmap="coolwarm",
    vmin=-1,
    vmax=1
)

plt.xticks(range(len(spectral_bands)), spectral_bands)
plt.yticks(range(len(spectral_bands)), spectral_bands)

# Display correlation values
for i in range(len(spectral_bands)):
    for j in range(len(spectral_bands)):
        plt.text(
            j, i,
            f"{correlation.iloc[i, j]:.2f}",
            ha="center",
            va="center",
            fontsize=8
        )

plt.colorbar(label="Correlation Coefficient")

plt.title("Sentinel-2 Spectral Band Correlation")
plt.xlabel("Spectral Bands")
plt.ylabel("Spectral Bands")

plt.tight_layout()

# Save graph
os.makedirs("outputs/graphs", exist_ok=True)

plt.savefig(
    "outputs/graphs/band_correlation.png",
    dpi=300
)

plt.show()

print("\nBand correlation analysis completed successfully!")
