from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app.common import load_scene, render_header
from src.crop_health_data import composite_rgb, index_rgba
from src.report_generator import build_pdf_report, build_statistics_csv

scene = load_scene()
render_header(scene, "Crop health dashboard")

st.markdown('<div class="section-title">Mysuru scene overview</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">A scene-level view of vegetation reflectance and moisture indicators. '
    'Raster footprint is not an administrative or surveyed field boundary.</div>',
    unsafe_allow_html=True,
)

width, height = scene["dimensions"]
resolution_x, resolution_y = scene["resolution"]
pixel_area_ha = abs(resolution_x * resolution_y) / 10_000
footprint_km2 = scene["total_pixels"] * pixel_area_ha / 100
valid_area_km2 = scene["base_valid_pixels"] * pixel_area_ha / 100
mean_ndvi = scene["statistics"]["NDVI"]["Mean"]

kpis = st.columns(6)
kpis[0].metric("Study area", "Mysuru", "Karnataka, India")
kpis[1].metric("Acquisition", "06 Feb 2025", "Sentinel-2 L2A")
kpis[2].metric("Pixel size", "20 m", "Source grid")
kpis[3].metric("Raster footprint", f"{footprint_km2:,.1f} km²", "Grid area estimate")
kpis[4].metric("Valid reflectance", f"{valid_area_km2:,.1f} km²", f'{scene["base_valid_pixels"]:,} pixels')
kpis[5].metric("Mean NDVI", f"{mean_ndvi:.3f}", "Scene statistic")

image_col, summary_col = st.columns([1.55, 1])
with image_col:
    st.markdown("#### Satellite scene preview")
    st.image(
        composite_rgb(scene, ("B4", "B3", "B2")),
        caption="True-colour display composite · Red B4 / Green B3 / Blue B2 · 2nd–98th percentile display stretch",
        width="stretch",
    )
with summary_col:
    st.markdown("#### Scene facts")
    st.write(f"**Collection:** `COPERNICUS/S2_SR_HARMONIZED`")
    st.write(f"**Grid:** {width} columns × {height} rows")
    st.write(f"**CRS designation:** EPSG:32643 (source CRS retained)")
    st.write("**Cloud coverage:** Not recorded in the source raster metadata.")
    st.write("**Cloud mask:** No QA/cloud mask is applied to this local six-band stack.")
    st.markdown(
        '<div class="field-note"><strong>Analytical context</strong><br>'
        f'Mean NDVI is {mean_ndvi:.3f} for the valid pixels in this raster. NDVI describes '
        'relative red/NIR reflectance response; this value alone does not establish crop type, '
        'yield, or agronomic condition.</div>',
        unsafe_allow_html=True,
    )

st.markdown("#### Index snapshots")
map_columns = st.columns(3)
for column, name, note in zip(
    map_columns,
    ("NDVI", "NDRE", "NDWI"),
    ("Canopy greenness", "Red-edge response", "McFeeters water contrast"),
):
    with column:
        st.markdown(f"**{name} · {note}**")
        st.image(index_rgba(scene, name), caption="Gray = invalid or masked", width="stretch")
        st.caption(
            f'Mean {scene["statistics"][name]["Mean"]:.4f} · '
            f'{scene["statistics"][name]["Valid Pixel Count"]:,} valid pixels'
        )

chart_col, comparison_col = st.columns(2)
ndvi_values = scene["indices"]["NDVI"]
valid_ndvi = ndvi_values[np.isfinite(ndvi_values)]
bins = [-np.inf, 0, 0.2, 0.4, 0.6, np.inf]
labels = ["< 0", "0–0.2", "0.2–0.4", "0.4–0.6", "≥ 0.6"]
counts, _ = np.histogram(valid_ndvi, bins=bins)
shares = 100 * counts / valid_ndvi.size

with chart_col:
    st.markdown("#### NDVI value distribution")
    st.caption("Share of valid pixels in numeric NDVI intervals; bins are not crop-condition classes.")
    distribution = go.Figure(
        go.Bar(
            x=labels,
            y=shares,
            marker_color=["#b68b65", "#bb986d", "#8eac71", "#65956b", "#39734f"],
            hovertemplate="NDVI range %{x}<br>%{y:.1f}% of valid pixels<extra></extra>",
        )
    )
    distribution.update_layout(
        height=275,
        margin=dict(l=8, r=8, t=10, b=8),
        yaxis_title="Valid pixels (%)",
        xaxis_title="NDVI numeric interval",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10, color="#647168"),
        showlegend=False,
    )
    st.plotly_chart(distribution, width="stretch", config={"displayModeBar": False})

with comparison_col:
    st.markdown("#### Mean index comparison")
    st.caption("Indices have different scales and meanings; compare cautiously.")
    names = ("NDVI", "EVI", "GNDVI", "NDRE", "NDMI", "MSI", "SAVI", "NDWI")
    means = [scene["statistics"][name]["Mean"] for name in names]
    comparison = go.Figure(
        go.Bar(
            x=names,
            y=means,
            marker_color=["#3c7d52" if name != "NDWI" else "#548c85" for name in names],
            hovertemplate="%{x}<br>Mean %{y:.4f}<extra></extra>",
        )
    )
    comparison.update_layout(
        height=275,
        margin=dict(l=8, r=8, t=10, b=8),
        yaxis_title="Mean index value",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10, color="#647168"),
        showlegend=False,
    )
    st.plotly_chart(comparison, width="stretch", config={"displayModeBar": False})

st.markdown("#### Exports")
download_col, report_col, csv_col = st.columns(3)
download_col.download_button(
    "Download combined seven-index map",
    data=(scene["project_root"] / "outputs/all_7_indices/sentinel2_all_7_indices.png").read_bytes(),
    file_name="sentinel2_all_7_indices.png",
    mime="image/png",
)
report_col.download_button(
    "Generate PDF scene report",
    data=build_pdf_report(scene),
    file_name="agrivision_mysuru_crop_health_report.pdf",
    mime="application/pdf",
)
csv_col.download_button(
    "Download eight-index CSV",
    data=build_statistics_csv(scene),
    file_name="agrivision_mysuru_index_statistics.csv",
    mime="text/csv",
)
