"""Create NoData-aware maps from downloaded NDVI date-comparison rasters."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from gee.config import OUTPUT_DIR, PROJECT_ROOT
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Patch

DEFAULT_RASTERS = {
    "first": PROJECT_ROOT / "outputs" / "NDVI_First_Date.tif",
    "second": PROJECT_ROOT / "outputs" / "NDVI_Second_Date.tif",
    "change": PROJECT_ROOT / "outputs" / "NDVI_Change_Map.tif",
}


def read_layer(path):
    with rasterio.open(path) as source:
        if source.count != 1 or source.crs is None:
            raise ValueError(f"{path} must be a single-band georeferenced raster.")
        data = np.ma.masked_invalid(source.read(1, masked=True))
        grid = (
            source.width,
            source.height,
            source.crs,
            source.transform,
        )
        return data, source.bounds, grid, source.crs.is_projected


def save_map(name, data, bounds, path, projected):
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("#d9d9d9")
    if name in ("first", "second"):
        plot_options = {"cmap": cmap, "vmin": -1, "vmax": 1}
        colorbar_label = "NDVI"
    else:
        maximum = float(np.max(np.abs(data.compressed())))
        limit = max(maximum, 0.05)
        plot_options = {
            "cmap": cmap,
            "norm": TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
        }
        colorbar_label = "NDVI change"

    left, bottom, right, top = bounds
    fig, axis = plt.subplots(figsize=(8, 7))
    plotted = axis.imshow(
        data,
        extent=(left, right, bottom, top),
        origin="upper",
        interpolation="nearest",
        **plot_options,
    )
    colorbar = fig.colorbar(plotted, ax=axis, shrink=0.82)
    colorbar.set_label(colorbar_label)
    axis.legend(
        handles=[Patch(facecolor="#d9d9d9", label="No valid observation")],
        loc="upper right",
        framealpha=0.9,
    )
    axis.set_title(f"{name.title()} NDVI" if name != "change" else "NDVI change")
    axis.set_xlabel("Easting (m)" if projected else "Longitude")
    axis.set_ylabel("Northing (m)" if projected else "Latitude")
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("first", "second", "change"):
        parser.add_argument(f"--{key}", type=Path, default=DEFAULT_RASTERS[key])
    parser.add_argument("--district", default="local")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR / "charts",
    )
    args = parser.parse_args(argv)
    paths = {key: getattr(args, key) for key in DEFAULT_RASTERS}
    layers = {key: read_layer(path) for key, path in paths.items()}
    reference_grid = layers["first"][2]
    for name, (_, _, grid, _) in layers.items():
        if grid != reference_grid:
            raise ValueError(f"{name} raster grid does not match the first-date grid.")
    for name, (data, _, _, _) in layers.items():
        if data.count() == 0:
            raise ValueError(f"{name} raster has no finite, valid pixels.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for name, (data, bounds, _, projected) in layers.items():
        output = args.output_dir / f"{args.district}_{name}_ndvi_{run_id}.png"
        save_map(name, data, bounds, output, projected)
        print(f"Saved {output}")


if __name__ == "__main__":
    main()
