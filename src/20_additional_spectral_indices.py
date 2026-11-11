
import rasterio
import numpy as np
import pandas as pd
from pathlib import Path

# ==========================================
# STEP 1: Define file paths
# ==========================================

input_file = Path(
    "data/additional_indices/Mysuru_Additional_Index_Bands_20250201.tif"
)

output_folder = Path("outputs/additional_indices")
results_folder = output_folder / "results"

results_folder.mkdir(parents=True, exist_ok=True)

# ==========================================
# STEP 2: Read Sentinel-2 bands
# ==========================================

with rasterio.open(input_file) as src:

    blue = src.read(1).astype("float32") / 10000.0
    green = src.read(2).astype("float32") / 10000.0
    red = src.read(3).astype("float32") / 10000.0
    nir = src.read(4).astype("float32") / 10000.0
    swir1 = src.read(5).astype("float32") / 10000.0

    profile = src.profile.copy()

print("Image loaded successfully")
print("Image shape:", blue.shape)


# ==========================================
# STEP 3: Apply QA60 cloud mask
# ==========================================

from rasterio.warp import reproject, Resampling

qa60_file = Path(
    "data/qa60_cloud_masking/Mysuru_QA60_20250201.tif"
)

# Read QA60 and align it with the spectral bands
with rasterio.open(qa60_file) as qa_src:

    qa60_aligned = np.zeros(
        blue.shape,
        dtype="uint16"
    )

    reproject(
        source=rasterio.band(qa_src, 1),
        destination=qa60_aligned,
        src_transform=qa_src.transform,
        src_crs=qa_src.crs,
        dst_transform=profile["transform"],
        dst_crs=profile["crs"],
        resampling=Resampling.nearest
    )

# Identify opaque clouds and cirrus clouds
opaque_clouds = (qa60_aligned & (1 << 10)) != 0
cirrus_clouds = (qa60_aligned & (1 << 11)) != 0

cloud_mask = opaque_clouds | cirrus_clouds

# Identify valid spectral pixels
valid_spectral_pixels = (
    (blue > 0) &
    (green > 0) &
    (red > 0) &
    (nir > 0) &
    (swir1 > 0)
)

# Exclude cloud pixels
valid_pixels = valid_spectral_pixels & ~cloud_mask

print("\n--- QA60 Cloud Mask Results ---")
print("Total pixels:", blue.size)
print("Cloud pixels:", np.sum(cloud_mask))
print("Clear pixels:", np.sum(~cloud_mask))
print("Cloud percentage:", round(np.mean(cloud_mask) * 100, 2), "%")

print("\n--- Valid Pixel Results ---")
print("Valid pixels after cloud masking:", np.sum(valid_pixels))
print("Invalid pixels:", np.sum(~valid_pixels))


# ==========================================
# STEP 4: Calculate six spectral indices
# ==========================================

def calculate_index(numerator, denominator):

    result = np.full(blue.shape, np.nan, dtype="float32")

    valid = valid_pixels & (np.abs(denominator) > 1e-10)

    np.divide(
        numerator,
        denominator,
        out=result,
        where=valid
    )

    return result


# 1. EVI - Enhanced Vegetation Index

evi_denominator = nir + (6 * red) - (7.5 * blue) + 1

evi = np.full(blue.shape, np.nan, dtype="float32")

evi_valid = (
    valid_pixels &
    (evi_denominator > 0.2)
)


np.divide(
    2.5 * (nir - red),
    evi_denominator,
    out=evi,
    where=evi_valid
)

# EVI diagnostic checks

print("\n--- EVI Quality Check ---")

print("Minimum EVI denominator:", np.min(evi_denominator[evi_valid]))
print("Maximum EVI denominator:", np.max(evi_denominator[evi_valid]))

print("EVI values above 1:", np.sum(evi > 1))
print("EVI values below -1:", np.sum(evi < -1))

print("EVI valid pixels:", np.sum(np.isfinite(evi)))
print("EVI excluded pixels:", np.sum(~np.isfinite(evi)))


# Inspect the pixel with maximum EVI

max_position = np.nanargmax(evi)

row, col = np.unravel_index(max_position, evi.shape)

print("\n--- Maximum EVI Pixel Details ---")

print("Row:", row)
print("Column:", col)

print("Blue:", blue[row, col])
print("Green:", green[row, col])
print("Red:", red[row, col])
print("NIR:", nir[row, col])

