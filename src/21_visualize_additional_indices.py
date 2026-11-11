
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ==========================================
# STEP 1: Define paths
# ==========================================

input_file = Path(
    "outputs/additional_indices/results/"
    "Mysuru_Six_Additional_Indices_20250201.tif"
)

maps_folder = Path("outputs/additional_indices/maps")
maps_folder.mkdir(parents=True, exist_ok=True)

# ==========================================
# STEP 2: Read six index bands
# ==========================================

with rasterio.open(input_file) as src:

    indices = {}

    for band_number in range(1, 7):

        name = src.descriptions[band_number - 1]

        data = src.read(band_number).astype("float32")

        if src.nodata is not None:
            data[data == src.nodata] = np.nan

        indices[name] = data

        print(f"{name} loaded successfully")

    transform = src.transform

    width = src.width
    height = src.height

# ==========================================
# STEP 3: Calculate map display limits
# ==========================================

display_limits = {}

for name, data in indices.items():

    valid_values = data[np.isfinite(data)]

    lower = np.percentile(valid_values, 2)
    upper = np.percentile(valid_values, 98)

    display_limits[name] = (lower, upper)

    print(
        f"{name}: Display range "
        f"{lower:.4f} to {upper:.4f}"
    )

# ==========================================
# STEP 4: Define index colors
# ==========================================

color_maps = {
    "EVI": "RdYlGn",
    "GNDVI": "RdYlGn",
    "NDMI": "BrBG",
    "MSI": "YlOrRd",
    "SAVI": "RdYlGn",
    "BSI": "RdYlBu_r"
}

# Calculate geographic extent
left = transform.c
top = transform.f
right = left + width * transform.a
bottom = top + height * transform.e

extent = [left, right, bottom, top]

# ==========================================
# STEP 5: Create six individual maps
# ==========================================

for name, data in indices.items():

    vmin, vmax = display_limits[name]

    fig, ax = plt.subplots(figsize=(9, 7))

    image = ax.imshow(
        data,
        cmap=color_maps[name],
        vmin=vmin,
        vmax=vmax,
        extent=extent
    )

    fig.colorbar(
        image,
        ax=ax,
        label=f"{name} Value",
        shrink=0.8
    )

    ax.set_title(
        f"Mysuru {name} Map - 2025-02-01",
        fontsize=14
    )

    ax.set_xlabel("Easting (metres)")
    ax.set_ylabel("Northing (metres)")

    ax.set_aspect("equal")

    plt.tight_layout()

    output_file = maps_folder / f"Mysuru_{name}_Map.png"

    plt.savefig(
        output_file,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print("Map saved:", output_file)

# ==========================================
# STEP 6: Create combined six-index map
# ==========================================

fig, axes = plt.subplots(
    2, 3,
    figsize=(18, 11)
)

for ax, (name, data) in zip(axes.flat, indices.items()):

    vmin, vmax = display_limits[name]

    image = ax.imshow(
        data,
        cmap=color_maps[name],
        vmin=vmin,
        vmax=vmax,
        extent=extent
    )

    ax.set_title(name, fontsize=13)
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")

    fig.colorbar(
        image,
        ax=ax,
        fraction=0.046,
        pad=0.04
    )

fig.suptitle(
    "Six Spectral Indices - Mysuru - 1 February 2025",
    fontsize=17
)

plt.tight_layout()

combined_file = maps_folder / "Mysuru_Combined_Six_Indices.png"

plt.savefig(
    combined_file,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print("\nAll six individual maps created!")
print("Combined map saved:", combined_file)



