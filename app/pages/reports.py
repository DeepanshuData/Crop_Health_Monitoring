from __future__ import annotations

import io
import zipfile

import streamlit as st

from app.common import load_scene, render_header
from src.crop_health_data import INDEX_NAMES, index_geotiff_bytes, statistics_frame
from src.report_generator import build_pdf_report, build_statistics_csv

scene = load_scene()
render_header(scene, "Crop health reports")

st.markdown('<div class="section-title">Export analysis products</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Download the validated raster outputs and a concise report for the '
    'verified Mysuru scene. Every statistic describes the source-scene pixels, not a farm boundary.</div>',
    unsafe_allow_html=True,
)

st.dataframe(statistics_frame(scene), hide_index=True, width="stretch")
st.markdown("#### Choose index raster")
index_name = st.selectbox("GeoTIFF product", INDEX_NAMES)
index_path = scene["project_root"] / "outputs" / "all_7_indices" / "geotiff" / f"{index_name}.tif"
index_data = (
    index_path.read_bytes()
    if index_path.is_file()
    else index_geotiff_bytes(scene, index_name)
)
columns = st.columns(3)
columns[0].download_button(
    f"Download {index_name} GeoTIFF",
    data=index_data,
    file_name=f"{index_name}.tif",
    mime="image/tiff",
)
columns[1].download_button(
    "Download index statistics CSV",
    data=build_statistics_csv(scene),
    file_name="index_statistics.csv",
    mime="text/csv",
)
columns[2].download_button(
    "Download project summary",
    data=(scene["project_root"] / "outputs" / "all_7_indices" / "project_summary.txt").read_bytes(),
    file_name="project_summary.txt",
    mime="text/plain",
)

pdf_bytes = build_pdf_report(scene)
st.download_button(
    "Generate and download PDF report",
    data=pdf_bytes,
    file_name="agrivision_mysuru_crop_health_report.pdf",
    mime="application/pdf",
    type="primary",
)
st.caption(
    "PDF includes source metadata, all eight index statistics, NDVI/NDRE/NDWI maps, "
    "masking details, and interpretation limitations."
)

with st.expander("Download a complete product bundle"):
    if st.button("Build ZIP bundle"):
        output_dir = scene["project_root"] / "outputs" / "all_7_indices"
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((output_dir / "geotiff").glob("*.tif")):
                archive.write(path, arcname=f"geotiff/{path.name}")
            archive.writestr(
                "geotiff/NDWI.tif",
                index_geotiff_bytes(scene, "NDWI"),
            )
            archive.write(output_dir / "sentinel2_all_7_indices.png", arcname="sentinel2_all_7_indices.png")
            archive.write(output_dir / "index_statistics.csv", arcname="index_statistics.csv")
            archive.write(output_dir / "project_summary.txt", arcname="project_summary.txt")
            archive.writestr("agrivision_mysuru_crop_health_report.pdf", pdf_bytes)
            archive.writestr("index_statistics_eight_indices.csv", build_statistics_csv(scene))
        st.download_button(
            "Download full analysis ZIP",
            data=bundle.getvalue(),
            file_name="agrivision_mysuru_analysis.zip",
            mime="application/zip",
            key="download_analysis_zip",
        )
