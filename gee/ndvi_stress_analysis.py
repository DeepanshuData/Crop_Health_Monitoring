"""Local, NoData-aware NDVI stress classification and area reporting."""

from pathlib import Path
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from gee.config import STRESS_THRESHOLD


def classify_stress(ndvi, valid, threshold=STRESS_THRESHOLD):
    """Classify valid pixels as 0/1 and leave all invalid cells as 255."""
    data = np.asarray(ndvi)
    valid_pixels = np.asarray(valid, dtype=bool) & np.isfinite(data)
    result = np.full(data.shape, 255, dtype=np.uint8)
    result[valid_pixels] = (data[valid_pixels] < threshold).astype(np.uint8)
    return result, valid_pixels


def calculate_stressed_area(ndvi_path, output_dir, district, threshold=STRESS_THRESHOLD):
    """Write a stress GeoTIFF, CSV report, and distribution chart."""
    ndvi_path = Path(ndvi_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ndvi_path) as source:
        if source.count != 1 or source.crs is None:
            raise ValueError("NDVI input must be a single-band georeferenced raster.")
        if not source.crs.is_projected:
            raise ValueError("Area calculations require a projected raster CRS.")
        data = source.read(1)
        valid = (source.read_masks(1) > 0) & np.isfinite(data)
        stress, valid = classify_stress(data, valid, threshold)
        transform = source.transform
        unit_factor = source.crs.linear_units_factor[1]
        pixel_area_m2 = abs(
            transform.a * transform.e - transform.b * transform.d
        ) * unit_factor**2
        if pixel_area_m2 <= 0:
            raise ValueError("Raster transform has a non-positive pixel area.")
        profile = source.profile.copy()
        width, height = source.width, source.height
        crs = source.crs

    total_pixels = width * height
    valid_count = int(valid.sum())
    stressed_count = int((stress == 1).sum())
    non_stressed_count = int((stress == 0).sum())
    nodata_count = total_pixels - valid_count
    if not valid_count:
        raise ValueError(f"No valid NDVI pixels found in {ndvi_path}.")
    values = {
        "district": district,
        "threshold": threshold,
        "total_pixels": total_pixels,
        "valid_pixels": valid_count,
        "stressed_pixels": stressed_count,
        "non_stressed_pixels": non_stressed_count,
        "nodata_pixels": nodata_count,
        "pixel_area_m2": pixel_area_m2,
        "valid_area_ha": valid_count * pixel_area_m2 / 10000,
        "stressed_area_ha": stressed_count * pixel_area_m2 / 10000,
        "non_stressed_area_ha": non_stressed_count * pixel_area_m2 / 10000,
        "stressed_percentage_valid": stressed_count / valid_count * 100,
        "crs": str(crs),
        "input_raster": str(ndvi_path),
    }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    raster_path = output_dir / f"{district}_ndvi_stress_{run_id}.tif"
    profile.update(dtype="uint8", count=1, nodata=255, compress="lzw")
    with rasterio.open(raster_path, "w", **profile) as destination:
        destination.write(stress, 1)
    with rasterio.open(raster_path) as check:
        if (
            check.width != width
            or check.height != height
            or check.crs != crs
            or check.transform != transform
            or check.nodata != 255
            or not np.array_equal(check.read(1), stress)
        ):
            raise IOError(f"Stress raster validation failed for {raster_path}.")

    report_path = output_dir / f"{district}_ndvi_stress_report_{run_id}.csv"
    pd.DataFrame([values]).to_csv(report_path, index=False)
    chart_path = output_dir / f"{district}_ndvi_stress_distribution_{run_id}.png"
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(
        ["Non-stressed", "Stressed"],
        [non_stressed_count, stressed_count],
        color=["#5b9e53", "#d9534f"],
    )
    ax.set_ylabel("Valid pixels")
    ax.set_title(f"{district.title()} NDVI stress (NDVI < {threshold})")
    fig.tight_layout()
    fig.savefig(chart_path, dpi=160)
    plt.close(fig)
    return {
        "statistics": values,
        "raster": raster_path,
        "report": report_path,
        "chart": chart_path,
    }
