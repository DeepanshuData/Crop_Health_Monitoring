"""Shared Streamlit page setup for the multi-page application."""

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
    save_uploaded_geojson,
)


def setup_page(title):
    st.set_page_config(page_title=title, page_icon="🌿", layout="wide")
    style_path = PROJECT_ROOT / "app" / "styles" / "style.css"
    if style_path.exists():
        st.markdown(
            f"<style>{style_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    district, mode = render_sidebar()
    try:
        if mode == "custom":
            upload = st.session_state["custom_boundary_upload"]
            feature = save_uploaded_geojson(upload)
            region_name = upload.name
        else:
            feature = district_feature(district)
            region_name = f"{district.title()}, Karnataka"
        activate_region(
            feature,
            district if mode == "district" else "custom",
            region_name,
        )
        initialize_earth_engine()
    except (ValueError, RuntimeError) as exc:
        st.error(str(exc))
        st.stop()
    st.title(title)
    st.caption(region_name)
    return district, feature, region_name
