
import pandas as pd

# Load dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Select Sentinel-2 spectral bands in wavelength order
spectral_bands = [
    "B2", "B3", "B4", "B5", "B6",
    "B7", "B8", "B8A", "B11", "B12"
]

# Display spectral band information
print("\nSPECTRAL BANDS")
print(spectral_bands)

# Calculate mean reflectance for each band
band_mean = df[spectral_bands].mean()

print("\nMEAN REFLECTANCE OF EACH BAND")
print(band_mean)

# Calculate mean reflectance by land-cover class
class_mean = df.groupby("Land_Cover")[spectral_bands].mean()

print("\nMEAN REFLECTANCE BY LAND-COVER CLASS")
print(class_mean)

