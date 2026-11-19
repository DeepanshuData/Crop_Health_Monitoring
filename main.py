"""Run the multi-district Sentinel-2 crop monitoring workflow."""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime, timezone

import ee
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gee.boundaries import DISTRICTS, load_district_feature
from gee.config import (
    ANALYSIS_SCALE_METERS,
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    EE_PROJECT,
    OUTPUT_DIR,
    STRESS_THRESHOLD,
    TARGET_DATES,
    district_output_dirs,
)
from gee.ndvi_date_comparison import compare_ndvi_dates
from gee.ndvi_ndre_timeseries import extract_timeseries
from gee.sentinel2_processor import calculate_indices

LOGGER = logging.getLogger("crop_health")


def _export(image, description, folder, geometry, nodata=-9999):
    task = ee.batch.Export.image.toDrive(
        image=image.clip(geometry),
        description=description,
        folder=folder,
        fileNamePrefix=description,
        region=geometry,
        scale=ANALYSIS_SCALE_METERS,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        formatOptions={"noData": nodata},
    )
    task.start()
    return {"description": description, "task_id": task.id, "state": "SUBMITTED"}


def _write_export_manifest(path, exports):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["description", "task_id", "state"])
        writer.writeheader()
        writer.writerows(exports)


def _stress_statistics(ndvi, geometry):
    valid = ndvi.mask().reduce(ee.Reducer.min())
    stressed = ndvi.lt(STRESS_THRESHOLD).And(valid)
    non_stressed = ndvi.gte(STRESS_THRESHOLD).And(valid)
    pixels = ee.Image.constant(1).rename("valid").updateMask(valid)
    stressed_pixels = ee.Image.constant(1).rename("stressed").updateMask(stressed)
    non_stressed_pixels = (
        ee.Image.constant(1).rename("non_stressed").updateMask(non_stressed)
    )
    area = ee.Image.pixelArea()
    stack = (
        pixels.addBands(stressed_pixels)
        .addBands(non_stressed_pixels)
        .addBands(area.updateMask(valid))
        .addBands(area.updateMask(stressed).rename("stressed_area"))
        .addBands(area.updateMask(non_stressed).rename("non_stressed_area"))
    )
    result = stack.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry,
        scale=ANALYSIS_SCALE_METERS,
        maxPixels=1e10,
        tileScale=4,
    ).getInfo()
    valid_count = int(result.get("valid") or 0)
    stressed_count = int(result.get("stressed") or 0)
    return {
        "threshold": STRESS_THRESHOLD,
        "valid_pixels": valid_count,
        "stressed_pixels": stressed_count,
        "non_stressed_pixels": int(result.get("non_stressed") or 0),
        "valid_area_ha": float(result.get("area") or 0) / 10000,
        "mean_valid_pixel_area_m2": (
            float(result.get("area") or 0) / valid_count if valid_count else None
        ),
        "stressed_area_ha": float(result.get("stressed_area") or 0) / 10000,
        "non_stressed_area_ha": float(result.get("non_stressed_area") or 0) / 10000,
        "stressed_percentage_valid": (
            100 * stressed_count / valid_count if valid_count else 0
        ),
        "total_grid_pixels": None,
        "nodata_pixels": None,
        "nodata_note": "Exact counts require the exported raster grid.",
    }


