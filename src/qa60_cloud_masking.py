
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

# ==========================================
# STEP 1: Define input file paths
# ==========================================

rgb_path = "data/qa60_cloud_masking/Mysuru_RGB_20250201.tif"
qa60_path = "data/qa60_cloud_masking/Mysuru_QA60_20250201.tif"

# ==========================================
# STEP 2: Read RGB image
# ==========================================

with rasterio.open(rgb_path) as rgb_src:
    rgb = rgb_src.read()
    rgb_profile = rgb_src.profile.copy()
    rgb_transform = rgb_src.transform
    rgb_crs = rgb_src.crs
    rgb_height = rgb_src.height
    rgb_width = rgb_src.width

print("RGB image shape:", rgb.shape)
print("RGB resolution:", rgb_src.res)

# ==========================================
# STEP 3: Read QA60 image
# ==========================================

with rasterio.open(qa60_path) as qa_src:
    qa60 = qa_src.read(1)

    print("Original QA60 shape:", qa60.shape)
    print("QA60 resolution:", qa_src.res)

# ==========================================
# STEP 4: Align QA60 with RGB image
# ==========================================

qa60_aligned = np.zeros(
    (rgb_height, rgb_width),
    dtype=qa60.dtype
)

reproject(
    source=qa60,
    destination=qa60_aligned,
    src_transform=qa_src.transform,
    src_crs=qa_src.crs,
    dst_transform=rgb_transform,
    dst_crs=rgb_crs,
    resampling=Resampling.nearest
)

print("Aligned QA60 shape:", qa60_aligned.shape)
print("RGB and QA60 images are now aligned.")


# ==========================================
# STEP 5: Identify cloud pixels using QA60
# ==========================================

# Bit 10 = Opaque clouds
# Bit 11 = Cirrus clouds

opaque_clouds = (qa60_aligned & (1 << 10)) != 0
cirrus_clouds = (qa60_aligned & (1 << 11)) != 0

# Combine both cloud conditions
cloud_mask = opaque_clouds | cirrus_clouds

# Clear pixels are pixels without cloud flags
clear_mask = ~cloud_mask

# ==========================================
# STEP 6: Apply cloud mask to RGB image
# ==========================================

rgb_masked = rgb.copy()

# Set cloud pixels to NoData (0)
rgb_masked[:, cloud_mask] = 0

# ==========================================
# STEP 7: Calculate cloud statistics
# ==========================================

total_pixels = cloud_mask.size
cloud_pixels = np.count_nonzero(cloud_mask)
clear_pixels = np.count_nonzero(clear_mask)

cloud_percentage = (cloud_pixels / total_pixels) * 100
clear_percentage = (clear_pixels / total_pixels) * 100

print("\n----- CLOUD MASKING RESULTS -----")
print("Total pixels:", total_pixels)
print("Cloud pixels:", cloud_pixels)
print("Clear pixels:", clear_pixels)
print("Cloud percentage:", round(cloud_percentage, 2), "%")
print("Clear percentage:", round(clear_percentage, 2), "%")


# ==========================================
# STEP 8: Visualize before and after masking
# ==========================================

import matplotlib.pyplot as plt

# Convert RGB arrays from (bands, height, width)
# to (height, width, bands)
rgb_before = np.moveaxis(rgb, 0, -1)
rgb_after = np.moveaxis(rgb_masked, 0, -1)

# Scale reflectance values for display
rgb_before_display = np.clip(rgb_before / 3000, 0, 1)
rgb_after_display = np.clip(rgb_after / 3000, 0, 1)

# Create comparison figure
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].imshow(rgb_before_display)
axes[0].set_title("Before Cloud Masking")
axes[0].axis("off")

axes[1].imshow(rgb_after_display)
axes[1].set_title("After QA60 Cloud Masking")
axes[1].axis("off")

plt.suptitle("Sentinel-2 Cloud Masking - Mysuru (01 Feb 2025)")
plt.tight_layout()

# Save comparison graph
plt.savefig(
    "outputs/qa60_cloud_masking/graphs/"
    "before_after_cloud_masking.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print("\nComparison graph saved successfully.")


# ==========================================
# STEP 9: Save masked RGB GeoTIFF
# ==========================================

output_path = (
    "outputs/qa60_cloud_masking/results/"
    "Mysuru_RGB_Cloud_Masked_20250201.tif"
)

# Update the original RGB metadata
rgb_profile.update(
    count=3,
    dtype="uint16",
    compress="lzw",
    nodata=0
)

# Save the masked satellite image
with rasterio.open(output_path, "w", **rgb_profile) as dst:
    dst.write(rgb_masked.astype("uint16"))

print("\nMasked GeoTIFF saved successfully:")
print(output_path)

