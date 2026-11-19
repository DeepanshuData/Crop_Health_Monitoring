"""Google Earth Engine workflows and local geospatial analysis."""

import importlib.util
import os
from pathlib import Path


def _use_packaged_proj_database():
    """Prefer Rasterio's bundled PROJ data when an external PROJ_LIB is stale."""
    spec = importlib.util.find_spec("rasterio")
    if not spec or not spec.submodule_search_locations:
        return
    proj_data = Path(next(iter(spec.submodule_search_locations))) / "proj_data"
    if not (proj_data / "proj.db").is_file():
        return
    # This process-only override avoids changing PostgreSQL or system settings.
    os.environ["PROJ_LIB"] = str(proj_data)
    os.environ["PROJ_DATA"] = str(proj_data)


_use_packaged_proj_database()
