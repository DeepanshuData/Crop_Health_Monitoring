"""Load and validate the exported Mandya crop-health rasters and summaries."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANDYA_INDEX_NAMES = ("NDVI", "NDRE", "NDWI")
INDEX_COLORMAPS = {"NDVI": "RdYlGn", "NDRE": "RdYlGn", "NDWI": "BrBG"}
INDEX_DIRECTORY = Path("outputs/mandya_spectral_indices/geotiff")
MONTHLY_NDVI_FILE = Path("data/mandya_monthly_ndvi.csv")
WORKFLOW_SUMMARY_FILE = Path("data/mandya_ndvi_workflow_summary.json")


def _index_path(project_root: Path, index_name: str) -> Path:
    if index_name not in MANDYA_INDEX_NAMES:
        raise ValueError(f"Unsupported Mandya index: {index_name}")
    path = project_root / INDEX_DIRECTORY / f"Mandya_{index_name}.tif"
    if not path.is_file():
        raise FileNotFoundError(f"Mandya {index_name} GeoTIFF is missing: {path}")
    return path


def _raster_grid(source: rasterio.DatasetReader) -> dict[str, Any]:
    if source.count != 1:
        raise ValueError(f"{source.name} must contain one index band.")
    if source.crs is None:
        raise ValueError(f"{source.name} has no CRS.")
    if not all(math.isfinite(value) and value > 0 for value in source.res):
        raise ValueError(f"{source.name} has invalid spatial resolution: {source.res}.")
    return {
        "width": source.width,
        "height": source.height,
        "crs": source.crs,
        "transform": source.transform,
        "resolution": tuple(float(value) for value in source.res),
        "bounds": tuple(float(value) for value in source.bounds),
        "nodata": source.nodata,
    }


def _is_wgs84_geographic(crs: rasterio.crs.CRS) -> bool:
    return crs.is_geographic and "World Geodetic System 1984" in crs.to_wkt()


def _index_statistics(source: rasterio.DatasetReader) -> dict[str, float | int]:
    count = 0
    minimum = math.inf
    maximum = -math.inf
    total = 0.0
    for _, window in source.block_windows(1):
        block = source.read(1, window=window, masked=True).filled(np.nan)
        values = block[np.isfinite(block)]
        if values.size == 0:
            continue
        count += int(values.size)
        minimum = min(minimum, float(values.min()))
        maximum = max(maximum, float(values.max()))
        total += float(values.sum(dtype=np.float64))

    if count == 0:
        raise ValueError(f"{source.name} contains no finite, valid pixels.")
    return {
        "minimum": minimum,
        "maximum": maximum,
        "mean": total / count,
        "valid_pixels": count,
    }


def load_mandya_products(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Validate all selectable index rasters and return NDVI stats and grid metadata."""
    project_root = Path(project_root).resolve()
    paths = {name: _index_path(project_root, name) for name in MANDYA_INDEX_NAMES}
    grid: dict[str, Any] | None = None
    statistics: dict[str, float | int] | None = None

    for name, path in paths.items():
        try:
            with rasterio.open(path) as source:
                current_grid = _raster_grid(source)
                if not _is_wgs84_geographic(current_grid["crs"]):
                    raise ValueError(
                        f"{path.name} must use a WGS 84 geographic CRS for the existing Folium map."
                    )
                if grid is None:
                    grid = current_grid
                elif any(
                    current_grid[key] != grid[key]
                    for key in ("width", "height", "crs", "transform", "resolution")
                ):
                    raise ValueError(
                        f"{path.name} does not match the other Mandya index raster grids."
                    )
                if name == "NDVI":
                    statistics = _index_statistics(source)
        except rasterio.errors.RasterioError as error:
            raise ValueError(f"Unable to read Mandya {name} raster: {error}") from error

    if grid is None or statistics is None:
        raise ValueError("Mandya index rasters did not provide a usable NDVI grid.")
    grid["crs_label"] = "WGS 84 (geographic)"
    grid["total_pixels"] = int(grid["width"] * grid["height"])
    return {"grid": grid, "statistics": statistics}


