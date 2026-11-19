"""NDVI/NDRE time-series extraction and CSV export."""

from __future__ import annotations

import ee
import pandas as pd

from gee.sentinel2_processor import (
    calculate_ndre,
    calculate_ndvi,
    mask_sentinel2_clouds,
)
from gee.config import SENTINEL2_COLLECTION


def build_timeseries(
    geometry,
    district_name: str,
    start_date: date | str,
    end_date: date | str,
    max_cloud_percentage: int = 80,
    scale: int = 20,
    max_dates: int = 12,
    batch_size: int = 4,
) -> pd.DataFrame:
    """Create a bounded, evenly sampled series with few EE round trips."""
    collection = (
        ee.ImageCollection(SENTINEL2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(str(start_date), str(end_date))
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percentage))
        .sort("system:time_start")
    )
    if not collection.size().getInfo():
        raise ValueError("No Sentinel-2 observations exist for this region and date range.")
    metadata = collection.map(
        lambda image: ee.Feature(
            None,
            {
                "acquisition_date": ee.Date(
                    image.get("system:time_start")
                ).format("YYYY-MM-dd"),
                "cloud_percentage": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            },
        )
    ).getInfo()["features"]
    cloud_by_date = {}
    for feature in metadata:
        properties = feature["properties"]
        acquisition_date = properties["acquisition_date"]
        cloud = properties.get("cloud_percentage")
        previous = cloud_by_date.get(acquisition_date)
        if cloud is not None and (previous is None or cloud < previous):
            cloud_by_date[acquisition_date] = cloud
    dates = sorted(cloud_by_date)
    if len(dates) > max_dates:
        indices = [
            round(index * (len(dates) - 1) / (max_dates - 1))
            for index in range(max_dates)
        ] if max_dates > 1 else [len(dates) - 1]
        dates = [dates[index] for index in indices]

    reducer = (
        ee.Reducer.mean()
        .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.sum(), sharedInputs=True)
    )
    rows = []
    for offset in range(0, len(dates), batch_size):
        batch_dates = dates[offset:offset + batch_size]
        date_features = ee.FeatureCollection([
            ee.Feature(
                None,
                {
                    "acquisition_date": acquisition_date,
                    "cloud_percentage": cloud_by_date.get(acquisition_date),
                },
            )
            for acquisition_date in batch_dates
        ])

        def summarize(feature):
            feature = ee.Feature(feature)
            acquisition_date = ee.String(feature.get("acquisition_date"))
            day = ee.Date(acquisition_date)
            image = ee.Image(
                collection.filterDate(day, day.advance(1, "day"))
                .map(mask_sentinel2_clouds)
                .sort("CLOUDY_PIXEL_PERCENTAGE")
                .mosaic()
            )
            ndvi = calculate_ndvi(image)
            ndre = calculate_ndre(image)
            valid_area = ee.Image.pixelArea().updateMask(ndvi.mask()).rename("valid_area_m2")
            stack = ndvi.addBands(ndre).addBands(valid_area)
            statistics = stack.reduceRegion(
                reducer=reducer,
                geometry=geometry,
                scale=scale,
                maxPixels=1e10,
                tileScale=4,
                bestEffort=True,
            )
            return ee.Feature(None, statistics).copyProperties(feature)

        result = ee.FeatureCollection(date_features.map(summarize)).getInfo()
        for item in result.get("features", []):
            properties = item["properties"]
            if properties.get("NDVI_mean") is None or properties.get("NDRE_mean") is None:
                continue
            rows.append({
                "district": district_name,
                "acquisition_date": properties["acquisition_date"],
                "mean_ndvi": properties["NDVI_mean"],
                "mean_ndre": properties["NDRE_mean"],
                "valid_pixel_count": int(properties.get("NDVI_count") or 0),
                "valid_area_ha": float(properties.get("valid_area_m2_sum") or 0) / 10000,
                "cloud_percentage": properties.get("cloud_percentage"),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No cloud-free, valid NDVI/NDRE observations were available.")
    frame["acquisition_date"] = pd.to_datetime(frame["acquisition_date"])
    return frame.sort_values("acquisition_date").reset_index(drop=True)
