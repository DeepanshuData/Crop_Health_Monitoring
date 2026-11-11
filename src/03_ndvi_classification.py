
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Step 1: Define raster path
raster_path = Path("data") / "Mysuru_NDVI_2024.tif"

# Step 2: Read NDVI raster
with rasterio.open(raster_path) as src:
    ndvi = src.read(1, masked=True)

# Step 3: Create an empty classification array
classification = np.zeros(ndvi.shape, dtype=np.uint8)

# Step 4: Assign vegetation classes
classification[(ndvi >= 0) & (ndvi < 0.2)] = 1
classification[(ndvi >= 0.2) & (ndvi < 0.4)] = 2
classification[(ndvi >= 0.4) & (ndvi < 0.6)] = 3
classification[ndvi >= 0.6] = 4

# Step 5: Preserve invalid pixels
classification = np.ma.array(
    classification,
    mask=np.ma.getmaskarray(ndvi)
)

# Step 6: Count pixels in each class
print("NDVI VEGETATION CLASSIFICATION")
print("--------------------------------")

class_names = {
    0: "Water / Non-vegetation",
    1: "Bare / Sparse vegetation",
    2: "Low vegetation",
    3: "Moderate vegetation",
    4: "Dense vegetation"
}

total_pixels = ndvi.count()

for class_value, class_name in class_names.items():

    if class_value == 0:
        count = np.ma.sum(ndvi < 0)
    else:
        count = np.ma.sum(classification == class_value)

    percentage = (count / total_pixels) * 100

    print(
        class_name,
        ":",
        count,
        "pixels |",
        round(percentage, 2),
        "%"
    )

# Step 7: Visualize classification
plt.figure(figsize=(10, 8))

plt.imshow(
    classification,
    cmap="RdYlGn",
    vmin=0,
    vmax=4,
    interpolation="nearest"
)

plt.colorbar(
    ticks=[0, 1, 2, 3, 4],
    label="Vegetation Class"
)

plt.title("Mysuru Vegetation Classification - 2024")
plt.xlabel("Column (Pixels)")
plt.ylabel("Row (Pixels)")

plt.tight_layout()
plt.show()

