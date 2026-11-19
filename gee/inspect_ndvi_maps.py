"""Print metadata and valid-pixel statistics for downloaded NDVI GeoTIFFs."""

import argparse
from pathlib import Path

from gee.config import PROJECT_ROOT
import numpy as np
import rasterio


DEFAULT_FILES = {
    "First Date NDVI": PROJECT_ROOT / "outputs" / "NDVI_First_Date.tif",
    "Second Date NDVI": PROJECT_ROOT / "outputs" / "NDVI_Second_Date.tif",
    "NDVI Change": PROJECT_ROOT / "outputs" / "NDVI_Change_Map.tif",
}
RASTER_ARGUMENTS = {
    "first": "First Date NDVI",
    "second": "Second Date NDVI",
    "change": "NDVI Change",
}


def inspect_raster(name, file_path):
    with rasterio.open(file_path) as source:
        if source.count < 1:
            raise ValueError(f"{file_path} contains no raster bands.")
        data = source.read(1, masked=True)
        values = data.compressed()
        print(f"\n{name}\n{'=' * len(name)}")
        print("Width:", source.width)
        print("Height:", source.height)
        print("Bands:", source.count)
        print("CRS:", source.crs)
        print("Resolution:", source.res)
        print("NoData value:", source.nodata)
        print("Valid pixels:", values.size)
        if values.size:
            print("Minimum:", float(np.min(values)))
            print("Maximum:", float(np.max(values)))
            print("Mean:", float(np.mean(values)))
        else:
            print("No valid pixels found.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key, name in RASTER_ARGUMENTS.items():
        parser.add_argument(f"--{key}", type=Path, default=DEFAULT_FILES[name])
    args = parser.parse_args(argv)
    for key, name in RASTER_ARGUMENTS.items():
        inspect_raster(name, getattr(args, key))


if __name__ == "__main__":
    main()
