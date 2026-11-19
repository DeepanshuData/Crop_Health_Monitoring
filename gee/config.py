"""Shared project paths and Earth Engine settings."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
BOUNDARY_DIR = DATA_DIR / "boundaries"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
EE_PROJECT = "agri-satellite-monitoring"
SENTINEL2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
DEFAULT_START_DATE = "2025-01-01"
DEFAULT_END_DATE = "2026-01-01"
TARGET_DATES = ("2025-07-15", "2025-10-15")
SEARCH_WINDOW_DAYS = 7
MAX_SCENE_CLOUD_PERCENT = 80
MAX_TIME_SERIES_RECORDS = 24
ANALYSIS_SCALE_METERS = 20
STRESS_THRESHOLD = 0.30


def district_output_dirs(district):
    """Create and return the standard output directories for a district."""
    root = OUTPUT_DIR / district.lower()
    paths = {
        "root": root,
        "maps": root / "maps",
        "charts": root / "charts",
        "reports": root / "reports",
        "timeseries": root / "timeseries",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
