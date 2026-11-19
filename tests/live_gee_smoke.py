"""Optional live Earth Engine smoke test for the web backend."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis_engine import (
    calculate_analysis,
    fetch_analysis_image,
    initialize_earth_engine,
)
from src.boundary_manager import district_feature, feature_to_ee


if __name__ == "__main__":
    initialize_earth_engine()
    for district in ("mandya", "mysuru", "hassan"):
        geometry = feature_to_ee(district_feature(district))
        image, metadata = fetch_analysis_image(
            geometry,
            "2025-10-01",
            "2025-11-01",
            max_cloud_percentage=80,
        )
        result = calculate_analysis(geometry, image)
        statistics = result["statistics"]
        print(
            district,
            metadata["acquisition_date"],
            round(statistics.get("NDVI_mean", -999), 4),
            round(statistics.get("NDRE_mean", -999), 4),
            round(statistics.get("NDWI_mean", -999), 4),
        )
