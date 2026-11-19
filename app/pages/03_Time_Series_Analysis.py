"""NDVI/NDRE time-series page."""

from datetime import date, timedelta
import json

import streamlit as st

from bootstrap import setup_page
from components.chart_components import line_chart
from src.boundary_manager import feature_to_ee
from src.export_manager import save_csv
from src.timeseries_engine import build_timeseries


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_timeseries(feature_json, region_name, start_date, end_date, cloud, count):
    feature = json.loads(feature_json)
    geometry = feature_to_ee(feature)
    return build_timeseries(
        geometry,
        region_name,
        start_date,
        end_date,
        max_cloud_percentage=cloud,
        max_dates=count,
    )


district, feature, region_name = setup_page("Time Series Analysis")
today = date.today()
start = st.date_input("Start date", today - timedelta(days=365))
end = st.date_input("End date", today)
index_name = st.radio("Index", ["NDVI", "NDRE"], index=0, horizontal=True)
cloud = st.slider("Maximum scene cloud (%)", 0, 100, 80)
observation_count = st.selectbox(
    "Observations to sample across the date range",
    [12, 24],
    help="Spaced acquisition dates keep Earth Engine requests bounded.",
)

if st.button("Generate 12-month time series", type="primary"):
    if end - start < timedelta(days=300):
        st.warning("A 12-month series is recommended for trend interpretation.")
    if start >= end:
        st.error("End date must be later than start date.")
        st.stop()
    with st.spinner("Aggregating actual acquisition-date observations..."):
        try:
            frame = _cached_timeseries(
                json.dumps(feature, sort_keys=True),
                region_name,
                start,
                end,
                cloud,
                observation_count,
            )
            st.session_state["timeseries_frame"] = frame
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            st.stop()

frame = st.session_state.get("timeseries_frame")
if frame is not None:
    column = "mean_ndvi" if index_name == "NDVI" else "mean_ndre"
    line_chart(frame, "acquisition_date", column, f"{index_name} time series")
    st.dataframe(frame, use_container_width=True)
    csv_path = save_csv(
        frame,
        st.session_state["active_district"],
        f"{index_name.lower()}_timeseries",
    )
    st.download_button(
        "Download time-series CSV",
        data=csv_path.read_bytes(),
        file_name=csv_path.name,
        mime="text/csv",
    )
