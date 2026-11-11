
import rasterio
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Step 1: Define raster path
raster_path = Path("data") / "Mysuru_NDVI_2024.tif"

# Step 2: Open the raster
with rasterio.open(raster_path) as src:

    # Read NDVI values
    ndvi = src.read(1, masked=True)

# Step 3: Create the map
plt.figure(figsize=(10, 8))

plt.imshow(
    ndvi,
    cmap="RdYlGn",
    vmin=-0.2,
    vmax=0.8
)

# Step 4: Add color bar
plt.colorbar(label="NDVI Value")

# Step 5: Add title
plt.title("Mysuru NDVI Map - 2024")

# Step 6: Add axis labels
plt.xlabel("Column (Pixels)")
plt.ylabel("Row (Pixels)")

# Step 7: Display map
plt.tight_layout()
plt.show()

