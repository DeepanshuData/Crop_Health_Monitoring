# Crop Health Monitoring Architecture

## Processing layers

1. `data/boundaries/` contains the geoBoundaries administrative district
   Features in WGS 84.
2. `gee/boundaries.py` validates a named polygon before converting it to an
   Earth Engine geometry.
3. `gee/sentinel2_fetcher.py` filters Sentinel-2 SR Harmonized scenes and
   chooses from low-cloud candidates using district-specific valid-pixel
   coverage.
4. `gee/sentinel2_processor.py` owns the shared SCL mask and NDVI, NDRE, and
   NDWI calculations.
5. Date comparison computes a common observation mask; time-series processing
   returns a bounded number of per-scene summaries.
6. `main.py` coordinates districts, launches the requested Drive exports,
   writes local reports and manifests, and continues after district failures.
7. `gee/ndvi_stress_analysis.py` handles local raster classification and
   verifies output grid metadata after writing.

## Web application layers

The Streamlit application uses a thin UI over reusable backend engines:

- `app/app.py` is the entry point; `app/pages/*.py` provides the dashboard,
  crop-health, time-series, comparison, stress, and export views.
- `app/components/` contains shared sidebar, map, metric, chart and style
  components.
- `src/boundary_manager.py` validates uploaded or bundled GeoJSON, preserves
  uploads, converts boundaries to Earth Engine geometries and calculates area.
- `src/analysis_engine.py` owns GEE initialization and NDVI/NDRE/NDWI analysis.
- `src/timeseries_engine.py` builds bounded, acquisition-date time-series data.
- `src/comparison_engine.py` masks NDVI change to common valid observations.
- `src/stress_engine.py` calculates threshold-based stress and area totals.
- `src/export_manager.py` writes CSV/JSON local outputs and submits
  asynchronous Earth Engine GeoTIFF exports to Google Drive. The Streamlit
  export controls show the current task status without making large
  synchronous download-URL requests.

The existing `gee/` modules remain reusable CLI implementation surfaces and
do not execute GEE work on import. The web application initializes GEE only
after the sidebar boundary is validated and an analysis is requested.

## NoData and area semantics

Cloud and invalid pixels stay masked through the index and change calculations.
For local stress rasters they are encoded as `255`; they are not included in
stressed or non-stressed totals. The local raster processor calculates area
from the affine pixel dimensions and projected CRS unit conversion. The
Earth Engine workflow uses `ee.Image.pixelArea()` for regional areas.

## External services and outputs

Earth Engine initialization occurs in the command entry point, not at module
import. GeoTIFF creation is an asynchronous Google Drive export task; local
time-series CSVs, charts, JSON summaries, and task manifests are separated by
district and run identifier. No export task is launched merely by importing a
module.
