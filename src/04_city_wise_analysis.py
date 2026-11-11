import pandas as pd
import matplotlib.pyplot as plt

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Sentinel-2 spectral bands
spectral_bands = [
    "B2", "B3", "B4", "B5", "B6",
    "B7", "B8", "B8A", "B11", "B12"
]

# Calculate average reflectance for each city and land-cover class
city_mean = df.groupby(
    ["City", "Land_Cover"]
)[spectral_bands].mean()

# Display results
print("\nCITY-WISE SPECTRAL REFLECTANCE")
print(city_mean)

# Create one graph for each city
cities = df["City"].unique()

for city in cities:

    city_data = city_mean.loc[city]

    plt.figure(figsize=(10, 5))

    for land_cover in city_data.index:

        plt.plot(
            spectral_bands,
            city_data.loc[land_cover],
            marker="o",
            linewidth=2,
            label=land_cover
        )

    plt.title(f"Spectral Signatures - {city}")
    plt.xlabel("Sentinel-2 Spectral Bands")
    plt.ylabel("Mean Surface Reflectance")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()

    plt.savefig(
        f"outputs/graphs/{city}_spectral_signature.png",
        dpi=300
    )

    plt.show()
    