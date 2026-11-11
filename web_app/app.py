from __future__ import annotations

import csv
import io
import math
import threading
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_RASTER = PROJECT_ROOT / "data" / "sentinel2_complete_bands" / "Mysuru_Sentinel2_6_Bands.tif"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "all_7_indices"
GEOTIFF_DIR = OUTPUT_DIR / "geotiff"
STATISTICS_FILE = OUTPUT_DIR / "index_statistics.csv"
OVERVIEW_FILE = OUTPUT_DIR / "sentinel2_all_7_indices.png"
SUMMARY_FILE = OUTPUT_DIR / "project_summary.txt"

STUDY_AREA = "Mysuru, Karnataka, India"
ACQUISITION_DATE = "2025-02-06"
COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
CRS_LABEL = "EPSG:32643"

INDEX_DETAILS = {
    "NDVI": {
        "formula": "(NIR - Red) / (NIR + Red)",
        "meaning": "Canopy greenness and relative vegetation vigor.",
        "use": "Compare crop vigor and identify areas with sparse or stressed vegetation.",
        "cmap": "RdYlGn",
    },
    "EVI": {
        "formula": "2.5 × (NIR - Red) / (NIR + 6 × Red - 7.5 × Blue + 1)",
        "meaning": "Enhanced canopy vigor, with reduced soil and atmospheric influence.",
        "use": "Assess vigorous or dense vegetation. Unstable denominators are masked.",
        "cmap": "RdYlGn",
    },
    "GNDVI": {
        "formula": "(NIR - Green) / (NIR + Green)",
        "meaning": "Green-band vegetation response related to canopy vigor and chlorophyll.",
        "use": "Compare crop vigor and chlorophyll-related variation.",
        "cmap": "RdYlGn",
    },
    "NDRE": {
        "formula": "(NIR - Red Edge 1) / (NIR + Red Edge 1)",
        "meaning": "Red-edge response to canopy chlorophyll and stress.",
        "use": "Monitor denser canopies where red-edge response is informative.",
        "cmap": "RdYlGn",
    },
    "NDMI": {
        "formula": "(NIR - SWIR 1) / (NIR + SWIR 1)",
        "meaning": "Canopy moisture variation.",
        "use": "Identify relative moisture differences and potential water stress.",
        "cmap": "BrBG",
    },
    "MSI": {
        "formula": "SWIR 1 / NIR",
        "meaning": "Moisture stress ratio; larger values commonly indicate drier vegetation.",
        "use": "Compare relative vegetation moisture stress within this scene.",
        "cmap": "YlOrRd",
    },
    "SAVI": {
        "formula": "1.5 × (NIR - Red) / (NIR + Red + 0.5)",
        "meaning": "Soil-adjusted vegetation greenness.",
        "use": "Assess vegetation while reducing soil-background influence in sparse cover.",
        "cmap": "RdYlGn",
    },
}
INDEX_NAMES = tuple(INDEX_DETAILS)

app = Flask(__name__, template_folder="templates", static_folder="static")
_preview_cache: dict[tuple[str, int, int], bytes] = {}
_preview_cache_lock = threading.Lock()


def _read_statistics() -> dict[str, dict[str, float | int | str]]:
    if not STATISTICS_FILE.is_file():
        raise FileNotFoundError(f"Statistics CSV is missing: {STATISTICS_FILE}")

    with STATISTICS_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    by_name = {row["Index Name"]: row for row in rows}

    if set(by_name) != set(INDEX_NAMES):
        raise ValueError(
            f"Statistics CSV must contain exactly {INDEX_NAMES}; found {tuple(by_name)}."
        )

    statistics: dict[str, dict[str, float | int | str]] = {}
    for name in INDEX_NAMES:
        row = by_name[name]
        statistics[name] = {
            "minimum": float(row["Minimum"]),
            "maximum": float(row["Maximum"]),
            "mean": float(row["Mean"]),
            "median": float(row["Median"]),
            "standard_deviation": float(row["Standard Deviation"]),
            "valid_pixels": int(row["Valid Pixel Count"]),
            "invalid_pixels": int(row["Invalid Pixel Count"]),
        }
    return statistics


