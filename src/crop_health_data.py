"""Reusable loading and visualization helpers for verified crop-health rasters."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.io import MemoryFile
from rasterio.transform import rowcol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_RASTER = Path("data/sentinel2_complete_bands/Mysuru_Sentinel2_6_Bands.tif")
INDEX_RASTER_DIR = Path("outputs/all_7_indices/geotiff")
STATISTICS_CSV = Path("outputs/all_7_indices/index_statistics.csv")

INDEX_DETAILS: dict[str, dict[str, str]] = {
    "NDVI": {
        "full_name": "Normalized Difference Vegetation Index",
        "formula": "(B8 - B4) / (B8 + B4)",
        "bands": "B8 (Near Infrared), B4 (Red)",
        "purpose": "Canopy greenness and relative vegetation vigor.",
        "interpretation": "Higher values generally indicate stronger green vegetation response; this is not a crop diagnosis.",
        "colormap": "RdYlGn",
    },
    "EVI": {
        "full_name": "Enhanced Vegetation Index",
        "formula": "2.5 × (B8 - B4) / (B8 + 6 × B4 - 7.5 × B2 + 1)",
        "bands": "B8 (Near Infrared), B4 (Red), B2 (Blue)",
        "purpose": "Vegetation response with reduced soil and atmospheric influence.",
        "interpretation": "Compare canopy response while observing the denominator stability mask; no values are clipped.",
        "colormap": "RdYlGn",
    },
    "GNDVI": {
        "full_name": "Green Normalized Difference Vegetation Index",
        "formula": "(B8 - B3) / (B8 + B3)",
        "bands": "B8 (Near Infrared), B3 (Green)",
        "purpose": "Green-band vegetation response related to vigor and chlorophyll.",
        "interpretation": "Compare relative green-band canopy response within the scene.",
        "colormap": "RdYlGn",
    },
    "NDRE": {
        "full_name": "Normalized Difference Red Edge",
        "formula": "(B8 - B5) / (B8 + B5)",
        "bands": "B8 (Near Infrared), B5 (Red Edge 1)",
        "purpose": "Red-edge response related to canopy chlorophyll and stress.",
        "interpretation": "Useful for comparing denser canopies; values are not a confirmed stress diagnosis.",
        "colormap": "RdYlGn",
    },
    "NDMI": {
        "full_name": "Normalized Difference Moisture Index",
        "formula": "(B8 - B11) / (B8 + B11)",
        "bands": "B8 (Near Infrared), B11 (Shortwave Infrared 1)",
        "purpose": "Relative canopy moisture variation.",
        "interpretation": "Compare moisture response within this scene; this is distinct from McFeeters NDWI.",
        "colormap": "BrBG",
    },
    "MSI": {
        "full_name": "Moisture Stress Index",
        "formula": "B11 / B8",
        "bands": "B11 (Shortwave Infrared 1), B8 (Near Infrared)",
        "purpose": "Relative vegetation moisture-stress ratio.",
        "interpretation": "Larger values commonly correspond to drier vegetation, but do not confirm crop stress.",
        "colormap": "YlOrRd",
    },
    "SAVI": {
        "full_name": "Soil Adjusted Vegetation Index",
        "formula": "1.5 × (B8 - B4) / (B8 + B4 + 0.5)",
        "bands": "B8 (Near Infrared), B4 (Red)",
        "purpose": "Vegetation greenness with reduced soil-background influence.",
        "interpretation": "Useful for relative comparisons where vegetation cover is sparse.",
        "colormap": "RdYlGn",
    },
    "NDWI": {
        "full_name": "Normalized Difference Water Index (McFeeters)",
        "formula": "(B3 - B8) / (B3 + B8)",
        "bands": "B3 (Green), B8 (Near Infrared)",
        "purpose": "Surface-water spectral contrast using green and near-infrared reflectance.",
        "interpretation": "This is the McFeeters NDWI variant, not NDMI. It can highlight open water; it is not a crop-moisture diagnosis.",
        "colormap": "BrBG",
    },
}
INDEX_NAMES = ("NDVI", "EVI", "GNDVI", "NDRE", "NDMI", "MSI", "SAVI", "NDWI")
EXPECTED_BANDS = ("B2", "B3", "B4", "B5", "B8", "B11")
NODATA_VALUE = -9999.0
REFLECTANCE_SCALE = 10000.0
EVI_DENOMINATOR_THRESHOLD = 0.1
BAND_DETAILS = {
    "B2": ("Blue", "Atmospheric-sensitive visible band used in EVI."),
    "B3": ("Green", "Visible green band used by GNDVI and McFeeters NDWI."),
    "B4": ("Red", "Chlorophyll absorption band used by NDVI, EVI, and SAVI."),
    "B5": ("Red Edge 1", "Red-edge band used by NDRE for canopy response."),
    "B8": ("Near Infrared", "Strong vegetation-reflectance band used in most indices."),
    "B11": ("Shortwave Infrared 1", "Moisture-sensitive band used by NDMI and MSI."),
}


def _safe_ratio(
    numerator: np.ndarray,
    denominator: np.ndarray,
    valid_mask: np.ndarray,
) -> np.ndarray:
    result = np.full(denominator.shape, np.nan, dtype=np.float32)
    safe_pixels = (
        valid_mask
        & np.isfinite(numerator)
        & np.isfinite(denominator)
        & (denominator != 0)
    )
    np.divide(numerator, denominator, out=result, where=safe_pixels)
    result[~np.isfinite(result)] = np.nan
    return result


def calculate_ndwi(green: np.ndarray, nir: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """Calculate McFeeters NDWI from green and NIR reflectance."""
    return _safe_ratio(green - nir, green + nir, valid_mask)


def calculate_indices_from_reflectance(
    reflectance: dict[str, np.ndarray],
    valid_mask: np.ndarray,
) -> dict[str, np.ndarray]:
    """Calculate all eight index arrays without clipping scientific values."""
    blue = reflectance["B2"]
    green = reflectance["B3"]
    red = reflectance["B4"]
    red_edge = reflectance["B5"]
    nir = reflectance["B8"]
    swir1 = reflectance["B11"]

    evi_denominator = nir + 6 * red - 7.5 * blue + 1
    evi_valid = valid_mask & (
        np.abs(evi_denominator) >= EVI_DENOMINATOR_THRESHOLD
    )

    return {
        "NDVI": _safe_ratio(nir - red, nir + red, valid_mask),
        "EVI": _safe_ratio(2.5 * (nir - red), evi_denominator, evi_valid),
        "GNDVI": _safe_ratio(nir - green, nir + green, valid_mask),
        "NDRE": _safe_ratio(nir - red_edge, nir + red_edge, valid_mask),
        "NDMI": _safe_ratio(nir - swir1, nir + swir1, valid_mask),
        "MSI": _safe_ratio(swir1, nir, valid_mask),
        "SAVI": _safe_ratio(1.5 * (nir - red), nir + red + 0.5, valid_mask),
        "NDWI": calculate_ndwi(green, nir, valid_mask),
    }


def _index_statistics(name: str, values: np.ndarray) -> dict[str, float | int | str]:
    valid_values = values[np.isfinite(values)]
    if valid_values.size == 0:
        raise ValueError(f"{name} has no valid pixels.")
    return {
        "Index Name": name,
        "Minimum": float(np.min(valid_values)),
        "Maximum": float(np.max(valid_values)),
        "Mean": float(np.mean(valid_values)),
        "Median": float(np.median(valid_values)),
        "Standard Deviation": float(np.std(valid_values, ddof=0)),
        "Valid Pixel Count": int(valid_values.size),
        "Invalid Pixel Count": int(values.size - valid_values.size),
    }


def load_verified_scene(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Load verified Mysuru index rasters and derive bands, NDWI and metadata."""
    project_root = Path(project_root).resolve()
    source_path = project_root / SOURCE_RASTER
    if not source_path.is_file():
        raise FileNotFoundError(f"Verified input raster not found: {source_path}")

    with rasterio.open(source_path) as source:
        if source.count != len(EXPECTED_BANDS):
            raise ValueError(f"Expected six source bands, found {source.count}.")
        if source.descriptions != EXPECTED_BANDS:
            raise ValueError(
                f"Expected band order {EXPECTED_BANDS}, found {source.descriptions}."
            )
        if source.crs is None:
            raise ValueError("The source raster has no CRS definition.")
        if not all(np.isclose(size, 20.0) for size in source.res):
            raise ValueError(f"Expected 20 m pixels, found {source.res}.")

        source_bands = source.read(masked=True).astype(np.float32)
        source_masks = np.ma.getmaskarray(source_bands)
        raw_bands = source_bands.filled(np.nan)
        profile = source.profile.copy()
        transform = source.transform
        source_crs = source.crs
        bounds = tuple(source.bounds)
        dimensions = (source.width, source.height)
        resolution = source.res
        source_tags = source.tags()
        source_nodata = source.nodata

    reflectance_stack = raw_bands / REFLECTANCE_SCALE
    reflectance = {
        name: reflectance_stack[number]
        for number, name in enumerate(EXPECTED_BANDS)
    }
    valid_mask = (
        ~np.any(source_masks, axis=0)
        & np.all(np.isfinite(reflectance_stack), axis=0)
        & np.all(reflectance_stack > 0, axis=0)
    )

    indices: dict[str, np.ndarray] = {}
    statistics: dict[str, dict[str, float | int | str]] = {}
    for name in INDEX_NAMES[:-1]:
        index_path = project_root / INDEX_RASTER_DIR / f"{name}.tif"
        if not index_path.is_file():
            raise FileNotFoundError(f"Verified index GeoTIFF not found: {index_path}")
        with rasterio.open(index_path) as index_raster:
            if (
                index_raster.crs != source_crs
                or index_raster.transform != transform
                or (index_raster.width, index_raster.height) != dimensions
                or index_raster.dtypes != ("float32",)
                or index_raster.nodata != NODATA_VALUE
                or index_raster.descriptions != (name,)
            ):
                raise ValueError(f"{index_path.name} does not match the source raster grid.")
            indices[name] = index_raster.read(1, masked=True).filled(np.nan).astype(
                np.float32
            )
        statistics[name] = _index_statistics(name, indices[name])

    indices["NDWI"] = calculate_ndwi(
        reflectance["B3"], reflectance["B8"], valid_mask
    )
    statistics["NDWI"] = _index_statistics("NDWI", indices["NDWI"])

    statistics_path = project_root / STATISTICS_CSV
    if not statistics_path.is_file():
        raise FileNotFoundError(f"Verified statistics CSV not found: {statistics_path}")
    notebook_statistics = pd.read_csv(statistics_path)
    for row in notebook_statistics.to_dict(orient="records"):
        name = row["Index Name"]
        if name not in statistics:
            continue
        for column, key in (
            ("Minimum", "Minimum"),
            ("Maximum", "Maximum"),
            ("Mean", "Mean"),
            ("Median", "Median"),
            ("Standard Deviation", "Standard Deviation"),
            ("Valid Pixel Count", "Valid Pixel Count"),
            ("Invalid Pixel Count", "Invalid Pixel Count"),
        ):
            actual = statistics[name][key]
            expected = row[column]
            if isinstance(actual, float):
                if not np.isclose(actual, float(expected), rtol=1e-6, atol=1e-7):
                    raise ValueError(
                        f"Statistics CSV disagrees with verified {name} raster ({column})."
                    )
            elif int(actual) != int(expected):
                raise ValueError(
                    f"Statistics CSV disagrees with verified {name} raster ({column})."
                )

    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    raster_corners = [
        transform * (0, 0),
        transform * (dimensions[0], 0),
        transform * (dimensions[0], dimensions[1]),
        transform * (0, dimensions[1]),
    ]
    geographic_corners = [transformer.transform(x, y) for x, y in raster_corners]
    west = min(point[0] for point in geographic_corners)
    east = max(point[0] for point in geographic_corners)
    south = min(point[1] for point in geographic_corners)
    north = max(point[1] for point in geographic_corners)

    return {
        "project_root": project_root,
        "study_area": "Mysuru, Karnataka, India",
        "acquisition_date": "2025-02-06",
        "collection": "COPERNICUS/S2_SR_HARMONIZED",
        "input_path": source_path,
        "source_profile": profile,
        "source_crs": source_crs,
        "source_transform": transform,
        "source_bounds": bounds,
        "geographic_bounds": [[south, west], [north, east]],
        "geographic_corners": geographic_corners,
        "dimensions": dimensions,
        "resolution": resolution,
        "source_nodata": source_nodata,
        "cloud_metadata": source_tags.get("CLOUDY_PIXEL_PERCENTAGE"),
        "raw_bands": {
            name: raw_bands[number]
            for number, name in enumerate(EXPECTED_BANDS)
        },
        "reflectance": reflectance,
        "valid_mask": valid_mask,
        "indices": indices,
        "statistics": statistics,
        "base_valid_pixels": int(np.count_nonzero(valid_mask)),
        "total_pixels": int(valid_mask.size),
    }