print("EVI denominator:", evi_denominator[row, col])
print("EVI value:", evi[row, col])

# ==========================================
# Check QA60 cloud flags at maximum EVI pixel
# ==========================================

from rasterio.warp import reproject, Resampling

qa60_file = "data/qa60_cloud_masking/Mysuru_QA60_20250201.tif"

with rasterio.open(qa60_file) as qa_src:

    qa60_aligned = np.zeros(
        blue.shape,
        dtype="uint16"
    )

    reproject(
        source=rasterio.band(qa_src, 1),
        destination=qa60_aligned,
        src_transform=qa_src.transform,
        src_crs=qa_src.crs,
        dst_transform=profile["transform"],
        dst_crs=profile["crs"],
        resampling=Resampling.nearest
    )

qa_value = qa60_aligned[row, col]

opaque_cloud = (qa_value & (1 << 10)) != 0
cirrus_cloud = (qa_value & (1 << 11)) != 0

print("\n--- QA60 Cloud Check ---")
print("QA60 value:", qa_value)
print("Opaque cloud flag:", opaque_cloud)
print("Cirrus cloud flag:", cirrus_cloud)
print("Cloud detected:", opaque_cloud or cirrus_cloud)



# 2. GNDVI - Green Normalized Difference Vegetation Index
gndvi = calculate_index(
    nir - green,
    nir + green
)


# 3. NDMI - Normalized Difference Moisture Index
ndmi = calculate_index(
    nir - swir1,
    nir + swir1
)


# 4. MSI - Moisture Stress Index
msi = calculate_index(
    swir1,
    nir
)


# 5. SAVI - Soil Adjusted Vegetation Index
L = 0.5

savi = calculate_index(
    (nir - red) * (1 + L),
    nir + red + L
)


# 6. BSI - Bare Soil Index
bsi = calculate_index(
    (swir1 + red) - (nir + blue),
    (swir1 + red) + (nir + blue)
)

# ==========================================
# EVI DISTRIBUTION ANALYSIS
# ==========================================

evi_values = evi[np.isfinite(evi)]

print("\n--- EVI Percentile Analysis ---")

for percentile in [1, 5, 25, 50, 75, 95, 99, 99.5, 100]:

    value = np.percentile(evi_values, percentile)

    print(f"{percentile}th percentile: {value:.4f}")

print("Pixels with EVI above 1:", np.sum(evi_values > 1))
print("Pixels with EVI below -1:", np.sum(evi_values < -1))



# ==========================================
# STEP 5: Store all indices
# ==========================================

indices = {
    "EVI": evi,
    "GNDVI": gndvi,
    "NDMI": ndmi,
    "MSI": msi,
    "SAVI": savi,
    "BSI": bsi
}

# ==========================================
# STEP 6: Calculate statistical summary
# ==========================================

statistics = []

for name, index in indices.items():

    values = index[np.isfinite(index)]

    statistics.append({
        "Index": name,
        "Minimum": np.min(values),
        "Maximum": np.max(values),
        "Mean": np.mean(values),
        "Standard_Deviation": np.std(values),
        "Valid_Pixels": len(values)
    })

    print(
        f"{name}: Min={np.min(values):.4f}, "
        f"Max={np.max(values):.4f}, "
        f"Mean={np.mean(values):.4f}"
    )

# ==========================================
# STEP 7: Save statistical results
# ==========================================

stats_df = pd.DataFrame(statistics)

stats_file = results_folder / "additional_indices_statistics.csv"

stats_df.to_csv(stats_file, index=False)

print("\nStatistical summary saved:", stats_file)

# ==========================================
# STEP 8: Save six indices as GeoTIFF
# ==========================================

profile.update(
    driver="GTiff",
    count=6,
    dtype="float32",
    nodata=-9999.0,
    compress="lzw"
)

output_file = results_folder / "Mysuru_Six_Additional_Indices_20250201.tif"

with rasterio.open(output_file, "w", **profile) as dst:

    for band_number, (name, index) in enumerate(indices.items(), start=1):

        output_array = np.where(
            np.isfinite(index),
            index,
            -9999.0
        ).astype("float32")

        dst.write(output_array, band_number)
        dst.set_band_description(band_number, name)

print("\nAll six indices calculated successfully!")
print("GeoTIFF saved:", output_file)



