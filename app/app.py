from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.common import load_scene

st.set_page_config(
    page_title="AgriVision | Crop Health Intelligence",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <div class="brand-lockup">
      <div class="brand-leaf">✳</div>
      <div><strong>AgriVision</strong><small>GEOAI CROP HEALTH INTELLIGENCE</small></div>
    </div>
    <div class="brand-tagline">Satellite Intelligence for Smarter Agriculture</div>
    """,
    unsafe_allow_html=True,
)

try:
    scene = load_scene()
except (FileNotFoundError, ValueError, OSError) as error:
    st.error(f"The verified Mysuru scene could not be loaded: {error}")
    st.info("Check the source raster and seven validated GeoTIFFs, then restart the app.")
    st.stop()

valid_percent = 100 * scene["base_valid_pixels"] / scene["total_pixels"]
st.sidebar.markdown(
    f"""
    <div class="sidebar-scene">
      <span class="scene-live"></span>
      <div><b>Reference scene · Mysuru</b><small>06 Feb 2025 · 20 m</small></div>
    </div>
    <div class="sidebar-data">
      <span>EXISTING LOCAL REFERENCE</span>
      <b>{scene['dimensions'][0]} × {scene['dimensions'][1]} px</b>
      <small>{valid_percent:.1f}% valid reflectance pixels</small>
    </div>
    """,
    unsafe_allow_html=True,
)

pages = {
    "PLATFORM": [
        st.Page("pages/dashboard.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page("pages/explorer.py", title="Spectral Index Explorer", icon=":material/query_stats:"),
        st.Page("pages/field_analysis.py", title="Interactive Field Analysis", icon=":material/map:"),
    ],
    "MONITORING": [
        st.Page("pages/location.py", title="Location & Earth Engine", icon=":material/location_on:"),
        st.Page("pages/history.py", title="Historical Monitoring", icon=":material/timeline:"),
        st.Page("pages/satellite_crop_health.py", title="Satellite Crop Health Monitoring", icon=":material/satellite_alt:"),
        st.Page("pages/reports.py", title="Crop Health Reports", icon=":material/description:"),
    ],
    "PROJECT": [
        st.Page("pages/about.py", title="About the Project", icon=":material/info:"),
    ],
}
selected_page = st.navigation(pages, position="sidebar", expanded=True)
selected_page.run()
