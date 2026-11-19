"""Live NDVI, NDRE and NDWI analysis page."""

from datetime import date, timedelta

import streamlit as st

from bootstrap import setup_page
from components.export_controls import render_geotiff_export
from components.map_component import render_map
from components.metric_cards import metric_row
from src.analysis_engine import calculate_analysis, fetch_analysis_image
from src.boundary_manager import feature_to_ee


district, feature, region_name = setup_page("Crop Health Analysis")
geometry = feature_to_ee(feature)
today = date.today()
col1, col2, col3 = st.columns(3)
with col1:
    start = st.date_input("Start date", today - timedelta(days=30))
with col2:
    end = st.date_input("End date", today)
with col3:
    cloud = st.slider("Maximum scene cloud (%)", 0, 100, 80)

if st.button("Run Sentinel-2 analysis", type="primary"):
    if start >= end:
        st.error("End date must be later than start date.")
        st.stop()
    with st.spinner("Fetching and processing Sentinel-2 imagery..."):
        try:
            image, metadata = fetch_analysis_image(geometry, start, end, cloud)
            result = calculate_analysis(geometry, image)
            stats = result["statistics"]
            st.session_state["crop_health_result"] = result
            st.session_state["crop_health_metadata"] = metadata
            st.session_state["analysis_summary"] = {
                "acquisition_date": metadata["acquisition_date"],
                "ndvi_mean": round(stats.get("NDVI_mean", 0), 3),
                "ndre_mean": round(stats.get("NDRE_mean", 0), 3),
                "ndwi_mean": round(stats.get("NDWI_mean", 0), 3),
            }
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            st.stop()

result = st.session_state.get("crop_health_result")
if result is None:
    st.info("Choose a date range and run the analysis to generate satellite-derived maps.")
else:
    stats = result["statistics"]
    metric_row([
        {"label": "Acquisition", "value": st.session_state["crop_health_metadata"]["acquisition_date"]},
        {"label": "Mean NDVI", "value": round(stats.get("NDVI_mean", 0), 3)},
        {"label": "Mean NDRE", "value": round(stats.get("NDRE_mean", 0), 3)},
        {"label": "Mean NDWI", "value": round(stats.get("NDWI_mean", 0), 3)},
    ])
    layer = st.radio(
        "Map layer",
        ["Satellite", "NDVI", "NDRE", "NDWI"],
        index=1,
        horizontal=True,
    )
    if layer == "Satellite":
        ee_layers = [(result["satellite"], {
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
        }, "Sentinel-2 true color")]
    elif layer == "NDVI":
        ee_layers = [(result["ndvi"], {
            "min": -1, "max": 1, "palette": ["B54545", "F7C96A", "8BC34A", "1B7F3B"]
        }, "NDVI")]
    elif layer == "NDRE":
        ee_layers = [(result["ndre"], {
            "min": -1, "max": 1, "palette": ["B54545", "F7C96A", "8BC34A", "1B7F3B"]
        }, "NDRE")]
    else:
        ee_layers = [(result["ndwi"], {
            "min": -1, "max": 1, "palette": ["D27D46", "F5E6A1", "69B4D0", "1466A2"]
        }, "NDWI")]
    render_map(feature, ee_layers)
    export_name = st.radio(
        "GeoTIFF download",
        ["NDVI", "NDRE", "NDWI"],
        index=0,
        horizontal=True,
    )
    render_geotiff_export(
        result[export_name.lower()],
        geometry,
        st.session_state["active_district"],
        export_name.lower(),
        "Export actual GeoTIFF to Google Drive",
    )
