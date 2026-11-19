"""Bounded Sentinel-2 NDVI/NDRE time-series extraction and charts."""

from pathlib import Path

import ee
import matplotlib
import time

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gee.config import (
    ANALYSIS_SCALE_METERS,
    MAX_SCENE_CLOUD_PERCENT,
    MAX_TIME_SERIES_RECORDS,
    SENTINEL2_COLLECTION,
)
from gee.sentinel2_processor import calculate_ndre, calculate_ndvi, mask_sentinel2_clouds


def extract_timeseries(
    geometry,
    start_date,
    end_date,
    output_dir,
    district,
    chart_dir=None,
    run_id="",
    scale=ANALYSIS_SCALE_METERS,
    max_records=MAX_TIME_SERIES_RECORDS,
):
    """Fetch at most max_records scenes and write district-specific CSV/charts."""
    collection = (
        ee.ImageCollection(SENTINEL2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_SCENE_CLOUD_PERCENT))
        .sort("system:time_start")
    )
    count = collection.size().getInfo()
    if not count:
        raise ValueError(
            f"No Sentinel-2 time-series images for {district} "
            f"between {start_date} and {end_date}."
        )
    acquisition_dates = list(
        collection.aggregate_array("system:time_start")
        .map(lambda timestamp: ee.Date(timestamp).format("YYYY-MM-dd"))
        .distinct()
        .slice(0, max_records)
        .getInfo()
    )
    date_count = len(acquisition_dates)
    if not date_count:
        raise ValueError(f"No acquisition dates were returned for {district}.")

    def summarize(acquisition_date):
        day = ee.Date(acquisition_date)
        daily = (
            collection.filterDate(day, day.advance(1, "day"))
            .map(mask_sentinel2_clouds)
            .sort("CLOUDY_PIXEL_PERCENTAGE", False)
            .mosaic()
        )
        image = ee.Image(daily)
        indices = calculate_ndvi(image).addBands(calculate_ndre(image))
        stats = indices.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=scale,
            maxPixels=1e10,
            tileScale=4,
            bestEffort=True,
        )
        scene_count = collection.filterDate(day, day.advance(1, "day")).size().getInfo()
        properties = stats.getInfo()
        properties["date"] = acquisition_date
        properties["scene_count"] = scene_count
        return properties

    records = []
    for index, acquisition_date in enumerate(acquisition_dates):
        try:
            records.append(summarize(acquisition_date))
        except ee.EEException as exc:
            if "Too many concurrent" in str(exc):
                time.sleep(5)
                records.append(summarize(acquisition_date))
            else:
                raise
        if index % 10 == 9:
            time.sleep(0.5)
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError(f"No valid time-series records were returned for {district}.")
    frame = frame.dropna(subset=["NDVI", "NDRE"])
    frame = frame.sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise ValueError(f"No cloud-free NDVI/NDRE observations for {district}.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{run_id}" if run_id else ""
    csv_path = output_dir / f"{district}_ndvi_ndre_timeseries{suffix}.csv"
    frame.to_csv(csv_path, index=False)
    chart_dir = Path(chart_dir) if chart_dir else output_dir
    chart_dir.mkdir(parents=True, exist_ok=True)
    chart_paths = []
    for band in ("NDVI", "NDRE"):
        chart_path = chart_dir / f"{district}_{band.lower()}_timeseries{suffix}.png"
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(pd.to_datetime(frame["date"]), frame[band], marker="o", linewidth=1)
        ax.set(title=f"{district.title()} {band} time series", ylabel=band)
        ax.set_xlabel("Acquisition date")
        ax.grid(True, alpha=0.25)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(chart_path, dpi=160)
        plt.close(fig)
        chart_paths.append(chart_path)
    return {"data": frame, "csv": csv_path, "charts": chart_paths, "total_scenes": count}
