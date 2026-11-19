"""GeoJSON boundary loading, upload, validation and Earth Engine conversion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import ee
from shapely.geometry import shape

from gee.boundaries import DISTRICTS, load_district_feature
from gee.config import PROJECT_ROOT


UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"


def validate_feature(feature: dict) -> dict:
    """Validate a GeoJSON Feature or FeatureCollection Feature."""
    if not isinstance(feature, dict):
        raise ValueError("GeoJSON must be a JSON object.")
    if feature.get("type") == "FeatureCollection":
        features = feature.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("Upload exactly one Feature in a FeatureCollection.")
        feature = features[0]
    if feature.get("type") != "Feature":
        raise ValueError("GeoJSON must contain a Feature.")
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError("Feature has no geometry.")
    polygon = shape(geometry)
    if polygon.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Geometry must be Polygon or MultiPolygon.")
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError("Geometry is empty or invalid.")
    min_x, min_y, max_x, max_y = polygon.bounds
    if min_x < -180 or max_x > 180 or min_y < -90 or max_y > 90:
        raise ValueError("Coordinates must be longitude/latitude in EPSG:4326.")
    if polygon.area <= 0:
        raise ValueError("Geometry area must be greater than zero.")
    return feature


def district_feature(district: str) -> dict:
    """Load one of the bundled administrative district boundaries."""
    return load_district_feature(district)


def save_uploaded_geojson(uploaded_file) -> dict:
    """Preserve an uploaded GeoJSON file and return its validated Feature."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw = uploaded_file.getvalue()
    try:
        feature = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Uploaded file is not valid UTF-8 GeoJSON.") from exc
    feature = validate_feature(feature)
    safe_name = Path(uploaded_file.name).stem.replace(" ", "_")
    target = UPLOAD_DIR / f"{safe_name}.geojson"
    target.write_text(json.dumps(feature, indent=2), encoding="utf-8")
    return feature


def feature_to_ee(feature: dict):
    """Convert a validated GeoJSON Feature to an Earth Engine geometry."""
    feature = validate_feature(feature)
    return ee.Geometry(feature["geometry"])


def geometry_area_ha(feature: dict) -> float:
    """Calculate approximate area on an equal-area projection."""
    import pyproj
    from shapely.ops import transform

    geometry = shape(feature["geometry"])
    transformer = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:6933", always_xy=True
    ).transform
    projected = transform(transformer, geometry)
    return float(projected.area / 10000)
