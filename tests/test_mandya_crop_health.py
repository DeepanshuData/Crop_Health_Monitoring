from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.gee_service import _add_indices, _prepare_collection
from src.mandya_crop_health import (
    MANDYA_INDEX_NAMES,
    load_mandya_monthly_ndvi,
    load_mandya_products,
    load_uploaded_ndvi_raster,
    read_mandya_index_overlay,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WGS84_GEOGRAPHIC_WKT = (
    'GEOGCS["WGS 84",DATUM["World Geodetic System 1984",'
    'SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


class MandyaCropHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.raster_directory = (
            self.project_root / "outputs" / "mandya_spectral_indices" / "geotiff"
        )
        self.raster_directory.mkdir(parents=True)
        profile = {
            "driver": "GTiff",
            "width": 3,
            "height": 2,
            "count": 1,
            "dtype": "float32",
            "crs": WGS84_GEOGRAPHIC_WKT,
            "transform": from_origin(76.5, 13.0, 0.00018, 0.00018),
        }
        data = np.array([[1.0, np.nan, 3.0], [4.0, 5.0, np.nan]], dtype=np.float32)
        for name in MANDYA_INDEX_NAMES:
            with rasterio.open(
                self.raster_directory / f"Mandya_{name}.tif", "w", **profile
            ) as raster:
                raster.write(data, 1)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_raster_statistics_exclude_non_finite_pixels_and_preserve_grid(self) -> None:
        products = load_mandya_products(self.project_root)
        self.assertEqual(products["statistics"]["valid_pixels"], 4)
        self.assertEqual(products["statistics"]["minimum"], 1.0)
        self.assertEqual(products["statistics"]["maximum"], 5.0)
        self.assertEqual(products["statistics"]["mean"], 3.25)
        self.assertEqual(products["grid"]["crs_label"], "WGS 84 (geographic)")
        self.assertEqual(products["grid"]["resolution"], (0.00018, 0.00018))

    def test_map_overlay_keeps_georeferenced_bounds_and_transparent_invalid_pixels(self) -> None:
        overlay = read_mandya_index_overlay("NDVI", self.project_root)
        self.assertAlmostEqual(overlay["bounds"][0][0], 12.99964)
        self.assertAlmostEqual(overlay["bounds"][0][1], 76.5)
        self.assertAlmostEqual(overlay["bounds"][1][0], 13.0)
        self.assertAlmostEqual(overlay["bounds"][1][1], 76.50054)
        self.assertEqual(overlay["image"].shape, (2, 3, 4))
        self.assertEqual(int(overlay["image"][0, 1, 3]), 0)

    def test_saved_monthly_series_keeps_real_month_gaps(self) -> None:
        monthly = load_mandya_monthly_ndvi(PROJECT_ROOT)
        months = monthly["month"].tolist()
        self.assertEqual(len(months), 10)
        self.assertNotIn("2026-06", months)
        self.assertNotIn("2026-07", months)
        self.assertNotIn("2026-08", months)

    def test_uploaded_geotiff_is_analyzed_in_memory(self) -> None:
        raster_bytes = (self.raster_directory / "Mandya_NDVI.tif").read_bytes()
        uploaded = load_uploaded_ndvi_raster(raster_bytes)
        self.assertEqual(uploaded["statistics"]["valid_pixels"], 4)
        self.assertEqual(uploaded["statistics"]["mean"], 3.25)
        self.assertEqual(uploaded["grid"]["crs_label"], "WGS 84 (geographic)")

    def test_gee_index_calculations_use_expected_methods_and_bands(self) -> None:
        class FakeValue:
            def __getattr__(self, _name):
                return lambda *_args: FakeValue()

        class FakeImage:
            def __init__(self) -> None:
                self.normalized_bands = []
                self.expressions = []

            def select(self, _band):
                return FakeValue()

            def normalizedDifference(self, bands):
                self.normalized_bands.append(bands)
                return FakeValue()

            def expression(self, expression, _variables):
                self.expressions.append(expression)
                return FakeValue()

            def addBands(self, _bands):
                return self

        image = FakeImage()
        _add_indices(image)
        self.assertEqual(image.normalized_bands, [["B8", "B4"], ["B3", "B8"]])
        self.assertEqual(
            image.expressions,
            ["(NIR - RED_EDGE) / (NIR + RED_EDGE)"],
        )

    def test_strict_cloud_limit_uses_less_than_ten_percent(self) -> None:
        class FakeCollection:
            def __init__(self) -> None:
                self.filters = []

            def filterBounds(self, _geometry):
                return self

            def filterDate(self, _start, _end):
                return self

            def filter(self, item):
                self.filters.append(item)
                return self

            def map(self, _callback):
                return self

            def sort(self, _property):
                return self

        class FakeFilter:
            @staticmethod
            def lt(property_name, value):
                return ("lt", property_name, value)

            @staticmethod
            def lte(property_name, value):
                return ("lte", property_name, value)

        collection = FakeCollection()

        class FakeEarthEngine:
            Filter = FakeFilter
            ImageCollection = staticmethod(lambda _collection_name: collection)

        _prepare_collection(
            FakeEarthEngine,
            object(),
            date(2025, 11, 14),
            date(2026, 11, 14),
            10,
            exclusive_cloud_limit=True,
        )
        self.assertIn(("lt", "CLOUDY_PIXEL_PERCENTAGE", 10), collection.filters)


if __name__ == "__main__":
    unittest.main()
