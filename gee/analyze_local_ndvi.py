"""Inspect district NDVI GeoTIFFs and validate common-pixel change."""

import argparse
import json
from pathlib import Path

import numpy as np
from gee.raster_utils import common_valid_change
import rasterio


ROOT = Path(__file__).resolve().parents[1]
TARGET_DATES = {"first": "2025-07-15", "second": "2025-10-15"}


def read_raster(path):
    with rasterio.open(path) as src:
        data = src.read(1)
        valid = (src.read_masks(1) > 0) & np.isfinite(data)
        return {
            "data": data,
            "valid": valid,
            "width": src.width,
            "height": src.height,
            "bands": src.count,
            "crs": str(src.crs),
            "transform": tuple(src.transform),
            "resolution": src.res,
            "dtype": src.dtypes[0],
            "nodata": src.nodata,
            "tags": src.tags(),
        }


def summarize(name, raster):
    data = raster["data"]
    valid = raster["valid"]
    values = data[valid]
    return {
        "width": raster["width"],
        "height": raster["height"],
        "bands": raster["bands"],
        "crs": raster["crs"],
        "transform": raster["transform"],
        "resolution": raster["resolution"],
        "dtype": raster["dtype"],
        "nodata_metadata": raster["nodata"],
        "total_pixels": int(data.size),
        "finite_pixels": int(np.isfinite(data).sum()),
        "nan_pixels": int(np.isnan(data).sum()),
        "infinite_pixels": int(np.isinf(data).sum()),
        "valid_pixels": int(valid.sum()),
        "valid_percent": float(valid.mean() * 100),
        "min": float(values.min()) if values.size else None,
        "max": float(values.max()) if values.size else None,
        "mean": float(values.mean()) if values.size else None,
        "embedded_tags": raster["tags"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--first",
        type=Path,
        default=ROOT / "outputs" / "NDVI_First_Date.tif",
        help="First-date NDVI GeoTIFF.",
    )
    parser.add_argument(
        "--second",
        type=Path,
        default=ROOT / "outputs" / "NDVI_Second_Date.tif",
        help="Second-date NDVI GeoTIFF.",
    )
    parser.add_argument(
        "--change",
        type=Path,
        default=ROOT / "outputs" / "NDVI_Change_Map.tif",
        help="Second-minus-first change GeoTIFF.",
    )
    args = parser.parse_args(argv)
    paths = {"first": args.first, "second": args.second, "change": args.change}
    rasters = {
        name: read_raster(path)
        for name, path in paths.items()
    }
    report = {
        name: summarize(name, raster)
        for name, raster in rasters.items()
    }

    first = rasters["first"]
    second = rasters["second"]
    change = rasters["change"]
    grids_match = all(
        (first[key] == second[key] == change[key])
        for key in ("width", "height", "crs", "transform")
    )
    grids_match = grids_match and first["crs"] != "None"
    report["grid_compatibility"] = {
        "all_grids_match": grids_match,
        "first_matches_second": all(
            first[key] == second[key]
            for key in ("width", "height", "crs", "transform")
        ),
    }
    if not grids_match:
        raise ValueError("The input rasters are not on the same grid.")

    _, _, expected_change, common = common_valid_change(
        first["data"],
        second["data"],
        first["valid"],
        second["valid"],
    )
    change_valid = change["valid"]
    total = int(common.size)
    union_count = int((first["valid"] | second["valid"]).sum())
    report["comparison"] = {
        "requested_target_dates": TARGET_DATES,
        "actual_acquisition_dates": (
            {
                "first": first["tags"].get("ACQUISITION_DATE"),
                "second": second["tags"].get("ACQUISITION_DATE"),
            }
        ),
        "overlapping_valid_pixels": int(common.sum()),
        "overlap_percent_of_grid": float(common.mean() * 100),
        "overlap_percent_of_first_valid": float(
            common.sum() / first["valid"].sum() * 100
        ) if first["valid"].any() else 0.0,
        "overlap_percent_of_second_valid": float(
            common.sum() / second["valid"].sum() * 100
        ) if second["valid"].any() else 0.0,
        "overlap_percent_of_valid_union": float(
            common.sum() / union_count * 100
        ) if union_count else 0.0,
        "change_valid_pixels_match_input_overlap": bool(
            np.array_equal(change_valid, common)
        ),
        "change_matches_second_minus_first": bool(
            np.allclose(
                change["data"][common],
                expected_change[common],
                rtol=1e-6,
                atol=1e-7,
            )
        ),
        "total_grid_pixels": total,
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
