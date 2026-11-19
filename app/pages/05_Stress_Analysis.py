"""Configurable NDVI crop-stress screening page."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from bootstrap import setup_page
from components.export_controls import render_geotiff_export
from components.map_component import render_map
from components.metric_cards import metric_row
from src.analysis_engine import fetch_analysis_image
from src.boundary_manager import feature_to_ee
from src.export_manager import save_csv
from src.stress_engine import classify_stress, stress_report


district, feature, region_name = setup_page("Stress Analysis")
geometry = feature_to_ee(feature)
today = date.today()
start = st.date_input("Analysis start", today - timedelta(days=30))
end = st.date_input("Analysis end", today)
threshold = st.slider(
    "NDVI stress threshold",
    min_value=-1.0,
    max_value=1.0,
    value=0.30,
    step=0.01,
)
if st.button("Run stress analysis", type="primary"):
    if start >= end:
        st.error("End date must be later than start date.")
        st.stop()
    with st.spinner("Calculating masked NDVI stress classes..."):
        try:
            image, metadata = fetch_analysis_image(geometry, start, end)
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            result = classify_stress(ndvi, threshold, geometry)
            report = stress_report(result["statistics"], st.session_state["active_district"])
            st.session_state["stress_result"] = result
            st.session_state["stress_report"] = report
            st.session_state["stress_metadata"] = metadata
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            st.stop()

result = st.session_state.get("stress_result")
if result is None:
    st.info("Run the analysis to calculate stressed and non-stressed areas.")
else:
    stats = result["statistics"]
    metric_row([
        {"label": "Acquisition", "value": st.session_state["stress_metadata"]["acquisition_date"]},
        {"label": "Valid pixels", "value": f"{stats['valid_pixels']:,}"},
        {"label": "Stressed pixels", "value": f"{stats['stressed_pixels']:,}"},
        {"label": "Stressed area", "value": f"{stats['stressed_area_ha']:,.1f} ha"},
        {"label": "Stress percentage", "value": f"{stats['stressed_percentage']:.2f}%"},
    ])
    render_map(feature, [(result["classification"], {
        "min": 0,
        "max": 1,
        "palette": ["1A9850", "D73027"],
    }, "Crop stress")])
    report = st.session_state["stress_report"]
    st.dataframe(report, use_container_width=True)
    csv_path = save_csv(
        report,
        st.session_state["active_district"],
        "stress_report",
    )
    st.download_button(
        "Download stress CSV",
        data=csv_path.read_bytes(),
        file_name=csv_path.name,
        mime="text/csv",
    )
    render_geotiff_export(
        result["classification"],
        geometry,
        st.session_state["active_district"],
        f"stress_{threshold:.2f}",
        "Export stress GeoTIFF to Google Drive",
        nodata=255,
    )
    st.caption(
        "This is a configurable NDVI screening rule, not a definitive disease diagnosis."
    )
