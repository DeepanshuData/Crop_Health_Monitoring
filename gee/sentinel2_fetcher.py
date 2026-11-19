"""Sentinel-2 collection queries and district-aware image selection."""

import ee
from datetime import date

from gee.config import (
    ANALYSIS_SCALE_METERS,
    MAX_SCENE_CLOUD_PERCENT,
    SEARCH_WINDOW_DAYS,
    SENTINEL2_COLLECTION,
)
from gee.sentinel2_processor import mask_sentinel2_clouds


def fetch_sentinel2_collection(
    geometry,
    start_date,
    end_date,
    max_cloud_percentage=MAX_SCENE_CLOUD_PERCENT,
):
    """Fetch scenes intersecting a region within a half-open date interval."""
    return (
        ee.ImageCollection(SENTINEL2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percentage))
        .sort("system:time_start")
    )


def select_best_image(
    target_date,
    geometry,
    search_days=SEARCH_WINDOW_DAYS,
    max_cloud_percentage=MAX_SCENE_CLOUD_PERCENT,
    scale=ANALYSIS_SCALE_METERS,
):
    """Select the scene with the most valid in-region pixels in a date window."""
    target = ee.Date(target_date)
    collection = fetch_sentinel2_collection(
        geometry,
        target.advance(-search_days, "day"),
        target.advance(search_days + 1, "day"),
        max_cloud_percentage,
    )
    count = collection.size().getInfo()
    if not count:
        raise ValueError(f"No Sentinel-2 scenes found around {target_date}.")

    available_dates = collection.aggregate_array("system:time_start").map(
        lambda timestamp: ee.Date(timestamp).format("YYYY-MM-dd")
    ).distinct().getInfo()
    target_day = date.fromisoformat(target_date)
    candidate_dates = sorted(
        available_dates,
        key=lambda value: abs((date.fromisoformat(value) - target_day).days),
    )[:3]
    best = None
    best_pixels = -1
    for acquisition_date in candidate_dates:
        day = ee.Date(acquisition_date)
        daily_collection = collection.filterDate(day, day.advance(1, "day"))
        image = (
            daily_collection.map(mask_sentinel2_clouds)
            .sort("CLOUDY_PIXEL_PERCENTAGE", False)
            .mosaic()
            .set("system:time_start", day.millis())
            .set(
                "CLOUDY_PIXEL_PERCENTAGE",
                daily_collection.aggregate_min("CLOUDY_PIXEL_PERCENTAGE"),
            )
        )
        valid_pixels = (
            ee.Image.constant(1)
            .updateMask(image.select("B8").mask())
            .reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=geometry,
                scale=scale,
                maxPixels=1e10,
                tileScale=4,
                bestEffort=True,
            )
            .get("constant")
            .getInfo()
        )
        pixel_count = int(valid_pixels or 0)
        if pixel_count > best_pixels:
            best, best_pixels = image, pixel_count

    if best is None or best_pixels == 0:
        raise ValueError(
            f"Scenes were found around {target_date}, but none had valid "
            "cloud-free pixels in the district."
        )
    metadata = best.toDictionary(
        ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE"]
    ).getInfo()
    metadata["valid_pixels"] = best_pixels
    metadata["acquisition_date"] = ee.Date(
        metadata["system:time_start"]
    ).format("YYYY-MM-dd").getInfo()
    return best, metadata
