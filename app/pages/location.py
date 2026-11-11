from __future__ import annotations

import json
import os
from datetime import date

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.common import load_scene, render_header
from src.gee_service import EarthEngineError, search_sentinel2

scene = load_scene()
render_header(scene, "Location & Earth Engine")

st.markdown('<div class="section-title">Choose a study area</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">The bundled local analysis covers only the verified Mysuru scene. '
    'For another location, supply its polygon and run a real Sentinel-2 query through Earth Engine.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="field-note"><strong>Offline dataset availability</strong><br>'
    "Mysuru, Karnataka · 6 February 2025 is the only six-band source scene in this workflow. "
    "Other districts and dates are not preloaded; selecting a name does not imply local imagery exists.</div>",
    unsafe_allow_html=True,
)

with st.form("earth_engine_search", clear_on_submit=False):
    state_choice = st.selectbox(
        "State / Union Territory",
        ("Karnataka", "Other state / Union Territory"),
    )
    if state_choice == "Other state / Union Territory":
        state_label = st.text_input("State / Union Territory name")
    else:
        state_label = state_choice
    area_label = st.text_input(
        "District or study-area label",
        value="Mysuru" if state_choice == "Karnataka" else "",
    )
    geojson_file = st.file_uploader(
        "Study-area boundary GeoJSON",
        type=("geojson", "json"),
        help="Upload a Polygon, MultiPolygon, Feature, or FeatureCollection. Coordinates must use longitude, latitude (WGS 84).",
        max_upload_size=2,
    )
    date_range = st.date_input(
        "Acquisition date range",
        value=(date(2025, 1, 1), date(2025, 2, 28)),
        max_value=date.today(),
    )
    cloud_limit = st.slider("Maximum scene cloud metadata (%)", 0, 100, 30)
    submitted = st.form_submit_button("Search Sentinel-2 imagery", type="primary")

if submitted:
    if geojson_file is None:
        st.session_state.pop("location_search", None)
        st.error("Upload a study-area GeoJSON before searching.")
    elif len(date_range) != 2:
        st.error("Select both a start and end date.")
    else:
        try:
            geojson_text = geojson_file.getvalue().decode("utf-8-sig")
            json.loads(geojson_text)
            with st.spinner("Querying Sentinel-2, applying the SCL cloud/shadow mask, and summarizing indices…"):
                result = search_sentinel2(
                    geojson_text,
                    date_range[0],
                    date_range[1],
                    cloud_limit,
                    project=os.environ.get("EARTHENGINE_PROJECT"),
                )
            st.session_state["location_search"] = result
            st.session_state["location_label"] = f"{area_label}, {state_label}".strip(", ")
        except UnicodeDecodeError:
            st.session_state.pop("location_search", None)
            st.error("The GeoJSON file must be UTF-8 encoded.")
        except (json.JSONDecodeError, ValueError, EarthEngineError) as error:
            st.session_state.pop("location_search", None)
            st.error(str(error))

result = st.session_state.get("location_search")
if result:
    label = st.session_state.get("location_label", "User-supplied study area")
    st.markdown(f"### Earth Engine result · {label}")
    stats = result["statistics"]
    st.caption(
        f'{result["scene_count"]} matching Sentinel-2 scenes · '
        f'{result["start_date"]} to {result["end_date"]} · '
        f'collection cloud metadata mean: '
        f'{result["cloud_metadata_mean_percent"]:.1f}%'
        if result["cloud_metadata_mean_percent"] is not None
        else f'{result["scene_count"]} matching Sentinel-2 scenes · '
        f'{result["start_date"]} to {result["end_date"]} · cloud metadata mean unavailable'
    )
    stat_frame = pd.DataFrame(
        [
            {
                "Index": name,
                "Mean": stats.get(f"{name}_mean"),
                "Minimum": stats.get(f"{name}_min"),
                "Maximum": stats.get(f"{name}_max"),
                "Std. deviation": stats.get(f"{name}_stdDev"),
            }
            for name in ("NDVI", "EVI", "GNDVI", "NDRE", "NDMI", "MSI", "SAVI", "NDWI")
        ]
    )
    map_col, table_col = st.columns([1.3, 1])
    index_name = map_col.selectbox(
        "Earth Engine index map",
        ("NDVI", "NDRE", "NDWI", "False-colour composite"),
    )
    tile_name = "false_color" if index_name == "False-colour composite" else index_name
    geometry = result["geometry"]
    if geometry["type"] == "FeatureCollection":
        feature_geometries = [feature["geometry"] for feature in geometry["features"]]
    elif geometry["type"] == "Feature":
        feature_geometries = [geometry["geometry"]]
    else:
        feature_geometries = [geometry]
    def collect_positions(value):
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (float, int))
            and isinstance(value[1], (float, int))
        ):
            return [value]
        found = []
        if isinstance(value, list):
            for child in value:
                found.extend(collect_positions(child))
        return found

    positions = []
    for item in feature_geometries:
        positions.extend(collect_positions(item["coordinates"]))
    if not positions:
        st.error("The submitted geometry has no usable coordinates to display.")
        st.stop()
    longitude = sum(position[0] for position in positions) / max(len(positions), 1)
    latitude = sum(position[1] for position in positions) / max(len(positions), 1)
    gee_map = folium.Map(location=[latitude, longitude], zoom_start=10, tiles="OpenStreetMap")
    folium.GeoJson(geometry, name="Submitted study-area boundary").add_to(gee_map)
    folium.TileLayer(
        tiles=result["tiles"][tile_name],
        attr="Google Earth Engine · COPERNICUS/S2_SR_HARMONIZED",
        name=f"{index_name} · masked median composite",
        overlay=True,
        control=True,
    ).add_to(gee_map)
    folium.LayerControl(collapsed=False).add_to(gee_map)
    with map_col:
        st_folium(gee_map, height=440, use_container_width=True, key=f"gee-map-{tile_name}")
    with table_col:
        st.dataframe(stat_frame, hide_index=True, width="stretch")
        st.download_button(
            "Download regional statistics CSV",
            data=stat_frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="earth_engine_regional_index_statistics.csv",
            mime="text/csv",
        )
        st.markdown("**Processing**")
        st.write(result["cloud_shadow_mask"])
        st.write(
            "Cloud metadata is the collection's scene-level `CLOUDY_PIXEL_PERCENTAGE`; it is not "
            "an AOI-specific cloud percentage."
        )
        st.write(
            "Earth Engine uses a masked median composite for this date range. Regional statistics "
            "are computed at 20 m and are not an offline verified product."
        )

st.markdown("#### Earth Engine setup")
st.markdown(
    "Install the requirements, authenticate the Earth Engine Python API in this environment, "
    "and set `EARTHENGINE_PROJECT` to a Google Cloud project enabled for Earth Engine. "
    "Authentication is never started by the app. Queries may require a network connection "
    "and Earth Engine access approval."
)
st.code(
    r".\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    "\n"
    r".\.venv\Scripts\earthengine authenticate"
    "\n"
    r"$env:EARTHENGINE_PROJECT = 'your-earth-engine-enabled-project'",
    language="powershell",
)
