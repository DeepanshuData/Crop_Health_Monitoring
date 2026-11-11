"""Optional Google Earth Engine workflow for user-supplied study-area GeoJSON."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any


COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
EE_BANDS = ("B2", "B3", "B4", "B5", "B8", "B11")
EE_INDEX_BANDS = ("NDVI", "EVI", "GNDVI", "NDRE", "NDMI", "MSI", "SAVI", "NDWI")


class EarthEngineError(RuntimeError):
    """Raised when an Earth Engine operation cannot complete."""


def validate_request(
    geojson_text: str,
    start_date: date,
    end_date: date,
    max_cloud_percent: int,
) -> dict[str, Any]:
    if not isinstance(geojson_text, str) or not geojson_text.strip():
        raise ValueError("Upload a GeoJSON Polygon, MultiPolygon, Feature, or FeatureCollection.")
    if len(geojson_text.encode("utf-8")) > 2_000_000:
        raise ValueError("The study-area GeoJSON must be smaller than 2 MB.")
    try:
        geojson = json.loads(geojson_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid GeoJSON: {error.msg}.") from error

    if not isinstance(geojson, dict):
        raise ValueError("GeoJSON must be an object.")
    geometry = geojson
    if geojson.get("type") == "Feature":
        geometry = geojson.get("geometry")
    elif geojson.get("type") == "FeatureCollection":
        features = geojson.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("GeoJSON FeatureCollection must contain at least one feature.")
        if any(not isinstance(feature, dict) or feature.get("geometry") is None for feature in features):
            raise ValueError("Every GeoJSON feature must have a geometry.")

    supported_types = {"Polygon", "MultiPolygon"}
    geometry_type = geometry.get("type") if isinstance(geometry, dict) else None
    if geojson.get("type") == "FeatureCollection":
        geometry_type = "FeatureCollection"
    elif geometry_type not in supported_types:
        raise ValueError("Provide a Polygon or MultiPolygon study-area geometry.")

    def validate_position(position: Any) -> None:
        if (
            not isinstance(position, (list, tuple))
            or len(position) < 2
            or not isinstance(position[0], (int, float))
            or not isinstance(position[1], (int, float))
            or not math.isfinite(float(position[0]))
            or not math.isfinite(float(position[1]))
            or not -180 <= float(position[0]) <= 180
            or not -90 <= float(position[1]) <= 90
        ):
            raise ValueError("GeoJSON coordinates must contain valid longitude/latitude pairs.")

    def walk_coordinates(value: Any) -> None:
        if not isinstance(value, (list, tuple)) or not value:
            raise ValueError("The GeoJSON geometry has empty or invalid coordinates.")
        if (
            len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            validate_position(value)
            return
        for child in value:
            walk_coordinates(child)

    geometries = (
        [feature["geometry"] for feature in geojson["features"]]
        if geojson.get("type") == "FeatureCollection"
        else [geometry]
    )
    for item in geometries:
        if not isinstance(item, dict) or item.get("type") not in supported_types:
            raise ValueError("All study-area features must be Polygon or MultiPolygon geometries.")
        coordinates = item.get("coordinates")
        walk_coordinates(coordinates)
        polygons = [coordinates] if item["type"] == "Polygon" else coordinates
        for polygon in polygons:
            if not polygon:
                raise ValueError("Polygons must contain at least one ring.")
            for ring in polygon:
                if len(ring) < 4:
                    raise ValueError("Polygon rings must contain at least four positions.")
                if ring[0] != ring[-1]:
                    raise ValueError(
                        "Each polygon ring must be closed (first and last positions match)."
                    )

    if end_date < start_date:
        raise ValueError("The end date must be on or after the start date.")
    if max_cloud_percent < 0 or max_cloud_percent > 100:
        raise ValueError("Cloud-cover threshold must be between 0 and 100 percent.")

    return geojson


def _earth_engine(project: str | None):
    try:
        import ee
    except ImportError as error:
        raise EarthEngineError(
            "The Earth Engine Python API is not installed. Install the project requirements first."
        ) from error
    try:
        if project:
            ee.Initialize(project=project.strip())
        else:
            ee.Initialize()
    except Exception as error:
        raise EarthEngineError(
            "Earth Engine is not authenticated or initialized. Authenticate in a terminal with "
            "`earthengine authenticate`, then configure a Google Cloud project with Earth Engine "
            "access. Authentication is not started automatically from this app."
        ) from error
    return ee


def _region_geometry(ee, geojson: dict[str, Any]):
    try:
        if geojson.get("type") == "FeatureCollection":
            return ee.FeatureCollection(geojson).geometry()
        if geojson.get("type") == "Feature":
            return ee.Geometry(geojson.get("geometry"))
        return ee.Geometry(geojson)
    except Exception as error:
        raise ValueError(f"Earth Engine could not construct the study-area geometry: {error}") from error


def _mask_cloud_shadow(image):
    scl = image.select("SCL")
    clear = (
        scl.neq(0)
        .And(scl.neq(1))
        .And(scl.neq(3))
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return image.updateMask(clear)


def _scaled_reflectance(image):
    scaled = image.select(list(EE_BANDS)).multiply(0.0001)
    return scaled.copyProperties(
        image, ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "system:index"]
    )


def _add_indices(image):
    blue = image.select("B2")
    green = image.select("B3")
    red = image.select("B4")
    red_edge = image.select("B5")
    nir = image.select("B8")
    swir1 = image.select("B11")

    def safe_ratio(numerator, denominator):
        return numerator.divide(denominator.updateMask(denominator.neq(0)))

    ndvi = safe_ratio(nir.subtract(red), nir.add(red)).rename("NDVI")
    evi_denominator = nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)
    evi = (
        safe_ratio(nir.subtract(red).multiply(2.5), evi_denominator)
        .updateMask(evi_denominator.abs().gte(0.1))
        .rename("EVI")
    )
    gndvi = safe_ratio(nir.subtract(green), nir.add(green)).rename("GNDVI")
    ndre = safe_ratio(nir.subtract(red_edge), nir.add(red_edge)).rename("NDRE")
    ndmi = safe_ratio(nir.subtract(swir1), nir.add(swir1)).rename("NDMI")
    msi = safe_ratio(swir1, nir).rename("MSI")
    savi = safe_ratio(nir.subtract(red).multiply(1.5), nir.add(red).add(0.5)).rename("SAVI")
    ndwi = safe_ratio(green.subtract(nir), green.add(nir)).rename("NDWI")
    return image.addBands([ndvi, evi, gndvi, ndre, ndmi, msi, savi, ndwi])


def _prepare_collection(
    ee,
    geometry,
    start_date: date,
    end_date: date,
    max_cloud_percent: int,
):
    return (
        ee.ImageCollection(COLLECTION_ID)
        .filterBounds(geometry)
        .filterDate(start_date.isoformat(), (end_date + timedelta(days=1)).isoformat())
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percent))
        .map(lambda image: _add_indices(_scaled_reflectance(_mask_cloud_shadow(image))))
        .sort("system:time_start")
    )


def _index_statistics(ee, image, geometry) -> dict[str, Any]:
    reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.minMax(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
    )
    try:
        result = image.select(list(EE_INDEX_BANDS)).reduceRegion(
            reducer=reducer,
            geometry=geometry,
            scale=20,
            maxPixels=100_000_000,
            tileScale=4,
        ).getInfo()
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not calculate regional statistics. Check the geometry size and "
            f"permissions, then try a smaller area: {error}"
        ) from error
    if not result or all(value is None for value in result.values()):
        raise EarthEngineError("Earth Engine returned no valid pixels for this region and date range.")
    return result


def search_sentinel2(
    geojson_text: str,
    start_date: date,
    end_date: date,
    max_cloud_percent: int,
    project: str | None = None,
) -> dict[str, Any]:
    """Search, cloud/shadow mask, scale, summarize and create tiles for an AOI."""
    geojson = validate_request(geojson_text, start_date, end_date, max_cloud_percent)
    ee = _earth_engine(project)
    geometry = _region_geometry(ee, geojson)
    collection = _prepare_collection(ee, geometry, start_date, end_date, max_cloud_percent)
    try:
        scene_count = int(collection.size().getInfo())
    except Exception as error:
        raise EarthEngineError(f"Earth Engine could not search the image collection: {error}") from error
    if scene_count == 0:
        raise EarthEngineError(
            "No Sentinel-2 scenes match this geometry, date range and cloud threshold. "
            "Try a longer date range or a higher cloud threshold."
        )

    try:
        scene_dates = collection.aggregate_array("system:time_start").getInfo()
        scene_cloud = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()
        composite = collection.median().clip(geometry)
    except Exception as error:
        raise EarthEngineError(f"Earth Engine could not build the scene composite: {error}") from error

    statistics = _index_statistics(ee, composite, geometry)
    vis_params = {
        "NDVI": {"min": -0.2, "max": 0.8, "palette": ["a50026", "ffffbf", "006837"]},
        "NDRE": {"min": -0.2, "max": 0.6, "palette": ["a50026", "ffffbf", "006837"]},
        "NDWI": {"min": -0.5, "max": 0.5, "palette": ["8c510a", "f7f7f7", "01665e"]},
        "false_color": {"bands": ["B8", "B4", "B3"], "min": 0.02, "max": 0.45},
    }
    tiles = {}
    try:
        for layer_name, params in vis_params.items():
            band = layer_name if layer_name != "false_color" else "B8"
            layer = composite.select(band) if layer_name != "false_color" else composite
            tiles[layer_name] = layer.getMapId(params)["tile_fetcher"].url_format
    except Exception as error:
        raise EarthEngineError(f"Earth Engine could not create map layers: {error}") from error

    return {
        "collection": COLLECTION_ID,
        "scene_count": scene_count,
        "cloud_metadata_mean_percent": scene_cloud,
        "scene_dates": [
            datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).date().isoformat()
            for timestamp in scene_dates
        ],
        "statistics": statistics,
        "tiles": tiles,
        "geometry": geojson,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "max_cloud_percent": max_cloud_percent,
        "cloud_shadow_mask": "Sentinel-2 SCL classes 0, 1, 3, 8, 9, 10 and 11 masked.",
    }


def sentinel2_time_series(
    geojson_text: str,
    start_date: date,
    end_date: date,
    max_cloud_percent: int,
    project: str | None = None,
) -> dict[str, Any]:
    """Return real per-scene means and first/latest/difference map layers for an AOI."""
    geojson = validate_request(geojson_text, start_date, end_date, max_cloud_percent)
    ee = _earth_engine(project)
    geometry = _region_geometry(ee, geojson)
    collection = _prepare_collection(ee, geometry, start_date, end_date, max_cloud_percent)
    try:
        count = int(collection.size().getInfo())
    except Exception as error:
        raise EarthEngineError(f"Earth Engine could not search the requested dates: {error}") from error
    if count == 0:
        raise EarthEngineError(
            "No Sentinel-2 observations match this geometry, date range and cloud threshold."
        )

    limited_collection = collection.limit(120)
    scenes = limited_collection.toList(120)

    def summarize_scene(scene):
        image = ee.Image(scene)
        means = image.select(["NDVI", "NDRE", "NDWI"]).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=20,
            maxPixels=100_000_000,
            tileScale=4,
        )
        return ee.Feature(
            None,
            {
                "date": image.date().format("YYYY-MM-dd"),
                "scene_cloud_percent": image.get("CLOUDY_PIXEL_PERCENTAGE"),
                "NDVI": means.get("NDVI"),
                "NDRE": means.get("NDRE"),
                "NDWI": means.get("NDWI"),
            },
        )

    try:
        response = ee.FeatureCollection(scenes.map(summarize_scene)).getInfo()
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not calculate historical regional means. Try fewer dates or a "
            f"smaller study area: {error}"
        ) from error
    observations = []
    for feature in response.get("features", []):
        properties = feature.get("properties", {})
        if any(properties.get(name) is not None for name in ("NDVI", "NDRE", "NDWI")):
            observations.append(properties)
    if not observations:
        raise EarthEngineError(
            "Earth Engine found scenes but no valid masked pixels in the study area."
        )
    observations.sort(key=lambda row: row["date"])
    first_image = ee.Image(limited_collection.sort("system:time_start").first()).clip(geometry)
    last_image = ee.Image(limited_collection.sort("system:time_start", False).first()).clip(geometry)
    tile_layers = {}
    try:
        index_vis = {
            "NDVI": {"min": -0.2, "max": 0.8, "palette": ["a50026", "ffffbf", "006837"]},
            "NDRE": {"min": -0.2, "max": 0.6, "palette": ["a50026", "ffffbf", "006837"]},
            "NDWI": {"min": -0.5, "max": 0.5, "palette": ["8c510a", "f7f7f7", "01665e"]},
        }
        difference_vis = {
            "min": -0.4,
            "max": 0.4,
            "palette": ["a50026", "ffffbf", "006837"],
        }
        for index_name, params in index_vis.items():
            tile_layers[index_name] = {}
            for period, image in (("first", first_image), ("latest", last_image)):
                tile_layers[index_name][period] = image.select(index_name).getMapId(params)[
                    "tile_fetcher"
                ].url_format
            difference = last_image.select(index_name).subtract(
                first_image.select(index_name)
            ).rename(f"{index_name}_difference")
            tile_layers[index_name]["difference"] = difference.getMapId(difference_vis)[
                "tile_fetcher"
            ].url_format
    except Exception as error:
        raise EarthEngineError(f"Earth Engine could not create historical map layers: {error}") from error

    return {
        "observations": observations,
        "scene_count": count,
        "first_date": observations[0]["date"],
        "latest_date": observations[-1]["date"],
        "tiles": tile_layers,
        "geometry": geojson,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "max_cloud_percent": max_cloud_percent,
        "cloud_shadow_mask": "Sentinel-2 SCL classes 0, 1, 3, 8, 9, 10 and 11 masked.",
    }
