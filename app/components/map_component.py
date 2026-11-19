"""Folium and Earth Engine map helpers."""

from __future__ import annotations

import folium
from streamlit_folium import st_folium


def geojson_bounds(feature):
    import shapely.geometry

    bounds = shapely.geometry.shape(feature["geometry"]).bounds
    return [(bounds[1], bounds[0]), (bounds[3], bounds[2])]


def ee_tile_layer(image, vis_params, name):
    map_id = image.getMapId(vis_params)
    return folium.TileLayer(
        tiles=map_id["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    )


def boundary_tile(feature):
    bounds = geojson_bounds(feature)
    center_lat = (bounds[0][0] + bounds[1][0]) / 2
    center_lon = (bounds[0][1] + bounds[1][1]) / 2
    return folium.Map(location=[center_lat, center_lon], zoom_start=10)


def render_map(feature, earth_engine_layers=None, height=520):
    """Render a boundary plus optional Earth Engine tile layers."""
    map_object = boundary_tile(feature)
    folium.GeoJson(
        feature,
        name="Selected boundary",
        style_function=lambda _: {
            "fillColor": "#59D15C",
            "fillOpacity": 0.08,
            "color": "#BDF57A",
            "weight": 2,
        },
    ).add_to(map_object)
    bounds = geojson_bounds(feature)
    map_object.fit_bounds(bounds)
    for image, parameters, name in earth_engine_layers or []:
        ee_tile_layer(image, parameters, name).add_to(map_object)
    folium.LayerControl(collapsed=False).add_to(map_object)
    return st_folium(map_object, width=None, height=height)
