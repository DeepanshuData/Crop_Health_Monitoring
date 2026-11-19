"""NDVI comparison between two user-selected dates."""

from datetime import date, timedelta

import streamlit as st

from bootstrap import setup_page
from components.export_controls import render_geotiff_export
from components.map_component import render_map
from components.metric_cards import metric_row
from src.boundary_manager import feature_to_ee
from src.comparison_engine import compare_dates


district, feature, region_name = setup_page("NDVI Comparison")
geometry = feature_to_ee(feature)
today = date.today()
first = st.date_input("First date", today - timedelta(days=120))
second = st.date_input("Second date", today)

if st.button("Compare NDVI dates", type="primary"):
    with st.spinner("Selecting suitable acquisitions and calculating common valid pixels..."):
        try:
            result = compare_dates(geometry, first, second)
            st.session_state["comparison_result"] = result
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            st.stop()

result = st.session_state.get("comparison_result")
if result is None:
    st.info("Changes are calculated only for pixels valid on both selected dates.")
else:
    metric_row([
        {"label": "First acquisition", "value": result["first_metadata"]["acquisition_date"]},
        {"label": "First mean NDVI", "value": round(result["first_mean"], 3)},
        {"label": "Second acquisition", "value": result["second_metadata"]["acquisition_date"]},
        {"label": "Second mean NDVI", "value": round(result["second_mean"], 3)},
        {"label": "Mean change", "value": round(result["mean_change"], 3)},
        {"label": "Common pixels", "value": f"{result['common_valid_pixels']:,}"},
        {"label": "Common area", "value": f"{result['common_valid_area_ha']:,.1f} ha"},
    ])
    ndvi_params = {"min": -1, "max": 1, "palette": ["B54545", "F7C96A", "8BC34A", "1B7F3B"]}
    layer = st.radio(
        "Map",
        ["First NDVI", "Second NDVI", "NDVI change"],
        horizontal=True,
    )
    if layer == "First NDVI":
        layers = [(result["first_ndvi"], ndvi_params, "First NDVI")]
    elif layer == "Second NDVI":
        layers = [(result["second_ndvi"], ndvi_params, "Second NDVI")]
    else:
        layers = [(result["change"], {
            "min": -1, "max": 1,
            "palette": ["D73027", "FC8D59", "FEE08B", "FFFFBF", "91CF60", "1A9850"],
        }, "NDVI change")]
    render_map(feature, layers)
    st.caption(
        "NDVI increases are not automatically crop-health improvements: crop stage, "
        "soil exposure, moisture and management can influence change."
    )
    render_geotiff_export(
        result["change"],
        geometry,
        st.session_state["active_district"],
        "ndvi_change",
        "Export common-pixel NDVI change GeoTIFF to Google Drive",
    )
