"""Dashboard overview and selectable boundary map."""

import streamlit as st

from bootstrap import setup_page
from components.map_component import render_map
from components.metric_cards import metric_row
from src.boundary_manager import geometry_area_ha, feature_to_ee


district, feature, region_name = setup_page("Dashboard")
summary = st.session_state.get("analysis_summary", {})
metric_row([
    {"label": "Selected region", "value": region_name},
    {"label": "Study area", "value": f"{geometry_area_ha(feature):,.0f} ha"},
    {"label": "Latest acquisition", "value": summary.get("acquisition_date", "Not run")},
    {"label": "Mean NDVI", "value": summary.get("ndvi_mean", "—")},
])
render_map(feature)