def _check_products() -> tuple[dict[str, dict[str, float | int | str]], dict[str, int | str]]:
    statistics = _read_statistics()
    if not INPUT_RASTER.is_file():
        raise FileNotFoundError(f"Input raster is missing: {INPUT_RASTER}")

    for name in INDEX_NAMES:
        path = GEOTIFF_DIR / f"{name}.tif"
        if not path.is_file():
            raise FileNotFoundError(f"Index GeoTIFF is missing: {path}")

    with rasterio.open(INPUT_RASTER) as source:
        if source.count != 6 or source.descriptions != ("B2", "B3", "B4", "B5", "B8", "B11"):
            raise ValueError(
                "The configured input must contain B2, B3, B4, B5, B8, B11 in that order."
            )
        if source.crs is None:
            raise ValueError("The configured input raster has no CRS.")
        if not all(math.isclose(size, 20.0) for size in source.res):
            raise ValueError(f"Expected 20 m source pixels; found {source.res}.")
        source_profile = {
            "width": source.width,
            "height": source.height,
            "crs": source.crs,
            "transform": source.transform,
            "resolution": source.res,
        }

    for name in INDEX_NAMES:
        with rasterio.open(GEOTIFF_DIR / f"{name}.tif") as index_raster:
            if (
                index_raster.crs != source_profile["crs"]
                or index_raster.transform != source_profile["transform"]
                or index_raster.width != source_profile["width"]
                or index_raster.height != source_profile["height"]
                or index_raster.dtypes != ("float32",)
                or index_raster.nodata != -9999.0
                or index_raster.descriptions != (name,)
            ):
                raise ValueError(f"{name}.tif does not match the verified source grid.")
            values = index_raster.read(1, masked=True).compressed()
            if values.size == 0:
                raise ValueError(f"{name}.tif contains no valid pixels.")
            display_min, display_max = np.percentile(values, [2, 98])
            if math.isclose(float(display_min), float(display_max)):
                padding = max(abs(float(display_min)) * 0.01, 1e-6)
                display_min -= padding
                display_max += padding
            statistics[name]["display_min"] = float(display_min)
            statistics[name]["display_max"] = float(display_max)

    metadata: dict[str, int | str] = {
        "study_area": STUDY_AREA,
        "acquisition_date": ACQUISITION_DATE,
        "collection": COLLECTION,
        "crs": CRS_LABEL,
        "resolution_m": source_profile["resolution"][0],
        "width": source_profile["width"],
        "height": source_profile["height"],
        "total_pixels": source_profile["width"] * source_profile["height"],
        "input_name": INPUT_RASTER.name,
        "valid_pixels": int(statistics["NDVI"]["valid_pixels"]),
    }
    metadata["invalid_pixels"] = int(metadata["total_pixels"]) - int(metadata["valid_pixels"])
    return statistics, metadata


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/api/dashboard")
def dashboard_data():
    try:
        statistics, metadata = _check_products()
    except (FileNotFoundError, ValueError, rasterio.errors.RasterioError) as error:
        app.logger.exception("Dashboard products could not be validated.")
        return jsonify({"error": str(error)}), 503

    indices = []
    for name in INDEX_NAMES:
        details = INDEX_DETAILS[name]
        stat = statistics[name]
        indices.append(
            {
                "name": name,
                "formula": details["formula"],
                "meaning": details["meaning"],
                "use": details["use"],
                "cmap": details["cmap"],
                "statistics": stat,
                "preview_url": f"/api/indices/{name}/preview.png",
                "download_url": f"/download/{name}",
            }
        )

    bands = [
        {"name": "B2", "label": "Blue"},
        {"name": "B3", "label": "Green"},
        {"name": "B4", "label": "Red"},
        {"name": "B5", "label": "Red Edge 1"},
        {"name": "B8", "label": "Near Infrared"},
        {"name": "B11", "label": "Shortwave Infrared 1"},
    ]
    return jsonify(
        {
            "metadata": metadata,
            "bands": bands,
            "indices": indices,
            "visualization_url": "/download/overview",
            "statistics_url": "/download/statistics",
            "summary_url": "/download/summary",
        }
    )


