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

    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    evi_denominator = nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)
    evi = (
        safe_ratio(nir.subtract(red).multiply(2.5), evi_denominator)
        .updateMask(evi_denominator.abs().gte(0.1))
        .rename("EVI")
    )
    gndvi = safe_ratio(nir.subtract(green), nir.add(green)).rename("GNDVI")
    ndre = image.expression(
        "(NIR - RED_EDGE) / (NIR + RED_EDGE)",
        {"NIR": nir, "RED_EDGE": red_edge},
    ).rename("NDRE")
    ndmi = safe_ratio(nir.subtract(swir1), nir.add(swir1)).rename("NDMI")
    msi = safe_ratio(swir1, nir).rename("MSI")
    savi = safe_ratio(nir.subtract(red).multiply(1.5), nir.add(red).add(0.5)).rename("SAVI")
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    return image.addBands([ndvi, evi, gndvi, ndre, ndmi, msi, savi, ndwi])


def _prepare_collection(
    ee,
    geometry,
    start_date: date,
    end_date: date,
    max_cloud_percent: int,
    exclusive_cloud_limit: bool = False,
):
    cloud_filter = (
        ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percent)
        if exclusive_cloud_limit
        else ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percent)
    )
    return (
        ee.ImageCollection(COLLECTION_ID)
        .filterBounds(geometry)
        .filterDate(start_date.isoformat(), (end_date + timedelta(days=1)).isoformat())
        .filter(cloud_filter)
        .map(lambda image: _add_indices(_scaled_reflectance(_mask_cloud_shadow(image))))
        .sort("system:time_start")
    )


def _index_statistics(ee, image, geometry, scale: int = 20) -> dict[str, Any]:
    reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.minMax(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
    )
    try:
        result = image.select(list(EE_INDEX_BANDS)).reduceRegion(
            reducer=reducer,
            geometry=geometry,
            scale=scale,
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


def _summarize_time_series_scenes(
    ee,
    collection,
    geometry,
    scene_count: int,
    index_names: tuple[str, ...],
    scale: int,
    max_pixels: int,
    scene_limit: int,
    context: str,
):
    selected_count = min(scene_count, scene_limit)
    limited_collection = collection.limit(selected_count)
    scenes = limited_collection.toList(selected_count)

    def summarize_scene(scene):
        image = ee.Image(scene)
        means = image.select(list(index_names)).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=scale,
            maxPixels=max_pixels,
            tileScale=4,
        )
        properties = {
            "date": image.date().format("YYYY-MM-dd"),
            "scene_cloud_percent": image.get("CLOUDY_PIXEL_PERCENTAGE"),
        }
        properties.update({name: means.get(name) for name in index_names})
        return ee.Feature(None, properties)

    try:
        response = ee.FeatureCollection(scenes.map(summarize_scene)).getInfo()
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not calculate {context} regional means. "
            f"Try fewer dates or a smaller study area: {error}"
        ) from error

    observations = []
    for feature in response.get("features", []):
        properties = feature.get("properties", {})
        if any(properties.get(name) is not None for name in index_names):
            observations.append(properties)
    if not observations:
        raise EarthEngineError(
            f"Earth Engine found scenes but no valid masked pixels for {context}."
        )
    observations.sort(key=lambda row: row["date"])
    return limited_collection, observations


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

    limited_collection, observations = _summarize_time_series_scenes(
        ee,
        collection,
        geometry,
        count,
        ("NDVI", "NDRE", "NDWI"),
        scale=20,
        max_pixels=100_000_000,
        scene_limit=120,
        context="historical",
    )
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


def _mandya_boundary(ee):
    districts = (
        ee.FeatureCollection("FAO/GAUL/2025/level2")
        .filter(ee.Filter.eq("GAUL0_NAME", "India"))
        .filter(ee.Filter.eq("GAUL1_NAME", "Karnataka"))
        .filter(ee.Filter.eq("GAUL2_NAME", "Mandya"))
    )
    try:
        district_count = int(districts.size().getInfo())
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not load the Mandya district boundary: {error}"
        ) from error
    if district_count != 1:
        raise EarthEngineError(
            f"Expected one Mandya boundary in FAO/GAUL/2025/level2; found {district_count}."
        )
    return districts, districts.geometry()


