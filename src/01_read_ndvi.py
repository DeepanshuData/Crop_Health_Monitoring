
import rasterio
import numpy as np
from pathlib import Path

# Step 1: Define the satellite image path
raster_path = Path("data") / "Mysuru_NDVI_2024.tif"

# Step 2: Open the GeoTIFF file
with rasterio.open(raster_path) as src:

    # Step 3: Read NDVI band as a masked array
    ndvi = src.read(1, masked=True)

    # Step 4: Calculate NDVI statistics
    print("Minimum NDVI:", ndvi.min())
    print("Maximum NDVI:", ndvi.max())
    print("Mean NDVI:", ndvi.mean())
    print("Median NDVI:", np.ma.median(ndvi))
    print("Standard Deviation:", ndvi.std())

    # Step 5: Count valid pixels
    valid_pixels = ndvi.count()

    # Step 6: Count pixels with positive NDVI
    positive_pixels = np.ma.sum(ndvi > 0)

    # Step 7: Calculate positive NDVI percentage
    positive_percentage = (
        positive_pixels / valid_pixels
    ) * 100

    print("Total Valid Pixels:", valid_pixels)
    print("Positive NDVI Pixels:", positive_pixels)
    print("Positive NDVI Percentage:", positive_percentage)

