"""Create CSV downloads and submit Earth Engine GeoTIFF exports."""

from __future__ import annotations

import json
from pathlib import Path

import ee
import pandas as pd

from gee.config import PROJECT_ROOT


def save_csv(frame: pd.DataFrame, district: str, name: str) -> Path:
    """Write a CSV to a district-specific local exports directory."""
    directory = PROJECT_ROOT / "outputs" / district.lower() / "exports"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{district.lower()}_{name}.csv"
    frame.to_csv(target, index=False)
    return target


def save_json(document: dict, district: str, name: str) -> Path:
    directory = PROJECT_ROOT / "outputs" / district.lower() / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{district.lower()}_{name}.json"
    target.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return target


def start_geotiff_export(image, geometry, district: str, name: str, nodata=-9999) -> str:
    """Submit a clipped GeoTIFF export to the user's Google Drive."""
    description = f"{district.lower()}_{name}"
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder="crop_health_monitoring",
        fileNamePrefix=description,
        region=geometry,
        scale=20,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        formatOptions={"noData": nodata},
    )
    task.start()
    return task.id


def geotiff_export_status(task_id: str) -> dict:
    """Return the current Earth Engine status for a submitted export task."""
    return ee.data.getTaskStatus(task_id)[0]
