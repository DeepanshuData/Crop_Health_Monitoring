"""Earth Engine NDVI stress classification and CSV/GeoTIFF export helpers."""

from __future__ import annotations

import ee
import pandas as pd


def classify_stress(ndvi, threshold: float = 0.30, geometry=None, scale: int = 20) -> dict:
    """Return a classification raster and explicitly counted area statistics."""
    if not -1 <= threshold <= 1:
        raise ValueError("NDVI stress threshold must be between -1 and 1.")
    valid = ndvi.mask().reduce(ee.Reducer.min())
    stressed = ndvi.lt(threshold).And(valid)
    non_stressed = ndvi.gte(threshold).And(valid)
    classification = (
        ee.Image(255)
        .where(non_stressed, 0)
        .where(stressed, 1)
        .updateMask(valid)
        .toUint8()
        .rename("stress")
    )
    if geometry is not None:
        classification = classification.clip(geometry)
    stats = {}
    if geometry is not None:
        area = ee.Image.pixelArea()
        result = (
            ee.Image.constant(1).rename("valid").updateMask(valid)
            .addBands(ee.Image.constant(1).rename("stressed").updateMask(stressed))
            .addBands(ee.Image.constant(1).rename("non_stressed").updateMask(non_stressed))
            .addBands(area.updateMask(valid).rename("valid_area"))
            .addBands(area.updateMask(stressed).rename("stressed_area"))
            .addBands(area.updateMask(non_stressed).rename("non_stressed_area"))
        ).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geometry,
            scale=scale,
            maxPixels=1e10,
            tileScale=4,
            bestEffort=True,
        ).getInfo()
        valid_count = int(result.get("valid") or 0)
        stressed_count = int(result.get("stressed") or 0)
        valid_area = float(result.get("valid_area") or 0)
        stressed_area = float(result.get("stressed_area") or 0)
        non_stressed_area = float(result.get("non_stressed_area") or 0)
        stats = {
            "threshold": threshold,
            "valid_pixels": valid_count,
            "stressed_pixels": stressed_count,
            "non_stressed_pixels": int(result.get("non_stressed") or 0),
            "valid_area_ha": valid_area / 10000,
            "stressed_area_ha": stressed_area / 10000,
            "non_stressed_area_ha": non_stressed_area / 10000,
            "stressed_percentage": (
                stressed_area / valid_area * 100 if valid_area else 0
            ),
        }
    return {"classification": classification, "statistics": stats}


def stress_report(statistics: dict, district: str) -> pd.DataFrame:
    return pd.DataFrame([{"district": district, **statistics}])
