
import rasterio
import numpy as np

# Step 1: Read the downloaded Sentinel-2 bands
input_file = "data/ndvi_band_math/Mysuru_NDVI_Bands_20250201.tif"

with rasterio.open(input_file) as src:
    red = src.read(1).astype(np.float32)  # B4 - Red
    nir = src.read(2).astype(np.float32)  # B8 - NIR

    profile = src.profile.copy()

# Step 2: Create a valid-pixel mask
valid_pixels = (red > 0) & (nir > 0)

# Step 3: Calculate NDVI manually
ndvi = np.full(red.shape, -9999, dtype=np.float32)

denominator = nir + red

np.divide(
    nir - red,
    denominator,
    out=ndvi,
    where=valid_pixels & (denominator != 0)
)

# Step 4: Calculate NDVI statistics
valid_ndvi = ndvi[ndvi != -9999]

print("NDVI Calculation Completed!")
print("Valid pixels:", valid_ndvi.size)
print("NDVI Minimum:", valid_ndvi.min())
print("NDVI Maximum:", valid_ndvi.max())
print("NDVI Mean:", valid_ndvi.mean())

# Step 5: Save the NDVI GeoTIFF
profile.update(
    count=1,
    dtype="float32",
    nodata=-9999
)

output_file = "outputs/ndvi_band_math/Mysuru_NDVI_20250201.tif"

with rasterio.open(output_file, "w", **profile) as dst:
    dst.write(ndvi, 1)

print("NDVI GeoTIFF saved:", output_file)

