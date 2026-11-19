# Initial Project Audit

## Baseline

- The repository had no commits; all workspace files were untracked.
- Existing functionality was limited to stand-alone Earth Engine scripts,
   local raster inspection/stress scripts, one sample polygon, and existing
   outputs.
- No `README.md`, `requirements.txt`, or test suite existed.
- No `.venv` was present during inspection; the active shell used system
  Python 3.13.7.
- Existing local outputs include four GeoTIFFs, two CSVs, and three charts.
  They were retained and not used as proof of new multi-district results.

## Findings and changes

| Finding | Change |
| --- | --- |
| `sentinel2_processor.py` referenced undefined `point` and initialized GEE in its test entry point without checking an empty collection. | Replaced the sample runner with import-safe shared mask/index functions. |
| Multiple scripts implemented different SCL masks. | Centralized a documented mask retaining SCL 2, 4, 5, 6 only. |
| Time-series module initialized GEE at import, used one shared output filename, and fetched the full collection with `getInfo()`. | Moved initialization to `main.py`, bounded records, and created district-specific CSVs/charts. |
| Scene selection used scene cloud percentage only and treated overlapping tiles as separate observations. | Tiles are mosaicked per acquisition date; candidate dates are ranked by valid masked B8 pixel count inside the district. |
| Date comparison did not explicitly report valid-mask overlap. | The workflow applies the common mask explicitly and records per-date/common counts and common area. The existing rasters were also checked: 2,436 first-date pixels, 8,890 second-date pixels, and 144 common/change pixels; the old change raster matches second-minus-first on that overlap. The lower change count is therefore consistent with the shared clear-pixel support, not evidence that masked pixels were set to zero. |
| Existing stress analysis omitted total and NoData pixels, used fixed paths, and did not verify its output. | Added NoData-aware counts, CRS-unit-aware pixel area, district output paths, and post-write raster validation. |
| Only a synthetic Mandya sample boundary existed. | Added three valid geoBoundaries ADM2 polygons, preserving the original sample file. |
| Existing outputs use a 10 m UTM 43N grid, but acquisition dates are not embedded in all rasters. | Existing files were retained; newly generated acquisition dates are written in per-run reports. |
| `PROJ_LIB` resolved to PostgreSQL's PostGIS PROJ database, too old for the installed Rasterio. | Project imports set `PROJ_LIB` and `PROJ_DATA` to Rasterio's packaged database in the current Python process only; PostgreSQL files and system settings are not changed. |
| The project had no web interface. | Added a Streamlit application with a dashboard and six analysis/export pages backed by reusable modules in `src/`. |
| Live GEE web-backend smoke testing was missing. | Added `tests/live_gee_smoke.py`; it completed for Mandya, Mysuru and Hassan using October 2025 imagery. |

## Scope and verification limitations

The local audit did not establish that the existing CSV statistics, GeoTIFF
values, or charts were produced by a live Earth Engine run. No local `.venv`
was available. A live GEE integration requires credentials, network access,
project permissions, and export permissions; it must be reported separately
from local tests. Earth Engine exports are asynchronous Drive tasks and are
not automatically downloaded into the local output folders.
