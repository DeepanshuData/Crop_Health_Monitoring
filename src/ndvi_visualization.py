
import rasterio
import numpy as np
import matplotlib.pyplot as plt

# Read the calculated NDVI GeoTIFF
input_file = "outputs/ndvi_band_math/Mysuru_NDVI_20250201.tif"

with rasterio.open(input_file) as src:
    ndvi = src.read(1)

# Exclude NoData pixels
valid_ndvi = np.ma.masked_equal(ndvi, -9999)

# Create NDVI visualization
plt.figure(figsize=(10, 8))

plt.imshow(
    valid_ndvi,
    cmap="RdYlGn",
    vmin=-1,
    vmax=1
)

plt.colorbar(label="NDVI")
plt.title("Sentinel-2 NDVI - Mysuru (01 February 2025)")
plt.xlabel("Column")
plt.ylabel("Row")

plt.tight_layout()

# Save graph
output_file = "outputs/ndvi_band_math/graphs/Mysuru_NDVI_Map.png"

plt.savefig(output_file, dpi=300)
plt.show()

print("NDVI visualization saved:", output_file)

