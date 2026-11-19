import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from gee.boundaries import DISTRICTS, load_district_feature
from gee.ndvi_stress_analysis import calculate_stressed_area, classify_stress
from gee.raster_utils import common_valid_change


ROOT = Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def test_all_district_boundaries_are_valid_and_identified(self):
        for district in DISTRICTS:
            with self.subTest(district=district):
                feature = load_district_feature(district)
                self.assertEqual(feature["properties"]["district"].lower(), district)

    def test_unknown_district_is_rejected(self):
        with self.assertRaises(ValueError):
            load_district_feature("not-a-district")


class LocalProcessingTests(unittest.TestCase):
    def test_common_change_uses_only_valid_intersection(self):
        first = np.array([[0.2, 0.4], [np.nan, 0.8]])
        second = np.array([[0.3, 0.1], [0.5, 0.9]])
        first_valid = np.array([[True, True], [True, False]])
        second_valid = np.array([[True, False], [True, True]])
        _, _, change, common = common_valid_change(
            first, second, first_valid, second_valid
        )
        np.testing.assert_array_equal(common, [[True, False], [False, False]])
        self.assertAlmostEqual(float(change[0, 0]), 0.1)
        self.assertEqual(int(np.isfinite(change).sum()), 1)

    def test_stress_classification_preserves_nodata(self):
        data = np.array([[0.29, 0.30], [np.nan, 0.1]])
        valid = np.array([[True, True], [True, False]])
        result, usable = classify_stress(data, valid)
        np.testing.assert_array_equal(result, [[1, 0], [255, 255]])
        self.assertEqual(int(usable.sum()), 2)

    def test_stress_raster_preserves_grid_and_reports_pixel_areas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "input.tif"
            profile = {
                "driver": "GTiff",
                "height": 2,
                "width": 2,
                "count": 1,
                "dtype": "float32",
                "crs": "EPSG:32643",
                "transform": from_origin(500000, 1500000, 10, 10),
                "nodata": -9999,
            }
            with rasterio.open(source_path, "w", **profile) as output:
                output.write(np.array([[0.2, 0.4], [-9999, np.nan]], dtype="float32"), 1)
            result = calculate_stressed_area(source_path, root, "mandya")
            with rasterio.open(result["raster"]) as stress:
                self.assertEqual(stress.transform, profile["transform"])
                self.assertEqual(stress.crs.to_epsg(), 32643)
                self.assertEqual(stress.nodata, 255)
                np.testing.assert_array_equal(stress.read(1), [[1, 0], [255, 255]])
            stats = result["statistics"]
            self.assertEqual(stats["total_pixels"], 4)
            self.assertEqual(stats["valid_pixels"], 2)
            self.assertEqual(stats["nodata_pixels"], 2)
            self.assertAlmostEqual(stats["pixel_area_m2"], 100)
            self.assertAlmostEqual(stats["valid_area_ha"], 0.02)

    def test_boundary_files_are_geojson(self):
        for district in DISTRICTS:
            with self.subTest(district=district):
                path = ROOT / "data" / "boundaries" / f"{district}.geojson"
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(document["type"], "Feature")


if __name__ == "__main__":
    unittest.main()