def run_district(district, start_date, end_date, run_id):
    """Run one district and write local reports plus Drive export tasks."""
    LOGGER.info("Starting district: %s", district)
    feature = load_district_feature(district)
    geometry = ee.Geometry(feature["geometry"])
    paths = district_output_dirs(district)
    first_date, second_date = TARGET_DATES

    comparison = compare_ndvi_dates(first_date, second_date, geometry)
    first_image = comparison["first_image"]
    first_metadata = comparison["first_metadata"]
    first_indices = calculate_indices(first_image).select(["NDVI", "NDRE", "NDWI"])
    index_stats = first_indices.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            reducer2=ee.Reducer.count(), sharedInputs=True
        ),
        geometry=geometry,
        scale=ANALYSIS_SCALE_METERS,
        maxPixels=1e10,
        tileScale=4,
    ).getInfo()
    stress_stats = _stress_statistics(comparison["second_ndvi"], geometry)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    drive_folder = f"crop_health_{district}_{run_id}"
    series = extract_timeseries(
        geometry,
        start_date,
        end_date,
        paths["timeseries"],
        district,
        chart_dir=paths["charts"],
        run_id=run_id,
    )
    stress_chart = paths["charts"] / f"{district}_stress_distribution_{run_id}.png"
    fig, axis = plt.subplots(figsize=(6, 4))
    axis.bar(
        ["Non-stressed", "Stressed"],
        [stress_stats["non_stressed_pixels"], stress_stats["stressed_pixels"]],
        color=["#5b9e53", "#d9534f"],
    )
    axis.set_ylabel("Valid pixels")
    axis.set_title(f"{district.title()} NDVI stress (NDVI < {STRESS_THRESHOLD})")
    fig.tight_layout()
    fig.savefig(stress_chart, dpi=160)
    plt.close(fig)

    export_specs = [
        (
            first_indices,
            f"{district}_indices_{first_metadata['acquisition_date']}_{timestamp}",
            -9999,
        ),
        (
            comparison["first_ndvi"],
            f"{district}_ndvi_{comparison['first_metadata']['acquisition_date']}_{timestamp}",
            -9999,
        ),
        (
            comparison["second_ndvi"],
            f"{district}_ndvi_{comparison['second_metadata']['acquisition_date']}_{timestamp}",
            -9999,
        ),
        (
            comparison["change"],
            f"{district}_ndvi_change_{timestamp}",
            -9999,
        ),
        (
            comparison["second_ndvi"]
            .lt(STRESS_THRESHOLD)
            .where(comparison["second_ndvi"].gte(STRESS_THRESHOLD), 0)
            .rename("stress_class")
            .toUint8()
            .unmask(255),
            f"{district}_stress_class_{timestamp}",
            255,
        ),
    ]
    manifest_path = paths["maps"] / f"{district}_exports_{timestamp}.csv"
    exports = []
    try:
        for image, description, nodata in export_specs:
            exports.append(
                _export(image, description, drive_folder, geometry, nodata=nodata)
            )
    except Exception:
        _write_export_manifest(manifest_path, exports)
        raise
    _write_export_manifest(manifest_path, exports)
    summary = {
        "district": district,
        "run_id": run_id,
        "date_range_start": start_date,
        "date_range_end": end_date,
        "first_target_date": first_date,
        "first_acquisition_date": comparison["first_metadata"]["acquisition_date"],
        "first_scene_cloud_percentage": comparison["first_metadata"].get(
            "CLOUDY_PIXEL_PERCENTAGE"
        ),
        "second_target_date": second_date,
        "second_acquisition_date": comparison["second_metadata"]["acquisition_date"],
        "second_scene_cloud_percentage": comparison["second_metadata"].get(
            "CLOUDY_PIXEL_PERCENTAGE"
        ),
        "first_date_valid_pixels": comparison["metrics"]["first_valid_pixels"],
        "second_date_valid_pixels": comparison["metrics"]["second_valid_pixels"],
        "common_valid_pixels": comparison["metrics"]["common_valid_pixels"],
        "common_valid_area_ha": comparison["metrics"]["common_valid_area_m2"] / 10000,
        "common_valid_area_percent": comparison["metrics"][
            "common_valid_area_percent"
        ],
        "ndvi_mean": index_stats.get("NDVI_mean"),
        "ndre_mean": index_stats.get("NDRE_mean"),
        "ndwi_mean": index_stats.get("NDWI_mean"),
        "date_comparison_statistics": comparison["statistics"],
        **{f"stress_{key}": value for key, value in stress_stats.items()},
        "timeseries_records": len(series["data"]),
        "timeseries_total_scenes": series["total_scenes"],
        "drive_export_folder": drive_folder,
        "stress_chart": str(stress_chart),
        "stress_report_csv": str(
            paths["reports"] / f"{district}_stress_{timestamp}.csv"
        ),
    }
    report_path = paths["reports"] / f"{district}_summary_{timestamp}.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    stress_report_path = paths["reports"] / f"{district}_stress_{timestamp}.csv"
    stress_fields = [
        "district",
        "run_id",
        *stress_stats.keys(),
    ]
    with stress_report_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=stress_fields)
        writer.writeheader()
        writer.writerow(
            {"district": district, "run_id": run_id, **stress_stats}
        )
    LOGGER.info(
        "%s complete: acquired %s and %s; %d common valid pixels; %d exports queued",
        district,
        summary["first_acquisition_date"],
        summary["second_acquisition_date"],
        summary["common_valid_pixels"],
        len(exports),
    )
    return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--district", choices=DISTRICTS, default="mandya")
    group.add_argument("--all", action="store_true", dest="all_districts")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    return parser.parse_args(argv)


def main(argv=None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args(argv)
    try:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError:
        LOGGER.error("Start and end dates must use YYYY-MM-DD format.")
        return 2
    if start.isoformat() != args.start_date or end.isoformat() != args.end_date:
        LOGGER.error("Start and end dates must use YYYY-MM-DD format.")
        return 2
    if start >= end:
        LOGGER.error("The end date must be later than the start date.")
        return 2
    districts = DISTRICTS if args.all_districts else (args.district,)
    failures = []
    for district in districts:
        try:
            load_district_feature(district)
        except Exception as exc:
            LOGGER.exception("Boundary validation failed for %s", district)
            failures.append({"district": district, "error": str(exc)})
    if len(failures) == len(districts):
        error_dir = OUTPUT_DIR / "reports"
        error_dir.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (error_dir / f"pipeline_errors_{run_id}.json").write_text(
            json.dumps({"run_id": run_id, "failures": failures}, indent=2),
            encoding="utf-8",
        )
        return 1
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        ee.Initialize(project=EE_PROJECT)
    except Exception as exc:
        LOGGER.exception(
            "Earth Engine initialization failed. Check existing credentials and "
            "project access; authenticate with `earthengine authenticate` if needed."
        )
        error_dir = OUTPUT_DIR / "reports"
        error_dir.mkdir(parents=True, exist_ok=True)
        (error_dir / f"pipeline_errors_{run_id}.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "failures": [
                        {"district": district, "error": str(exc)}
                        for district in districts
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1

    for district in districts:
        if any(failure["district"] == district for failure in failures):
            continue
        try:
            run_district(district, args.start_date, args.end_date, run_id)
        except Exception as exc:
            LOGGER.exception("District processing failed for %s", district)
            failures.append({"district": district, "error": str(exc)})
    if failures:
        error_dir = OUTPUT_DIR / "reports"
        error_dir.mkdir(parents=True, exist_ok=True)
        failure_path = error_dir / f"pipeline_errors_{run_id}.json"
        failure_path.write_text(
            json.dumps({"run_id": run_id, "failures": failures}, indent=2),
            encoding="utf-8",
        )
        LOGGER.error("Failed districts: %s; details: %s", failures, failure_path)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
