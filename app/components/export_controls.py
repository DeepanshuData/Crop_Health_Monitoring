"""Streamlit controls for asynchronous Earth Engine GeoTIFF exports."""

import streamlit as st

from src.export_manager import geotiff_export_status, start_geotiff_export


def render_geotiff_export(
    image,
    geometry,
    district: str,
    name: str,
    label: str,
    nodata=-9999,
):
    task_key = f"geotiff_export:{district.lower()}:{name}"
    button_key = f"start_{task_key}"
    if st.button(label, key=button_key):
        with st.spinner("Submitting GeoTIFF export to Google Drive..."):
            task_id = start_geotiff_export(image, geometry, district, name, nodata)
        st.session_state[task_key] = task_id

    task_id = st.session_state.get(task_key)
    if not task_id:
        return

    status = geotiff_export_status(task_id)
    state = status.get("state", "UNKNOWN")
    if state == "COMPLETED":
        st.success(
            f"GeoTIFF export completed. Find {district.lower()}_{name}.tif "
            "in the crop_health_monitoring folder in Google Drive."
        )
    elif state in {"FAILED", "CANCELLED"}:
        details = status.get("error_message", "No details provided.")
        st.error(f"GeoTIFF export {state.lower()}: {details}")
    else:
        st.info(
            f"GeoTIFF export is {state.lower()} (task {task_id}). "
            "Check the Earth Engine Tasks page for progress."
        )
