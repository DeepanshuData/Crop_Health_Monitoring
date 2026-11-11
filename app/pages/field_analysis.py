from __future__ import annotations

import folium
import streamlit as st
from folium.plugins import Draw, Fullscreen
from streamlit_folium import st_folium

from app.common import load_scene, render_header
from src.crop_health_data import (
    INDEX_NAMES,
    composite_rgb,
    index_rgba,
    pixel_at_lonlat,
)

scene = load_scene()
render_header(scene, "Interactive field analysis")

st.markdown('<div class="section-title">Explore the source raster footprint</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Pan and zoom the map, toggle scene layers, draw a study area for visual reference, '
    'or click a location to inspect the nearest available 20 m pixel.</div>',
    unsafe_allow_html=True,
)

left, right = st.columns([1, 2])
with left:
    layer_choice = st.selectbox(
        "Map layer",
        ("True colour · B4/B3/B2", "False colour · B8/B4/B3", "Spectral index"),
    )
    index_choice = st.selectbox(
        "Index layer",
        INDEX_NAMES,
        disabled=layer_choice != "Spectral index",
        key="field_index",
    )
    st.markdown(
        '<div class="field-note"><strong>Map footprint</strong><br>'
        "The outline is the source raster extent, not a surveyed farm or district boundary. "
        "Drawn geometries are visual aids only; use the Earth Engine page to submit a GeoJSON "
        "boundary for regional analysis.</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Source CRS is retained from the raster. The geographic display bounds are "
        f"{scene['geographic_bounds'][0][0]:.4f}–{scene['geographic_bounds'][1][0]:.4f}° N."
    )

southwest, northeast = scene["geographic_bounds"]
center = [(southwest[0] + northeast[0]) / 2, (southwest[1] + northeast[1]) / 2]
field_map = folium.Map(
    location=center,
    zoom_start=12,
    tiles="OpenStreetMap",
    control_scale=True,
    prefer_canvas=True,
)
folium.raster_layers.ImageOverlay(
    image=composite_rgb(scene, ("B4", "B3", "B2")),
    bounds=scene["geographic_bounds"],
    name="True colour · B4/B3/B2 · 2025-02-06",
    opacity=0.93,
    interactive=True,
    cross_origin=False,
    zindex=1,
    show=layer_choice == "True colour · B4/B3/B2",
).add_to(field_map)
folium.raster_layers.ImageOverlay(
    image=composite_rgb(scene, ("B8", "B4", "B3")),
    bounds=scene["geographic_bounds"],
    name="False colour · B8/B4/B3 · 2025-02-06",
    opacity=0.9,
    interactive=True,
    cross_origin=False,
    zindex=2,
    show=layer_choice == "False colour · B8/B4/B3",
).add_to(field_map)
folium.raster_layers.ImageOverlay(
    image=index_rgba(scene, index_choice),
    bounds=scene["geographic_bounds"],
    name=f"{index_choice} · 20 m",
    opacity=0.85,
    interactive=True,
    cross_origin=False,
    zindex=3,
    show=layer_choice == "Spectral index",
).add_to(field_map)
folium.Rectangle(
    bounds=scene["geographic_bounds"],
    color="#285d3a",
    weight=2,
    fill=False,
    tooltip="Source raster footprint (not an administrative boundary)",
).add_to(field_map)
Draw(
    export=False,
    draw_options={
        "polyline": False,
        "polygon": True,
        "rectangle": True,
        "circle": False,
        "circlemarker": False,
        "marker": True,
    },
    edit_options={"edit": True, "remove": True},
).add_to(field_map)
Fullscreen(position="topright").add_to(field_map)
folium.LayerControl(collapsed=False).add_to(field_map)
field_map.fit_bounds(scene["geographic_bounds"])

with right:
    map_event = st_folium(
        field_map,
        height=490,
        use_container_width=True,
        returned_objects=["last_clicked", "last_active_drawing"],
        key=f"field-map-{layer_choice}-{index_choice}",
    )

if map_event and map_event.get("last_clicked"):
    click = map_event["last_clicked"]
    try:
        clicked = pixel_at_lonlat(
            scene,
            float(click["lng"]),
            float(click["lat"]),
            index_choice,
        )
    except (ValueError, KeyError) as error:
        st.error(f"Could not inspect this map location: {error}")
    else:
        if not clicked["inside"]:
            st.warning("The selected point is outside the verified Mysuru raster footprint.")
        elif not clicked["valid"]:
            st.info(
                f"Selected pixel at row {clicked['row']}, column {clicked['column']} is invalid "
                "or masked in this index."
            )
        else:
            st.success(
                f"{index_choice} = {clicked['value']:.4f} at row {clicked['row']}, "
                f"column {clicked['column']} · {clicked['easting']:.2f} m E, "
                f"{clicked['northing']:.2f} m N"
            )
            st.caption(
                "A point value describes one raster pixel and should not be treated as a field-level statistic."
            )

if map_event and map_event.get("last_active_drawing"):
    st.info(
        "Drawing captured for visual reference. Regional statistics are not calculated for drawn "
        "polygons; submit a GeoJSON boundary through Location & Earth Engine to request a "
        "supported regional summary."
    )
