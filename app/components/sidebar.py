"""Shared Streamlit sidebar controls."""

import hashlib
import json
from pathlib import Path

import streamlit as st

from gee.boundaries import DISTRICTS


def render_sidebar():
    st.sidebar.markdown("### Study area")
    district = st.sidebar.selectbox(
        "District",
        DISTRICTS,
        format_func=lambda value: f"{value.title()}, Karnataka",
    )
    upload = st.sidebar.file_uploader(
        "Upload custom farm/district GeoJSON",
        type=["geojson", "json"],
        help="Polygon or MultiPolygon in EPSG:4326.",
    )
    if upload is not None:
        st.session_state["custom_boundary_upload"] = upload
        st.sidebar.caption("Custom boundary will be used instead of the district.")
        boundary_mode = "custom"
    else:
        st.session_state.pop("custom_boundary_upload", None)
        boundary_mode = "district"
    st.sidebar.divider()
    st.sidebar.caption("Earth Engine project")
    st.sidebar.code("agri-satellite-monitoring")
    return district, boundary_mode


def activate_region(feature, district, region_name):
    """Clear prior analysis state whenever the selected geometry changes."""
    region_key = hashlib.sha256(
        json.dumps(feature, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("active_region_key") != region_key:
        for key in (
            "analysis_summary",
            "crop_health_result",
            "crop_health_metadata",
            "timeseries_frame",
            "comparison_result",
            "stress_result",
            "stress_report",
            "stress_metadata",
        ):
            st.session_state.pop(key, None)
    st.session_state["active_region_key"] = region_key
    st.session_state["active_feature"] = feature
    st.session_state["active_region_name"] = region_name
    st.session_state["active_district"] = district