def _farm_feature_collection(ee, geojson: dict[str, Any]):
    if geojson["type"] == "FeatureCollection":
        return ee.FeatureCollection(geojson)
    if geojson["type"] == "Feature":
        feature = ee.Feature(
            ee.Geometry(geojson["geometry"]),
            geojson.get("properties") or {},
        )
    else:
        feature = ee.Feature(ee.Geometry(geojson))
    return ee.FeatureCollection([feature])


def mandya_sentinel2_time_series(
    start_date: date,
    end_date: date,
    project: str | None = None,
    farm_geojson_text: str | None = None,
) -> dict[str, Any]:
    """Fetch Mandya composite layers, regional/farm summaries and date-wise observations."""
    if end_date < start_date:
        raise ValueError("The end date must be on or after the start date.")
    ee = _earth_engine(project)
    districts, geometry = _mandya_boundary(ee)
    collection = _prepare_collection(
        ee,
        geometry,
        start_date,
        end_date,
        10,
        exclusive_cloud_limit=True,
    ).select("NDVI")
    try:
        scene_count = int(collection.size().getInfo())
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not search the Mandya Sentinel-2 collection: {error}"
        ) from error
    if scene_count == 0:
        raise EarthEngineError(
            "No Mandya Sentinel-2 scenes match the last-year date range and <10% cloud threshold."
        )
    if scene_count > 1000:
        raise EarthEngineError(
            f"Earth Engine found {scene_count} scenes; narrow the date range to return complete observations."
        )

    composite = collection.median().clip(geometry)
    statistics = _index_statistics(ee, composite, geometry, scale=10)
    try:
        district_result = composite.select("NDVI").reduceRegions(
            collection=districts,
            reducer=ee.Reducer.mean(),
            scale=10,
            tileScale=4,
            maxPixelsPerRegion=1_000_000_000,
        )
        district_means = district_result.aggregate_array("mean").getInfo()
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not calculate the Mandya district feature mean: {error}"
        ) from error
    if not district_means or district_means[0] is None:
        raise EarthEngineError(
            "Earth Engine returned no valid district mean for the selected date range."
        )

    farm_statistics = []
    if farm_geojson_text is not None:
        farm_geojson = validate_request(
            farm_geojson_text,
            start_date,
            end_date,
            max_cloud_percent=10,
        )
        farm_feature_count = (
            len(farm_geojson["features"])
            if farm_geojson["type"] == "FeatureCollection"
            else 1
        )
        if farm_feature_count > 500:
            raise ValueError("Upload no more than 500 farm polygons per analysis.")
        farms = _farm_feature_collection(ee, farm_geojson)
        try:
            farm_result = composite.select("NDVI").reduceRegions(
                collection=farms,
                reducer=ee.Reducer.mean(),
                scale=10,
                tileScale=4,
                maxPixelsPerRegion=100_000_000,
            )
            farm_values = ee.Dictionary(
                {
                    "ids": farm_result.aggregate_array("system:index"),
                    "means": farm_result.aggregate_array("mean"),
                }
            ).getInfo()
        except Exception as error:
            raise EarthEngineError(
                f"Earth Engine could not calculate farm-level means: {error}"
            ) from error
        farm_ids = farm_values.get("ids") or []
        farm_means = farm_values.get("means") or []
        farm_statistics = [
            {
                "farm": str(farm_ids[index]) if index < len(farm_ids) and farm_ids[index] else f"Farm {index + 1}",
                "mean_ndvi": mean,
            }
            for index, mean in enumerate(farm_means)
        ]

    _, observations = _summarize_time_series_scenes(
        ee,
        collection,
        geometry,
        scene_count,
        ("NDVI",),
        scale=10,
        max_pixels=1_000_000_000,
        scene_limit=1000,
        context="date-wise Mandya NDVI",
    )
    tile_layers = {}
    visualization = {
        "NDVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["a50026", "ffffbf", "006837"],
        },
        "NDRE": {
            "min": -0.2,
            "max": 0.6,
            "palette": ["a50026", "ffffbf", "006837"],
        },
        "NDWI": {
            "min": -0.5,
            "max": 0.5,
            "palette": ["8c510a", "f7f7f7", "01665e"],
        },
    }
    try:
        for index_name, params in visualization.items():
            tile_layers[index_name] = composite.select(index_name).getMapId(params)[
                "tile_fetcher"
            ].url_format
        tile_layers["true_color"] = composite.getMapId(
            {"bands": ["B4", "B3", "B2"], "min": 0.0, "max": 0.3}
        )["tile_fetcher"].url_format
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not create Mandya map layers: {error}"
        ) from error

    return {
        "observations": observations,
        "scene_count": scene_count,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "statistics": statistics,
        "district_statistics": {
            "district": "Mandya",
            "mean_ndvi": district_means[0],
        },
        "farm_statistics": farm_statistics,
        "tiles": tile_layers,
        "cloud_filter": "CLOUDY_PIXEL_PERCENTAGE < 10",
        "cloud_shadow_mask": "Sentinel-2 SCL classes 0, 1, 3, 8, 9, 10 and 11 masked.",
    }


