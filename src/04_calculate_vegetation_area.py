
import rasterio
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from rasterio.warp import calculate_default_transform, reproject, Resampling

# Step 1: Define input raster
raster_path = Path("data") / "Mysuru_NDVI_2024.tif"

# Step 2: Open the original raster
with rasterio.open(raster_path) as src:

    # Get the new projected raster dimensions and transform
    dst_crs = "EPSG:32643"

    transform, width, height = calculate_default_transform(
        src.crs,
        dst_crs,
        src.width,
        src.height,
        *src.bounds
    )

    # Create an output array
    ndvi_projected = np.full(
        (height, width),
        np.nan,
        dtype=np.float32
    )

    # Reproject NDVI values
    reproject(
        source=rasterio.band(src, 1),
        destination=ndvi_projected,
        src_transform=src.transform,
        src_crs=src.crs,
        src_nodata=src.nodata,
        dst_transform=transform,
        dst_crs=dst_crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest
    )

# Step 3: Create vegetation classification
classification = np.zeros(
    ndvi_projected.shape,
    dtype=np.uint8
)

valid = np.isfinite(ndvi_projected)

classification[valid & (ndvi_projected >= 0) &
               (ndvi_projected < 0.2)] = 1

classification[valid & (ndvi_projected >= 0.2) &
               (ndvi_projected < 0.4)] = 2

classification[valid & (ndvi_projected >= 0.4) &
               (ndvi_projected < 0.6)] = 3

classification[valid & (ndvi_projected >= 0.6)] = 4

# Step 4: Calculate pixel area
pixel_area = abs(transform.a * transform.e)

# Convert square metres to hectares
pixel_area_hectares = pixel_area / 10000

# Step 5: Calculate area for each class
class_names = {
    0: "Water / Non-vegetation",
    1: "Bare / Sparse vegetation",
    2: "Low vegetation",
    3: "Moderate vegetation",
    4: "Dense vegetation"
}

print("VEGETATION AREA ANALYSIS")
print("------------------------")
print("Pixel area:", round(pixel_area, 2), "square metres")

for class_value, class_name in class_names.items():

    if class_value == 0:
        continue

    pixel_count = np.sum(
        valid & (classification == class_value)
    )

    area_hectares = pixel_count * pixel_area_hectares

    print(
        class_name,
        ":",
        pixel_count,
        "pixels |",
        round(area_hectares, 2),
        "hectares"
    )

# Step 6: Display projected classification map
plt.figure(figsize=(10, 8))

plt.imshow(
    np.ma.masked_where(~valid, classification),
    cmap="RdYlGn",
    vmin=0,
    vmax=4
)

plt.colorbar(
    ticks=[0, 1, 2, 3, 4],
    label="Vegetation Class"
)

plt.title("Mysuru Vegetation Area Classification")
plt.xlabel("Column (Pixels)")
plt.ylabel("Row (Pixels)")

plt.tight_layout()
plt.show()

