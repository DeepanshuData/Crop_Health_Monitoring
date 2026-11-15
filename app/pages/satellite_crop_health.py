from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
import sys

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.common import inject_styles
from src.mandya_crop_health import (
    MANDYA_INDEX_NAMES,
    load_mandya_monthly_ndvi,
    load_mandya_products,
    load_mandya_workflow_summary,
    load_uploaded_ndvi_raster,
    read_mandya_index_overlay,
)

inject_styles()


@st.cache_data(show_spinner=False)
def _load_products() -> dict:
    return load_mandya_products(PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def _load_monthly_ndvi() -> pd.DataFrame:
    return load_mandya_monthly_ndvi(PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def _load_workflow_summary() -> dict:
    return load_mandya_workflow_summary(PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def _load_overlay(index_name: str) -> dict:
    return read_mandya_index_overlay(index_name, PROJECT_ROOT)


st.markdown(
    """
    <div class="agri-topline satellite-dark-page">
      <div>
        <div class="agri-kicker">AGRIVISION &nbsp;·&nbsp; SATELLITE CROP HEALTH</div>
        <h1 class="agri-title">Mandya crop health monitoring</h1>
      </div>
      <div class="scene-badge">
        <span class="scene-live"></span>
        <span><b>Mandya, Karnataka</b><small>Sentinel-2 · archived 365-day GEE workflow</small></span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Saved satellite products are shown below. The raster footprint is not a surveyed farm boundary, "
    "and vegetation indices are not agronomic diagnoses."
)

try:
    products = _load_products()
    monthly = _load_monthly_ndvi()
    workflow = _load_workflow_summary()
except (FileNotFoundError, ValueError, OSError) as error:
    st.error(f"Mandya monitoring products could not be loaded: {error}")
    st.info("Check the Mandya index GeoTIFFs and saved GEE summary data, then reload this page.")
    st.stop()

project = os.environ.get("EARTHENGINE_PROJECT", "").strip()
query_end = date.today()
query_start = query_end - timedelta(days=365)
live_result = st.session_state.get("mandya_live_result")
live_error = st.session_state.pop("mandya_live_error", None)
if live_error:
    st.error(f"Live Earth Engine analysis failed: {live_error}")

if project:
    with st.form("mandya_live_analysis"):
        st.caption(
            f"Query Mandya for {query_start} through {query_end}, filtering scene cloud metadata "
            "to <10% and applying the SCL cloud/shadow mask."
        )
        farm_file = st.file_uploader(
            "Optional farm boundary GeoJSON",
            type=("geojson", "json"),
            help="Upload a Polygon, MultiPolygon, Feature, or FeatureCollection. "
            "Each feature is summarized separately using reduceRegions.",
            max_upload_size=2,
            key="mandya_farm_boundaries",
        )
        submitted = st.form_submit_button(
            "Run live Mandya GEE analysis",
            type="primary",
        )
    if submitted:
        from src.gee_service import EarthEngineError, mandya_sentinel2_time_series

        try:
            farm_geojson = (
                farm_file.getvalue().decode("utf-8-sig") if farm_file is not None else None
            )
            with st.spinner(
                "Loading Sentinel-2, applying the SCL mask, calculating indices and summaries…"
            ):
                live_result = mandya_sentinel2_time_series(
                    query_start,
                    query_end,
                    project=project,
                    farm_geojson_text=farm_geojson,
                )
            st.session_state["mandya_live_result"] = live_result
            st.session_state.pop("mandya_live_error", None)
            st.rerun()
        except (EarthEngineError, ValueError, UnicodeDecodeError) as error:
            st.session_state["mandya_live_error"] = str(error)
            st.rerun()
else:
    st.info(
        "Live Earth Engine access is not configured in this app. The archived Mandya products "
        "remain available; configure Earth Engine below to load live imagery, reducers, and "
        "date-wise observations."
    )
    with st.expander("Configure a Google Earth Engine project"):
        st.write(
            "The Google account and Cloud project must be registered and enabled for Earth Engine. "
            "Authentication stays on the server; do not paste credentials or private keys into the app."
        )
        st.code(
            r".\.venv\Scripts\python.exe -m pip install -r requirements.txt"
            "\n"
            r".\.venv\Scripts\earthengine authenticate"
            "\n"
            r"$env:EARTHENGINE_PROJECT = 'your-earth-engine-enabled-project'"
            "\n"
            r".\.venv\Scripts\streamlit.exe run app\app.py",
            language="powershell",
        )

if live_result:
    window_start = pd.to_datetime(live_result["start_date"]).date()
    window_end = pd.to_datetime(live_result["end_date"]).date()
    district_mean = live_result["statistics"]["NDVI_mean"]
    district_mean_source = f"{window_start} to {window_end} · median composite"
    scene_count = live_result["scene_count"]
    if district_mean is None:
        st.warning("The live composite has no valid district-wide NDVI pixels.")
        district_mean = float("nan")
else:
    window_start = pd.to_datetime(workflow["window_start"]).date()
    window_end = pd.to_datetime(workflow["window_end"]).date()
    district_mean = workflow["district_mean_ndvi_reduce_regions"]
    district_mean_source = f"{workflow['district_mean_date']} · first scene"
    scene_count = workflow["scene_count"]
ndvi_statistics = products["statistics"]

metrics = st.columns(4)
district_mean_label = f"{district_mean:.4f}" if pd.notna(district_mean) else "No data"
metrics[0].metric("District mean NDVI", district_mean_label, district_mean_source)
metrics[1].metric("12-month NDVI raster mean", f"{ndvi_statistics['mean']:.4f}")
metrics[2].metric(
    "Valid NDVI raster pixels",
    f"{ndvi_statistics['valid_pixels']:,}",
    f"{products['grid']['width']:,} × {products['grid']['height']:,} grid",
)
metrics[3].metric("Sentinel-2 scenes", f"{scene_count:,}")

st.markdown(
    '<div class="field-note"><strong>District, not farm, statistics</strong><br>'
    f'The archived district reducer results are for {workflow["district_mean_date"]}. '
    f'reduceRegion: {workflow["district_mean_ndvi_reduce_region"]:.8f}; '
    f'reduceRegions: {workflow["district_mean_ndvi_reduce_regions"]:.8f} '
    f'at {workflow["district_reducer_scale_m"]} m. Live farm results are computed only when farm '
    'polygons are uploaded; no farm-level values are invented.</div>',
    unsafe_allow_html=True,
)

reducer_rows = [
    {
        "Source": "Archived reduceRegion · first scene",
        "Date / period": workflow["district_mean_date"],
        "Mean NDVI": workflow["district_mean_ndvi_reduce_region"],
    },
    {
        "Source": "Archived reduceRegions · district feature",
        "Date / period": workflow["district_mean_date"],
        "Mean NDVI": workflow["district_mean_ndvi_reduce_regions"],
    },
]
if live_result:
    reducer_rows.extend(
        [
            {
                "Source": "Live reduceRegion · median composite",
                "Date / period": f"{window_start} to {window_end}",
                "Mean NDVI": live_result["statistics"].get("NDVI_mean"),
            },
            {
                "Source": "Live reduceRegions · district feature",
                "Date / period": f"{window_start} to {window_end}",
                "Mean NDVI": live_result["district_statistics"]["mean_ndvi"],
            },
        ]
    )
with st.expander("District reducer results"):
    st.dataframe(pd.DataFrame(reducer_rows), hide_index=True, width="stretch")

if live_result and live_result["farm_statistics"]:
    st.markdown("#### Uploaded farm polygon statistics")
    st.caption(
        "These values summarize only valid pixels in the Mandya-clipped raster footprint "
        "for each uploaded feature."
    )
    st.dataframe(
        pd.DataFrame(live_result["farm_statistics"]).rename(
            columns={"farm": "Farm", "mean_ndvi": "Mean NDVI"}
        ),
        hide_index=True,
        width="stretch",
    )

st.markdown('<div class="section-title">Satellite index map</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Select an exported Mandya index raster. The overlay uses the '
    'source GeoTIFF bounds, CRS, and grid, or use live Earth Engine map tiles when available.</div>',
    unsafe_allow_html=True,
)
grid = products["grid"]
map_options = (
    ("True-colour composite", *MANDYA_INDEX_NAMES)
    if live_result
    else MANDYA_INDEX_NAMES
)
map_layer = st.selectbox("Map layer", map_options, key="mandya_index_layer")
west, south, east, north = grid["bounds"]
satellite_map = folium.Map(
    location=[(south + north) / 2, (west + east) / 2],
    zoom_start=8,
    tiles="OpenStreetMap",
    control_scale=True,
)

if live_result:
    ee_layer = "true_color" if map_layer == "True-colour composite" else map_layer
    folium.TileLayer(
        tiles=live_result["tiles"][ee_layer],
        attr="Google Earth Engine · COPERNICUS/S2_SR_HARMONIZED",
        name=f"Mandya · {map_layer} · live 365-day median",
        overlay=True,
        control=True,
    ).add_to(satellite_map)
    satellite_map.fit_bounds([[south, west], [north, east]])
    folium.LayerControl(collapsed=False).add_to(satellite_map)
    st_folium(
        satellite_map,
        height=470,
        use_container_width=True,
        key=f"mandya-live-map-{ee_layer}",
    )
    st.caption(
        "Live map tiles use the cloud-filtered, SCL-masked Sentinel-2 median composite "
        f"for {window_start} through {window_end}."
    )
else:
    try:
        overlay = _load_overlay(map_layer)
    except (FileNotFoundError, ValueError, OSError) as error:
        st.error(f"The {map_layer} map layer is unavailable: {error}")
    else:
        folium.raster_layers.ImageOverlay(
            image=overlay["image"],
            bounds=overlay["bounds"],
            opacity=0.8,
            name=f"Mandya {map_layer}",
            interactive=True,
            cross_origin=False,
            zindex=2,
        ).add_to(satellite_map)
        satellite_map.fit_bounds(overlay["bounds"])
        folium.LayerControl(collapsed=False).add_to(satellite_map)
        st_folium(
            satellite_map,
            height=470,
            use_container_width=True,
            key=f"mandya-index-map-{map_layer}",
        )
        st.caption(
            f"{map_layer} display stretch: {overlay['display_min']:.3f}–"
            f"{overlay['display_max']:.3f} (2nd–98th percentile). "
            f"Raster bounds show the exported footprint, not an administrative boundary."
        )
    st.caption(
        "No Mandya true-colour composite GeoTIFF is available in the saved outputs; "
        "the selectable overlays are the processed index rasters."
    )

st.caption(
    f"GeoTIFF georeferencing preserved: {grid['crs_label']} · "
    f"{grid['resolution'][0]:.9f}° × {grid['resolution'][1]:.9f}° native pixel spacing · "
    f"window {window_start} to {window_end}."
)

if live_result:
    observations = pd.DataFrame(live_result["observations"])
    observations["date"] = pd.to_datetime(observations["date"])
    monthly = (
        observations.assign(month_date=observations["date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month_date", as_index=False)["NDVI"]
        .mean()
        .rename(columns={"NDVI": "mean_ndvi"})
    )
    datewise = observations.rename(columns={"date": "acquisition_date", "NDVI": "mean_ndvi"})
    st.caption(
        f"Live result: {live_result['scene_count']:,} matching scenes · "
        f"{len(datewise):,} dated rows · cloud cover <10% · SCL mask applied."
    )
else:
    datewise = None
    st.caption(
        f"Archived monthly means from {monthly['month'].iloc[0]} through "
        f"{monthly['month'].iloc[-1]}; missing months have no saved observation."
    )

plot_monthly = monthly.set_index("month_date").reindex(
    pd.date_range(monthly["month_date"].min(), monthly["month_date"].max(), freq="MS")
)
plot_monthly.index.name = "month_date"
chart = px.line(
    plot_monthly.reset_index(),
    x="month_date",
    y="mean_ndvi",
    markers=True,
    labels={"month_date": "Month", "mean_ndvi": "Mean NDVI"},
    color_discrete_sequence=["#9dcc80"],
)
chart.update_traces(connectgaps=False, hovertemplate="%{x|%b %Y}<br>Mean NDVI %{y:.4f}<extra></extra>")
chart.update_layout(
    height=350,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=10, color="#c5d3c8"),
    yaxis=dict(
        range=[-1, 1],
        title="District mean NDVI",
        gridcolor="#2a3c31",
        zerolinecolor="#405646",
        linecolor="#405646",
    ),
    xaxis=dict(
        title="Acquisition month",
        gridcolor="#2a3c31",
        zerolinecolor="#405646",
        linecolor="#405646",
    ),
    showlegend=False,
)

chart_col, monthly_col = st.columns([1.5, 1])
with chart_col:
    st.markdown("#### NDVI over time")
    st.caption("Blank months are unavailable; they are not interpolated or assigned values.")
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
with monthly_col:
    st.markdown("#### Monthly NDVI summary")
    display_monthly = monthly.copy()
    display_monthly["month"] = pd.to_datetime(display_monthly["month_date"]).dt.strftime("%b %Y")
    display_monthly["mean_ndvi"] = display_monthly["mean_ndvi"].map(lambda value: f"{value:.4f}")
    st.dataframe(
        display_monthly[["month", "mean_ndvi"]].rename(
            columns={"month": "Month", "mean_ndvi": "Mean NDVI"}
        ),
        hide_index=True,
        width="stretch",
    )

delta_frame = monthly.copy()
month_number = delta_frame["month_date"].dt.year * 12 + delta_frame["month_date"].dt.month
delta_frame["change"] = delta_frame["mean_ndvi"].diff().where(month_number.diff() == 1)
delta_frame = delta_frame.dropna(subset=["change"])
if not delta_frame.empty:
    st.markdown("#### Month-to-month seasonal changes")
    st.caption("Changes are shown only for consecutive months with observations.")
    seasonal = delta_frame[["month_date", "change"]].copy()
    seasonal["month"] = seasonal["month_date"].dt.strftime("%b %Y")
    seasonal["change"] = seasonal["change"].map(lambda value: f"{value:+.4f}")
    st.dataframe(
        seasonal[["month", "change"]].rename(
            columns={"month": "Month", "change": "NDVI change"}
        ),
        hide_index=True,
        width="stretch",
    )

with st.expander("Date-wise observations and data availability"):
    if datewise is None:
        st.warning(
            "The notebook reports 205 observations, but the per-scene date/NDVI rows were not "
            "saved as a project data file. This page therefore displays only the saved monthly "
            "averages. Configure `EARTHENGINE_PROJECT` to request current date-wise results."
        )
    else:
        st.dataframe(
            datewise[
                ["acquisition_date", "mean_ndvi", "scene_cloud_percent"]
            ].sort_values("acquisition_date"),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download date-wise observations",
            data=datewise[
                ["acquisition_date", "mean_ndvi", "scene_cloud_percent"]
            ]
            .to_csv(index=False, date_format="%Y-%m-%d")
            .encode("utf-8-sig"),
            file_name="mandya_ndvi_observations.csv",
            mime="text/csv",
        )

st.markdown("#### Processed NDVI raster statistics")
raster_stat_columns = st.columns(4)
raster_stat_columns[0].metric("Minimum NDVI", f"{ndvi_statistics['minimum']:.4f}")
raster_stat_columns[1].metric("Maximum NDVI", f"{ndvi_statistics['maximum']:.4f}")
raster_stat_columns[2].metric("Mean NDVI", f"{ndvi_statistics['mean']:.4f}")
raster_stat_columns[3].metric("Valid pixels", f"{ndvi_statistics['valid_pixels']:,}")
st.caption(
    "Statistics are recalculated from finite, unmasked pixels in Mandya_NDVI.tif. "
    "They describe the exported raster, not an additional live Earth Engine query."
)

with st.expander("Export NDVI to Google Drive and analyze the downloaded raster"):
    st.caption(
        "Exports are started only when requested. Earth Engine creates a 365-day mean NDVI "
        "GeoTIFF in the configured Drive folder."
    )
    if project:
        if st.button(
            "Start 365-day NDVI GeoTIFF export",
            key="mandya_start_drive_export",
        ):
            from src.gee_service import EarthEngineError, start_mandya_ndvi_drive_export

            try:
                task = start_mandya_ndvi_drive_export(
                    query_start,
                    query_end,
                    project=project,
                )
                st.session_state["mandya_ndvi_export_task"] = task
                st.session_state.pop("mandya_export_error", None)
                st.rerun()
            except (EarthEngineError, ValueError) as error:
                st.session_state["mandya_export_error"] = str(error)
                st.rerun()
    else:
        st.info("Configure `EARTHENGINE_PROJECT` and authenticate on the server to start Drive exports.")

    export_error = st.session_state.pop("mandya_export_error", None)
    if export_error:
        st.error(f"NDVI export could not be started or checked: {export_error}")

    export_task = st.session_state.get("mandya_ndvi_export_task")
    if export_task:
        st.write(
            f"**Task:** {export_task['description']} · **Status:** {export_task['state']} · "
            f"**Drive folder:** {export_task['drive_folder']}"
        )
        if project and st.button("Refresh export status", key="mandya_check_drive_export"):
            from src.gee_service import EarthEngineError, mandya_export_task_status

            try:
                status = mandya_export_task_status(export_task["task_id"], project=project)
                export_task.update(status)
                st.session_state["mandya_ndvi_export_task"] = export_task
                st.rerun()
            except (EarthEngineError, ValueError) as error:
                st.session_state["mandya_export_error"] = str(error)
                st.rerun()
        if export_task["state"] == "COMPLETED":
            st.success(
                "The GeoTIFF is ready in Google Drive. Download it below to analyze it in Python "
                "without replacing the existing project raster."
            )
        elif export_task["state"] == "FAILED":
            st.error(export_task.get("error_message") or "Earth Engine reported an export failure.")

    downloaded_raster = st.file_uploader(
        "Load a downloaded Earth Engine NDVI GeoTIFF into Python",
        type=("tif", "tiff"),
        help="The raster is analyzed in memory; the original file and project outputs are not changed.",
        key="mandya_downloaded_ndvi_raster",
    )
    if downloaded_raster is not None:
        try:
            uploaded_products = load_uploaded_ndvi_raster(downloaded_raster.getvalue())
        except (ValueError, OSError) as error:
            st.error(f"The uploaded NDVI GeoTIFF could not be analyzed: {error}")
        else:
            st.markdown(f"#### Uploaded raster · {downloaded_raster.name}")
            uploaded_stats = uploaded_products["statistics"]
            uploaded_metrics = st.columns(4)
            uploaded_metrics[0].metric("Minimum NDVI", f"{uploaded_stats['minimum']:.4f}")
            uploaded_metrics[1].metric("Maximum NDVI", f"{uploaded_stats['maximum']:.4f}")
            uploaded_metrics[2].metric("Mean NDVI", f"{uploaded_stats['mean']:.4f}")
            uploaded_metrics[3].metric("Valid pixels", f"{uploaded_stats['valid_pixels']:,}")
            uploaded_grid = uploaded_products["grid"]
            st.caption(
                f"Loaded with source georeferencing preserved: {uploaded_grid['crs_label']} · "
                f"{uploaded_grid['resolution'][0]:.9f}° × "
                f"{uploaded_grid['resolution'][1]:.9f}° · "
                f"{uploaded_grid['width']:,} × {uploaded_grid['height']:,} pixels."
            )
