import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import rasterio
from rasterio.transform import from_origin

from gee.boundaries import DISTRICTS, load_district_feature
from gee.ndvi_stress_analysis import calculate_stressed_area, classify_stress
from gee.raster_utils import common_valid_change
from src.boundary_manager import validate_feature
from src.export_manager import geotiff_export_status, save_csv, start_geotiff_export
from src.stress_engine import classify_stress as classify_gee_stress


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

    def test_feature_collection_with_one_feature_is_valid(self):
        feature = {
            "type": "Feature",
            "properties": {"name": "Farm"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[76.9, 12.4], [76.95, 12.4],
                                 [76.95, 12.45], [76.9, 12.45],
                                 [76.9, 12.4]]],
            },
        }
        validated = validate_feature({
            "type": "FeatureCollection",
            "features": [feature],
        })
        self.assertEqual(validated["geometry"]["type"], "Polygon")

    def test_invalid_and_empty_geometries_are_rejected(self):
        invalid = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[76.9, 12.4], [76.95, 12.4],
                                 [76.9, 12.4]]],
            },
        }
        with self.assertRaises(ValueError):
            validate_feature(invalid)

        outside_range = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[181.0, 12.4], [182.0, 12.4],
                                 [182.0, 12.5], [181.0, 12.5],
                                 [181.0, 12.4]]],
            },
        }
        with self.assertRaises(ValueError):
            validate_feature(outside_range)

    def test_csv_export_has_district_specific_filename(self):
        import pandas as pd

        frame = pd.DataFrame([{
            "district": "mandya",
            "acquisition_date": "2025-07-11",
            "mean_ndvi": 0.45,
        }])
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.export_manager.PROJECT_ROOT", Path(temp_dir)):
                path = save_csv(frame, "mandya", "test_timeseries")
                self.assertEqual(path.name, "mandya_test_timeseries.csv")
                self.assertTrue(path.exists())

    def test_geotiff_export_submits_drive_task_without_requesting_download_url(self):
        image = object()
        geometry = object()
        task = type("Task", (), {"id": "task-123", "start": lambda self: None})()
        with patch("src.export_manager.ee.batch.Export.image.toDrive", return_value=task) as export:
            task_id = start_geotiff_export(image, geometry, "Mandya", "ndvi_change")

        self.assertEqual(task_id, "task-123")
        export.assert_called_once_with(
            image=image,
            description="mandya_ndvi_change",
            folder="crop_health_monitoring",
            fileNamePrefix="mandya_ndvi_change",
            region=geometry,
            scale=20,
            maxPixels=1e13,
            fileFormat="GeoTIFF",
            formatOptions={"noData": -9999},
        )

    def test_geotiff_export_status_reads_task_status(self):
        with patch(
            "src.export_manager.ee.data.getTaskStatus",
            return_value=[{"state": "COMPLETED"}],
        ) as get_status:
            status = geotiff_export_status("task-123")

        get_status.assert_called_once_with("task-123")
        self.assertEqual(status["state"], "COMPLETED")

    def test_gee_stress_map_masks_valid_pixels_instead_of_no_data(self):
        ndvi = MagicMock()
        valid = MagicMock()
        image = MagicMock()
        image.where.return_value = image
        image.updateMask.return_value = image
        image.toUint8.return_value = image
        image.rename.return_value = image
        image.clip.return_value = image
        ndvi.mask.return_value.reduce.return_value = valid

        with patch("src.stress_engine.ee.Image", return_value=image) as image_factory, patch(
            "src.stress_engine.ee.Reducer.min"
        ):
            result = classify_gee_stress(ndvi)

        image_factory.assert_called_once_with(255)
        image.updateMask.assert_called_once_with(valid)
        self.assertIs(result["classification"], image)


if __name__ == "__main__":
    unittest.main()
