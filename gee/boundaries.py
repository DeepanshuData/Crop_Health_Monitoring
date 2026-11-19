"""Boundary loading and validation shared by the GEE and local workflows."""

import json
from pathlib import Path

from shapely.geometry import shape

from gee.config import BOUNDARY_DIR


DISTRICTS = ("mandya", "mysuru", "hassan")


def load_district_feature(district, boundary_dir=BOUNDARY_DIR):
    """Load a district Feature and reject malformed or misidentified geometry."""
    if not isinstance(district, str):
        raise ValueError(f"District must be one of {DISTRICTS}.")
    district = district.lower()
    if district not in DISTRICTS:
        raise ValueError(f"Unknown district {district!r}; choose {DISTRICTS}.")
    path = Path(boundary_dir) / f"{district}.geojson"
    with path.open(encoding="utf-8") as source:
        feature = json.load(source)
    if feature.get("type") != "Feature":
        raise ValueError(f"{path} must contain a GeoJSON Feature.")
    if str(feature.get("properties", {}).get("district", "")).lower() != district:
        raise ValueError(f"{path} does not identify district {district!r}.")
    geometry = shape(feature.get("geometry") or {})
    if geometry.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"{path} must contain a Polygon or MultiPolygon.")
    if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
        raise ValueError(f"Invalid district boundary in {path}: {geometry.geom_type}.")
    min_x, min_y, max_x, max_y = geometry.bounds
    if min_x < -180 or max_x > 180 or min_y < -90 or max_y > 90:
        raise ValueError(f"{path} coordinates are not longitude/latitude.")
    return feature


def load_ee_geometry(district, boundary_dir=BOUNDARY_DIR):
    """Convert a validated district GeoJSON geometry to an EE geometry."""
    import ee

    feature = load_district_feature(district, boundary_dir)
    return ee.Geometry(feature["geometry"])