def load_uploaded_ndvi_raster(geotiff_bytes: bytes) -> dict[str, Any]:
    """Analyze an uploaded Earth Engine NDVI GeoTIFF in memory without altering it."""
    if not geotiff_bytes:
        raise ValueError("The uploaded NDVI GeoTIFF is empty.")
    try:
        with MemoryFile(geotiff_bytes) as memory_file:
            with memory_file.open() as source:
                grid = _raster_grid(source)
                if not _is_wgs84_geographic(grid["crs"]):
                    raise ValueError("The uploaded NDVI GeoTIFF must use a WGS 84 geographic CRS.")
                statistics = _index_statistics(source)
    except rasterio.errors.RasterioError as error:
        raise ValueError(f"Unable to read the uploaded NDVI GeoTIFF: {error}") from error
    grid["crs_label"] = "WGS 84 (geographic)"
    grid["total_pixels"] = int(grid["width"] * grid["height"])
    return {"grid": grid, "statistics": statistics}


def read_mandya_index_overlay(
    index_name: str,
    project_root: Path = PROJECT_ROOT,
    max_dimension: int = 1000,
) -> dict[str, Any]:
    """Create a downsampled RGBA display image while retaining source raster bounds."""
    if max_dimension < 1:
        raise ValueError("The map preview size must be a positive integer.")
    path = _index_path(Path(project_root).resolve(), index_name)
    try:
        with rasterio.open(path) as source:
            grid = _raster_grid(source)
            if not _is_wgs84_geographic(grid["crs"]):
                raise ValueError(
                    f"{path.name} must use a WGS 84 geographic CRS for map display."
                )
            scale = min(1.0, max_dimension / max(source.width, source.height))
            out_height = max(1, round(source.height * scale))
            out_width = max(1, round(source.width * scale))
            preview = source.read(
                1,
                out_shape=(out_height, out_width),
                masked=True,
                resampling=Resampling.nearest,
            ).filled(np.nan)
    except rasterio.errors.RasterioError as error:
        raise ValueError(f"Unable to read Mandya {index_name} raster: {error}") from error

    valid = np.isfinite(preview)
    values = preview[valid]
    if values.size == 0:
        raise ValueError(f"Mandya {index_name} raster has no valid preview pixels.")
    display_min, display_max = np.percentile(values, [2, 98])
    if math.isclose(float(display_min), float(display_max)):
        padding = max(abs(float(display_min)) * 0.01, 1e-6)
        display_min -= padding
        display_max += padding

    color_map = plt.get_cmap(INDEX_COLORMAPS[index_name]).with_extremes(
        bad=(0, 0, 0, 0)
    )
    rgba = color_map(
        plt.Normalize(vmin=float(display_min), vmax=float(display_max))(
            np.ma.masked_invalid(preview)
        ),
        bytes=True,
    )
    rgba[~valid, 3] = 0
    west, south, east, north = grid["bounds"]
    return {
        "image": rgba,
        "bounds": [[south, west], [north, east]],
        "display_min": float(display_min),
        "display_max": float(display_max),
        "grid": grid,
    }


def load_mandya_monthly_ndvi(project_root: Path = PROJECT_ROOT) -> pd.DataFrame:
    """Load only the monthly means saved by the GEE notebook; do not fill gaps."""
    path = Path(project_root).resolve() / MONTHLY_NDVI_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Saved Mandya monthly NDVI values are missing: {path}")
    frame = pd.read_csv(path, dtype={"month": "string"})
    if list(frame.columns) != ["month", "mean_ndvi"] or frame.empty:
        raise ValueError("Mandya monthly NDVI data must contain month and mean_ndvi columns.")
    if frame["month"].duplicated().any():
        raise ValueError("Mandya monthly NDVI data contains duplicate months.")
    frame["month_date"] = pd.to_datetime(frame["month"], format="%Y-%m", errors="coerce")
    frame["mean_ndvi"] = pd.to_numeric(frame["mean_ndvi"], errors="coerce")
    if frame["month_date"].isna().any() or not np.isfinite(frame["mean_ndvi"]).all():
        raise ValueError("Mandya monthly NDVI data contains invalid dates or values.")
    return frame.sort_values("month_date").reset_index(drop=True)


def load_mandya_workflow_summary(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = Path(project_root).resolve() / WORKFLOW_SUMMARY_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Mandya GEE workflow summary is missing: {path}")
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Mandya GEE workflow summary is invalid JSON: {error.msg}.") from error
    required = {
        "district",
        "window_start",
        "window_end",
        "scene_count",
        "district_mean_date",
        "district_mean_ndvi_reduce_region",
        "district_mean_ndvi_reduce_regions",
        "district_reducer_scale_m",
    }
    if not required.issubset(summary):
        raise ValueError("Mandya GEE workflow summary is missing required fields.")
    return summary
