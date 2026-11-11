from __future__ import annotations

import streamlit as st

from app.common import load_scene, render_header
from src.crop_health_data import BAND_DETAILS, INDEX_DETAILS

scene = load_scene()
render_header(scene, "About AgriVision")

st.markdown('<div class="section-title">Project methodology</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">An explainable, reproducible Sentinel-2 surface-reflectance '
    'workflow. Local maps reuse the verified source raster and its derived index products.</div>',
    unsafe_allow_html=True,
)

st.markdown("### Verified local scene")
st.write(
    "**Area:** Mysuru, Karnataka, India  \n"
    "**Satellite and collection:** Sentinel-2 · `COPERNICUS/S2_SR_HARMONIZED`  \n"
    "**Acquisition:** 6 February 2025  \n"
    "**CRS designation:** EPSG:32643; exported products inherit the source CRS definition  \n"
    "**Resolution:** 20 m  \n"
    f"**Grid:** {scene['dimensions'][0]} columns × {scene['dimensions'][1]} rows  \n"
    "**Cloud coverage:** Not recorded in the local source raster."
)

st.markdown("### Source bands")
st.dataframe(
    [
        {"Band": band, "Name": BAND_DETAILS[band][0], "Agricultural relevance": BAND_DETAILS[band][1]}
        for band in BAND_DETAILS
    ],
    hide_index=True,
    width="stretch",
)

st.markdown("### Spectral indices")
for index_name, details in INDEX_DETAILS.items():
    with st.expander(f"{index_name} · {details['full_name']}"):
        st.markdown(f'<div class="index-formula">{details["formula"]}</div>', unsafe_allow_html=True)
        st.write(f"**Bands:** {details['bands']}")
        st.write(details["purpose"])
        st.write(details["interpretation"])

st.markdown("### Reflectance and pixel quality")
st.write(
    "The six input bands are scaled surface-reflectance values stored as integer DN and converted "
    "by dividing by 10,000. A source pixel is considered valid only when all six band values are "
    "finite and positive, preserving the original notebook's mask. The EVI denominator is "
    "additionally masked when its absolute value is below 0.1. Scientific values are not clipped."
)
st.write(
    "The `NDWI` shown here is McFeeters Green–NIR: `(B3 - B8) / (B3 + B8)`. It is not NDMI, "
    "which uses NIR and SWIR1. Invalid pixels are displayed gray and exported as NoData in the "
    "derived rasters."
)

st.markdown("### Boundaries, cloud handling, and interpretation")
st.write(
    "The local raster extent is not an administrative district boundary or surveyed field "
    "polygon. No local scene-level cloud mask or cloud percentage is available. The optional "
    "Earth Engine workflow accepts user-provided GeoJSON, filters Sentinel-2 scenes by "
    "`CLOUDY_PIXEL_PERCENTAGE`, and masks SCL classes 0, 1, 3, 8, 9, 10, and 11."
)
st.warning(
    "Vegetation and moisture indices are spectral indicators, not verified crop-health diagnoses. "
    "They cannot determine crop type, yield, irrigation need, or disease by themselves. "
    "Ground observations and agronomic context are needed."
)

st.markdown("### Reproducibility and external services")
st.write(
    "The local Streamlit app reads the existing validated GeoTIFFs and statistics. It does not "
    "rewrite the source imagery. The location search and historical series require network access, "
    "Earth Engine authentication, and a Cloud project authorized for Earth Engine. Maps may "
    "request external OpenStreetMap tiles."
)
st.code(
    r".\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    "\n"
    r".\.venv\Scripts\streamlit.exe run app\app.py",
    language="powershell",
)