def start_mandya_ndvi_drive_export(
    start_date: date,
    end_date: date,
    project: str | None = None,
) -> dict[str, str]:
    """Start an explicit Earth Engine mean-NDVI GeoTIFF export to Google Drive."""
    if end_date < start_date:
        raise ValueError("The end date must be on or after the start date.")
    ee = _earth_engine(project)
    _, geometry = _mandya_boundary(ee)
    collection = _prepare_collection(
        ee,
        geometry,
        start_date,
        end_date,
        10,
        exclusive_cloud_limit=True,
    )
    try:
        scene_count = int(collection.size().getInfo())
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not prepare the NDVI export collection: {error}"
        ) from error
    if scene_count == 0:
        raise EarthEngineError(
            "No Mandya Sentinel-2 scenes match the selected date range and <10% cloud threshold."
        )

    image = collection.select("NDVI").mean().clip(geometry)
    export_name = (
        f"Mandya_Mean_NDVI_{start_date:%Y%m%d}_{end_date:%Y%m%d}"
    )
    try:
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=export_name,
            folder="Crop_Health_Monitoring",
            fileNamePrefix=export_name,
            region=geometry,
            scale=10,
            crs="EPSG:4326",
            maxPixels=1_000_000_000_000,
            fileFormat="GeoTIFF",
            formatOptions={"cloudOptimized": True, "noData": -9999},
        )
        task.start()
        status = task.status()
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not start the Mandya Google Drive export: {error}"
        ) from error
    if not task.id or not status.get("state"):
        raise EarthEngineError(
            "Earth Engine started the export but did not return a task ID and status."
        )
    return {
        "task_id": task.id,
        "state": status["state"],
        "description": export_name,
        "drive_folder": "Crop_Health_Monitoring",
    }


def mandya_export_task_status(
    task_id: str,
    project: str | None = None,
) -> dict[str, str]:
    """Return a sanitized status for a previously started Mandya Drive export."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("Provide a valid Earth Engine export task ID.")
    ee = _earth_engine(project)
    try:
        statuses = ee.data.getTaskStatus(task_id.strip())
    except Exception as error:
        raise EarthEngineError(
            f"Earth Engine could not read export task status: {error}"
        ) from error
    if not statuses or not statuses[0].get("state"):
        raise EarthEngineError("Earth Engine returned no status for the export task.")
    task_status = statuses[0]
    return {
        "state": task_status["state"],
        "description": task_status.get("description", "Mandya NDVI export"),
        "error_message": task_status.get("error_message", ""),
    }
