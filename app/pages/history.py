from __future__ import annotations

import json
import os
from datetime import date

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from app.common import load_scene, render_header
from src.gee_service import EarthEngineError, sentinel2_time_series

scene = load_scene()
render_header(scene, "Historical monitoring")

st.markdown('<div class="section-title">Track real observations over time</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">A trustworthy time series requires multiple dated satellite observations '
    'over the same geometry. The local archive contains only one verified six-band date.</div>',
    unsafe_allow_html=True,
)

local_date = scene["acquisition_date"]
ndvi_stat = scene["statistics"]["NDVI"]
cols = st.columns(3)
cols[0].metric("Verified local scenes", "1")
cols[1].metric("Local acquisition", local_date)
cols[2].metric("Local mean NDVI", f'{ndvi_stat["Mean"]:.4f}')
st.info(
    "The separate `Mysuru_NDVI_2024.tif` file has no acquisition-date metadata and does not have "
    "the verified six-band stack. It is not included in this historical comparison."
)

with st.form("historical_search"):
    geojson_file = st.file_uploader(
        "Study-area GeoJSON",
        type=("geojson", "json"),
        key="history_geojson",
        max_upload_size=2,
    )
    date_range = st.date_input(
        "Time-series date range",
        value=(date(2024, 1, 1), date.today()),
        max_value=date.today(),
        key="history_dates",
    )
    cloud_limit = st.slider(
        "Maximum scene cloud metadata (%)",
        0,
        100,
        30,
        key="history_cloud_limit",
    )
    submitted = st.form_submit_button("Load Earth Engine time series", type="primary")

if submitted:
    if geojson_file is None:
        st.session_state.pop("history_result", None)
        st.error("Upload a Polygon or MultiPolygon GeoJSON to query real observations.")
    elif len(date_range) != 2:
        st.error("Select both a start and end date.")
    else:
        try:
            geojson_text = geojson_file.getvalue().decode("utf-8-sig")
            json.loads(geojson_text)
            with st.spinner("Querying real Sentinel-2 scenes and calculating regional means…"):
                result = sentinel2_time_series(
                    geojson_text,
                    date_range[0],
                    date_range[1],
                    cloud_limit,
                    project=os.environ.get("EARTHENGINE_PROJECT"),
                )
            st.session_state["history_result"] = result
        except UnicodeDecodeError:
            st.session_state.pop("history_result", None)
            st.error("The GeoJSON file must be UTF-8 encoded.")
        except (json.JSONDecodeError, ValueError, EarthEngineError) as error:
            st.session_state.pop("history_result", None)
            st.error(str(error))

result = st.session_state.get("history_result")
if result:
    observations = result["observations"]
    frame = pd.DataFrame(observations)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    count = result["scene_count"]
    st.markdown("### Earth Engine observation series")
    st.caption(
        f'{count} matching scenes in the requested date range · '
        f'{len(frame)} dated observations displayed, with a maximum of 120 · '
        f'SCL cloud/shadow mask applied.'
    )
    if len(frame) < 2:
        st.warning(
            "Only one valid dated observation is available; a temporal trend or before/after "
            "change cannot be calculated."
        )
    else:
        metric_cols = st.columns(3)
        for column, name in zip(metric_cols, ("NDVI", "NDRE", "NDWI")):
            values = frame[name].dropna()
            if len(values) >= 2:
                previous = float(values.iloc[0])
                latest = float(values.iloc[-1])
                delta = latest - previous
                relative = delta / abs(previous) * 100 if previous != 0 else None
                column.metric(
                    f"Latest mean {name}",
                    f"{latest:.4f}",
                    f"{delta:+.4f} from first observation"
                    + (f" · {relative:+.1f}%" if relative is not None else ""),
                )
            else:
                column.metric(f"Latest mean {name}", "No data")

    st.markdown("#### Regional index mean time series")
    chart = px.line(
        frame,
        x="date",
        y=["NDVI", "NDRE", "NDWI"],
        markers=True,
        labels={"date": "Acquisition date", "value": "Regional mean index", "variable": "Index"},
        color_discrete_sequence=["#3c7d52", "#d49742", "#4d8990"],
    )
    chart.update_layout(
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10, color="#647168"),
        legend_title_text="",
    )
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})

    selected_index = st.selectbox("Compare temporal maps", ("NDVI", "NDRE", "NDWI"))
    map_period = st.radio(
        "Map period",
        ("First observation", "Latest observation", "Latest minus first"),
        horizontal=True,
    )
    period_key = {
        "First observation": "first",
        "Latest observation": "latest",
        "Latest minus first": "difference",
    }[map_period]
    if period_key == "difference" and len(frame) < 2:
        st.info("A difference map requires at least two observations.")
    else:
        geojson = result["geometry"]
        if geojson["type"] == "FeatureCollection":
            geometries = [feature["geometry"] for feature in geojson["features"]]
        elif geojson["type"] == "Feature":
            geometries = [geojson["geometry"]]
        else:
            geometries = [geojson]

        def collect_positions(value):
            if (
                isinstance(value, list)
                and len(value) >= 2
                and isinstance(value[0], (float, int))
                and isinstance(value[1], (float, int))
            ):
                return [value]
            positions = []
            if isinstance(value, list):
                for child in value:
                    positions.extend(collect_positions(child))
            return positions

        positions = [
            position
            for geometry in geometries
            for position in collect_positions(geometry["coordinates"])
        ]
        if positions:
            center = [
                sum(position[1] for position in positions) / len(positions),
                sum(position[0] for position in positions) / len(positions),
            ]
            historical_map = folium.Map(location=center, zoom_start=10, tiles="OpenStreetMap")
            historical_map.add_child(folium.GeoJson(geojson, name="Submitted study-area boundary"))
            historical_map.add_child(
                folium.TileLayer(
                    tiles=result["tiles"][selected_index][period_key],
                    attr="Google Earth Engine · COPERNICUS/S2_SR_HARMONIZED",
                    name=f"{selected_index} · {map_period}",
                    overlay=True,
                    control=True,
                )
            )
            folium.LayerControl(collapsed=False).add_to(historical_map)
            st_folium(
                historical_map,
                height=470,
                use_container_width=True,
                key=f"history-{selected_index}-{period_key}",
            )
            if period_key == "difference":
                st.caption(
                    "Difference is latest minus first for the first/latest displayed observation dates. "
                    "Positive and negative values indicate spectral-index change, not a crop-health diagnosis."
                )
            else:
                st.caption(
                    f"Map date: {result['first_date'] if period_key == 'first' else result['latest_date']}."
                )

    st.markdown("#### Observation table")
    st.dataframe(frame, hide_index=True, width="stretch")
    st.download_button(
        "Download time-series CSV",
        data=frame.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig"),
        file_name="sentinel2_index_time_series.csv",
        mime="text/csv",
    )
