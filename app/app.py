"""Crop Health Intelligence Platform Streamlit entry point."""

from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
for import_path in (str(APP_DIR), str(ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from components.sidebar import activate_region, render_sidebar
from gee.config import PROJECT_ROOT
from src.analysis_engine import initialize_earth_engine
from src.boundary_manager import (
    district_feature,
    geometry_area_ha,
    save_uploaded_geojson,
)

st.set_page_config(
    page_title="Crop Health Intelligence",
    page_icon="🌿",
    layout="wide",
)

style_path = PROJECT_ROOT / "app" / "styles" / "style.css"
if style_path.exists():
    st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)

district, boundary_mode = render_sidebar()

try:
    if boundary_mode == "custom":
        upload = st.session_state["custom_boundary_upload"]
        feature = save_uploaded_geojson(upload)
        region_name = upload.name
    else:
        feature = district_feature(district)
        region_name = f"{district.title()}, Karnataka"
    activate_region(
        feature,
        district if boundary_mode == "district" else "custom",
        region_name,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

try:
    initialize_earth_engine()
except RuntimeError as exc:
    st.warning(str(exc))

st.title("Crop Health Intelligence Platform")
st.caption("Satellite-Based Agricultural Monitoring and Geospatial Analytics")

from components.metric_cards import metric_row

summary = st.session_state.get("analysis_summary", {})
summary_cards = [
    {"label": "Selected district", "value": region_name},
    {"label": "Study area", "value": f"{geometry_area_ha(feature):,.0f} ha"},
    {"label": "Latest acquisition", "value": summary.get("acquisition_date", "Not run")},
    {"label": "Mean NDVI", "value": summary.get("ndvi_mean", "—")},
]
summary_cards.extend([
    {"label": "Mean NDRE", "value": summary.get("ndre_mean", "—")},
    {"label": "Mean NDWI", "value": summary.get("ndwi_mean", "—")},
    {"label": "Stressed area", "value": summary.get("stress_percentage", "—")},
])
metric_row(summary_cards)

st.info(
    "No live satellite values are shown until an analysis is run. "
    "Vegetation indices are screening indicators, not crop-disease diagnoses."
)