@app.get("/api/indices/<index_name>/preview.png")
def index_preview(index_name: str):
    if index_name not in INDEX_DETAILS:
        abort(404)

    raster_path = GEOTIFF_DIR / f"{index_name}.tif"
    try:
        with rasterio.open(raster_path) as source:
            cache_key = (index_name, raster_path.stat().st_mtime_ns, raster_path.stat().st_size)
            with _preview_cache_lock:
                cached = _preview_cache.get(cache_key)
            if cached is not None:
                response = app.response_class(cached, mimetype="image/png")
                response.headers["Cache-Control"] = "no-cache"
                return response

            data = source.read(1, masked=True).astype(np.float32)
    except (FileNotFoundError, rasterio.errors.RasterioError) as error:
        app.logger.exception("Unable to read index preview for %s.", index_name)
        return jsonify({"error": str(error)}), 503

    values = data.compressed()
    if values.size == 0:
        return jsonify({"error": f"{index_name} contains no valid pixels."}), 422

    display_min, display_max = np.percentile(values, [2, 98])
    if math.isclose(float(display_min), float(display_max)):
        padding = max(abs(float(display_min)) * 0.01, 1e-6)
        display_min -= padding
        display_max += padding

    color_map = plt.get_cmap(INDEX_DETAILS[index_name]["cmap"]).copy()
    color_map.set_bad("#d9d9d9", alpha=1.0)
    normalized = plt.Normalize(vmin=float(display_min), vmax=float(display_max))
    rgba = color_map(normalized(data.filled(np.nan)), bytes=True)

    image_buffer = io.BytesIO()
    Image.fromarray(rgba).save(image_buffer, format="PNG", optimize=True)
    image_bytes = image_buffer.getvalue()
    with _preview_cache_lock:
        _preview_cache[cache_key] = image_bytes

    response = app.response_class(image_bytes, mimetype="image/png")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/indices/<index_name>/pixel")
def pixel_value(index_name: str):
    if index_name not in INDEX_DETAILS:
        abort(404)
    try:
        row = int(request.args.get("row", ""))
        column = int(request.args.get("column", ""))
    except ValueError:
        return jsonify({"error": "Pixel row and column must be integers."}), 400

    raster_path = GEOTIFF_DIR / f"{index_name}.tif"
    try:
        with rasterio.open(raster_path) as source:
            if row < 0 or row >= source.height or column < 0 or column >= source.width:
                return jsonify({"error": "Selected pixel is outside the raster bounds."}), 400
            value = source.read(1, window=((row, row + 1), (column, column + 1)), masked=True)[0, 0]
            x, y = source.xy(row, column, offset="center")
            valid = not np.ma.is_masked(value) and math.isfinite(float(value))
    except (FileNotFoundError, rasterio.errors.RasterioError) as error:
        app.logger.exception("Unable to inspect %s pixel (%s, %s).", index_name, row, column)
        return jsonify({"error": str(error)}), 503

    return jsonify(
        {
            "index": index_name,
            "row": row,
            "column": column,
            "valid": valid,
            "value": float(value) if valid else None,
            "easting": x,
            "northing": y,
        }
    )


@app.get("/download/<product>")
def download(product: str):
    downloads = {
        "overview": (OVERVIEW_FILE, "sentinel2_all_7_indices.png"),
        "statistics": (STATISTICS_FILE, "index_statistics.csv"),
        "summary": (SUMMARY_FILE, "project_summary.txt"),
    }
    if product in INDEX_DETAILS:
        downloads[product] = (GEOTIFF_DIR / f"{product}.tif", f"{product}.tif")
    if product not in downloads:
        abort(404)

    path, download_name = downloads[product]
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
