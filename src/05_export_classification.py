
import rasterio
import numpy as np
from pathlib import Path

from rasterio.warp import (
    calculate_default_transform,
    reproject,
    Resampling
)

# Step 1: Define input and output paths
input_path = Path("data") / "Mysuru_NDVI_2024.tif"
output_path = Path("outputs") / "Mysuru_Vegetation_Classification.tif"

# Step 2: Create output directory if needed
output_path.parent.mkdir(parents=True, exist_ok=True)

# Step 3: Open the original NDVI raster
with rasterio.open(input_path) as src:

    dst_crs = "EPSG:32643"

    # Calculate projected raster dimensions
    transform, width, height = calculate_default_transform(
        src.crs,
        dst_crs,
        src.width,
        src.height,
        *src.bounds
    )

    # Create destination array
    projected_ndvi = np.full(
        (height, width),
        np.nan,
        dtype=np.float32
    )

    # Reproject NDVI raster
    reproject(
        source=rasterio.band(src, 1),
        destination=projected_ndvi,
        src_transform=src.transform,
        src_crs=src.crs,
        src_nodata=src.nodata,
        dst_transform=transform,
        dst_crs=dst_crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest
    )

    # Step 4: Classify NDVI
    valid = np.isfinite(projected_ndvi)

    classification = np.zeros(
        projected_ndvi.shape,
        dtype=np.uint8
    )

    classification[valid & (projected_ndvi < 0)] = 0
    classification[valid & (projected_ndvi >= 0) &
                   (projected_ndvi < 0.2)] = 1
    classification[valid & (projected_ndvi >= 0.2) &
                   (projected_ndvi < 0.4)] = 2
    classification[valid & (projected_ndvi >= 0.4) &
                   (projected_ndvi < 0.6)] = 3
    classification[valid & (projected_ndvi >= 0.6)] = 4

    # Step 5: Save classification as GeoTIFF
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": dst_crs,
        "transform": transform,
        "nodata": 255,
        "compress": "lzw"
    }

    classification[~valid] = 255

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(classification, 1)

    print("Classification GeoTIFF exported successfully!")
    print("Output:", output_path)
    print("CRS:", dst_crs)
    print("Raster dimensions:", width, "x", height)

