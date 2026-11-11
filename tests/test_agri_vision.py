from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

import rasterio

from src.crop_health_data import INDEX_NAMES, index_geotiff_bytes, load_verified_scene
from src.gee_service import validate_request
from src.report_generator import build_pdf_report, build_statistics_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_GEOJSON = (
    '{"type":"Polygon","coordinates":[[[76.5,12.0],[76.6,12.0],'
    '[76.6,12.1],[76.5,12.1],[76.5,12.0]]]}'
)


class AgriVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene = load_verified_scene(PROJECT_ROOT)

    def test_local_scene_has_all_eight_index_summaries(self) -> None:
        self.assertEqual(self.scene["acquisition_date"], "2025-02-06")
        self.assertEqual(set(self.scene["statistics"]), set(INDEX_NAMES))
        self.assertEqual(self.scene["dimensions"], (498, 499))
        self.assertGreater(self.scene["base_valid_pixels"], 0)

    def test_geotiff_download_preserves_source_grid(self) -> None:
        for index_name in ("NDVI", "NDWI"):
            output = index_geotiff_bytes(self.scene, index_name)
            with rasterio.MemoryFile(output) as memory_file:
                with memory_file.open() as raster:
                    self.assertEqual((raster.width, raster.height), self.scene["dimensions"])
                    self.assertEqual(raster.crs, self.scene["source_crs"])
                    self.assertEqual(raster.transform, self.scene["source_transform"])
                    self.assertEqual(raster.dtypes, ("float32",))
                    self.assertEqual(raster.nodata, -9999.0)

    def test_report_and_statistics_downloads(self) -> None:
        self.assertTrue(build_statistics_csv(self.scene).startswith(b"\xef\xbb\xbf"))
        self.assertTrue(build_pdf_report(self.scene).startswith(b"%PDF-"))

    def test_geojson_validation(self) -> None:
        validated = validate_request(SAMPLE_GEOJSON, date(2025, 1, 1), date(2025, 2, 1), 30)
        self.assertEqual(validated["type"], "Polygon")
        with self.assertRaisesRegex(ValueError, "longitude/latitude"):
            validate_request(
                '{"type":"Polygon","coordinates":[[[181,0],[181,1],[180,1],[181,0]]]}',
                date(2025, 1, 1),
                date(2025, 2, 1),
                30,
            )
        with self.assertRaisesRegex(ValueError, "on or after"):
            validate_request(SAMPLE_GEOJSON, date(2025, 2, 1), date(2025, 1, 1), 30)
        open_hole = (
            '{"type":"Polygon","coordinates":['
            '[[0,0],[4,0],[4,4],[0,0]],'
            '[[1,1],[2,1],[2,2],[1,2]]]}'
        )
        with self.assertRaisesRegex(ValueError, "ring must be closed"):
            validate_request(open_hole, date(2025, 1, 1), date(2025, 2, 1), 30)


if __name__ == "__main__":
    unittest.main()
