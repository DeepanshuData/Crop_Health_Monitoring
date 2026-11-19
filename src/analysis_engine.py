"""Earth Engine initialization and primary Sentinel-2 analysis."""

from __future__ import annotations

from datetime import date

import ee

from gee.config import EE_PROJECT, SENTINEL2_COLLECTION
from gee.sentinel2_fetcher import fetch_sentinel2_collection
from gee.sentinel2_processor import (
    calculate_ndre,
    calculate_ndvi,
    calculate_ndwi,
    mask_sentinel2_clouds,
)


def initialize_earth_engine(project: str = EE_PROJECT) -> bool:
    """Initialize GEE once and report authentication/project failures."""
    try:
        ee.Initialize(project=project)
        return True
    except ee.EEException as exc:
        raise RuntimeError(
            "Earth Engine authentication or project access failed. "
            "Run `python -c \"import ee; ee.Authenticate()\"` or configure credentials."
        ) from exc


def fetch_analysis_image(
    geometry,
    start_date: date | str,
    end_date: date | str,
    max_cloud_percentage: int = 80,
):
    """Return the least-cloudy observation with a valid date and cloud metadata."""
    collection = fetch_sentinel2_collection(
        geometry, str(start_date), str(end_date), max_cloud_percentage
    )
    count = collection.size().getInfo()
    if not count:
        raise ValueError("No Sentinel-2 imagery was found for this boundary and date range.")
    image = ee.Image(collection.sort("CLOUDY_PIXEL_PERCENTAGE").first())
    image = mask_sentinel2_clouds(image)
    acquisition = ee.Date(image.get("system:time_start")).format("YYYY-MM-dd").getInfo()
    return image, {"acquisition_date": acquisition, "available_scenes": count}


def calculate_analysis(
    geometry,
    image,
    scale: int = 20,
) -> dict:
    """Calculate NDVI, NDRE, NDWI statistics and return EE images."""
    ndvi = calculate_ndvi(image)
    ndre = calculate_ndre(image)
    ndwi = calculate_ndwi(image)
    layers = ndvi.addBands([ndre, ndwi])
    stats = layers.reduceRegion(
        reducer=ee.Reducer.mean()
        .combine(reducer2=ee.Reducer.minMax(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.count(), sharedInputs=True),
        geometry=geometry,
        scale=scale,
        maxPixels=1e10,
        tileScale=4,
        bestEffort=True,
    ).getInfo()
    return {
        "satellite": image,
        "ndvi": ndvi,
        "ndre": ndre,
        "ndwi": ndwi,
        "statistics": stats,
    }