def statistics_frame(scene: dict[str, Any], names: tuple[str, ...] = INDEX_NAMES) -> pd.DataFrame:
    rows = []
    for name in names:
        row = dict(scene["statistics"][name])
        row["Full Name"] = INDEX_DETAILS[name]["full_name"]
        row["Formula"] = INDEX_DETAILS[name]["formula"]
        rows.append(row)
    return pd.DataFrame(rows)


def _stretch_band(band: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    valid_values = band[valid_mask & np.isfinite(band)]
    if valid_values.size == 0:
        raise ValueError("Band has no valid pixels for visualization.")
    low, high = np.percentile(valid_values, [2, 98])
    if np.isclose(low, high):
        high = low + max(abs(float(low)) * 0.01, 1e-6)
    return np.clip((band - low) / (high - low), 0.0, 1.0)


def composite_rgb(
    scene: dict[str, Any],
    band_names: tuple[str, str, str] = ("B4", "B3", "B2"),
) -> np.ndarray:
    """Create an 8-bit RGB composite using display-only percentile stretches."""
    channels = [
        _stretch_band(scene["reflectance"][name], scene["valid_mask"])
        for name in band_names
    ]
    rgb = np.stack(channels, axis=-1)
    invalid = ~scene["valid_mask"]
    rgb[invalid] = (0.84, 0.86, 0.84)
    return (rgb * 255).astype(np.uint8)


def index_rgba(scene: dict[str, Any], index_name: str) -> np.ndarray:
    if index_name not in INDEX_DETAILS:
        raise ValueError(f"Unsupported index: {index_name}")
    values = scene["indices"][index_name]
    valid_values = values[np.isfinite(values)]
    low, high = np.percentile(valid_values, [2, 98])
    if np.isclose(low, high):
        padding = max(abs(float(low)) * 0.01, 1e-6)
        low -= padding
        high += padding
    color_map = plt.get_cmap(INDEX_DETAILS[index_name]["colormap"]).copy()
    color_map.set_bad("#d9ddd9", alpha=1.0)
    return color_map(
        plt.Normalize(vmin=float(low), vmax=float(high))(
            np.ma.masked_invalid(values)
        ),
        bytes=True,
    )


def image_png(image: np.ndarray) -> bytes:
    output = io.BytesIO()
    Image.fromarray(image).save(output, format="PNG", optimize=True)
    return output.getvalue()


def index_geotiff_bytes(scene: dict[str, Any], index_name: str) -> bytes:
    if index_name not in INDEX_DETAILS:
        raise ValueError(f"Unsupported index: {index_name}")
    output_profile = scene["source_profile"].copy()
    output_profile.update(
        driver="GTiff",
        count=1,
        dtype="float32",
        nodata=NODATA_VALUE,
        compress="lzw",
    )
    data = np.where(
        np.isfinite(scene["indices"][index_name]),
        scene["indices"][index_name],
        NODATA_VALUE,
    ).astype(np.float32)
    with MemoryFile() as memory_file:
        with memory_file.open(**output_profile) as output:
            output.write(data, 1)
            output.set_band_description(1, index_name)
        return memory_file.read()


def pixel_at_lonlat(
    scene: dict[str, Any],
    longitude: float,
    latitude: float,
    index_name: str,
) -> dict[str, float | int | bool | None]:
    """Return a map click's source pixel and value when it falls inside the raster."""
    if index_name not in INDEX_DETAILS:
        raise ValueError(f"Unsupported index: {index_name}")
    transformer = Transformer.from_crs("EPSG:4326", scene["source_crs"], always_xy=True)
    x, y = transformer.transform(longitude, latitude)
    row, column = rowcol(scene["source_transform"], x, y)
    width, height = scene["dimensions"]
    if row < 0 or row >= height or column < 0 or column >= width:
        return {"inside": False, "valid": False, "row": int(row), "column": int(column)}
    value = scene["indices"][index_name][row, column]
    valid = bool(np.isfinite(value))
    return {
        "inside": True,
        "valid": valid,
        "row": int(row),
        "column": int(column),
        "easting": float(x),
        "northing": float(y),
        "value": float(value) if valid else None,
    }
