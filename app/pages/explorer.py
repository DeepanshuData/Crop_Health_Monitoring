from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.common import load_scene, render_header
from src.crop_health_data import (
    BAND_DETAILS,
    INDEX_DETAILS,
    INDEX_NAMES,
    composite_rgb,
    index_geotiff_bytes,
    index_rgba,
    statistics_frame,
)

scene = load_scene()
render_header(scene, "Spectral index explorer")

st.markdown('<div class="section-title">Explore spectral response</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Select an index to inspect its map, formula, input bands, and scene statistics. '
    'Color stretches change display only; scientific values remain un-clipped.</div>',
    unsafe_allow_html=True,
)

index_name = st.selectbox("Spectral index", INDEX_NAMES, key="explorer_index")
details = INDEX_DETAILS[index_name]
stat = scene["statistics"][index_name]

st.markdown(
    f'<div class="section-title">{details["full_name"]}</div>'
    f'<div class="index-formula">{details["formula"]}</div>',
    unsafe_allow_html=True,
)
st.caption(f'Input bands: {details["bands"]} · Purpose: {details["purpose"]}')

metric_columns = st.columns(6)
for column, label, key in zip(
    metric_columns,
    ("Minimum", "Maximum", "Mean", "Median", "Std. deviation", "Valid pixels"),
    ("Minimum", "Maximum", "Mean", "Median", "Standard Deviation", "Valid Pixel Count"),
):
    value = stat[key]
    column.metric(label, f"{value:,.4f}" if isinstance(value, float) else f"{value:,}")

map_column, meaning_column = st.columns([1.5, 1])
with map_column:
    st.image(
        index_rgba(scene, index_name),
        caption=f"{index_name} · gray pixels indicate invalid or masked values",
        width="stretch",
    )
with meaning_column:
    st.markdown("#### Interpretation")
    st.write(details["interpretation"])
    st.info("Interpret the index as a spectral indicator, not as a standalone crop diagnosis.")
    st.markdown("#### Masking and units")
    st.write("Input reflectance is stored as DN / 10,000. The original six-band positive, finite mask is retained.")
    if index_name == "EVI":
        st.write("EVI denominators with absolute value below 0.1 are masked for stability.")
    if index_name == "NDWI":
        st.write("NDWI uses the McFeeters Green–NIR formula. It is not NDMI (NIR–SWIR1).")

download_col, all_csv_col = st.columns(2)
download_col.download_button(
    f"Download {index_name} GeoTIFF",
    data=index_geotiff_bytes(scene, index_name),
    file_name=f"{index_name}.tif",
    mime="image/tiff",
)
all_csv_col.download_button(
    "Download eight-index statistics CSV",
    data=statistics_frame(scene).to_csv(index=False, float_format="%.8f").encode("utf-8-sig"),
    file_name="agrivision_index_statistics.csv",
    mime="text/csv",
)

histogram = go.Figure(
    go.Histogram(
        x=scene["indices"][index_name],
        nbinsx=60,
        marker_color="#4d875a",
        marker_line_width=0,
        hovertemplate="Index value %{x:.4f}<br>Pixels %{y}<extra></extra>",
    )
)
histogram.update_layout(
    title=f"{index_name} valid-pixel distribution",
    height=300,
    xaxis_title=f"{index_name} value",
    yaxis_title="Pixel count",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=10, color="#647168"),
    showlegend=False,
    margin=dict(l=10, r=10, t=45, b=10),
)
st.plotly_chart(histogram, width="stretch", config={"displayModeBar": False})

with st.expander("Satellite band explorer and composites"):
    band_names = tuple(BAND_DETAILS)
    selected_band = st.selectbox("Visualize source band", band_names, key="source_band")
    band_label, band_role = BAND_DETAILS[selected_band]
    st.write(f"**{selected_band} · {band_label}.** {band_role}")
    st.image(
        composite_rgb(scene, (selected_band, selected_band, selected_band)),
        caption=f"{selected_band} grayscale-style display, 2nd–98th percentile stretch; masked pixels are gray.",
        width="stretch",
    )
    composite_kind = st.radio(
        "Composite visualization",
        ("True colour · B4 / B3 / B2", "False colour · B8 / B4 / B3"),
        horizontal=True,
    )
    composite_bands = (
        ("B4", "B3", "B2")
        if composite_kind.startswith("True")
        else ("B8", "B4", "B3")
    )
    st.image(
        composite_rgb(scene, composite_bands),
        caption=f"{composite_kind}. False colour maps NIR to red and emphasizes vegetation response; both are display-stretched composites.",
        width="stretch",
    )
    st.caption("Band reflectance and the original source imagery are not modified by these display stretches.")
