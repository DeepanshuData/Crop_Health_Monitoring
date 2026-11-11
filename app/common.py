"""Shared Streamlit components and cached local scene loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from src.crop_health_data import PROJECT_ROOT, load_verified_scene

STYLE_FILE = PROJECT_ROOT / "app" / "styles" / "style.css"


@st.cache_data(show_spinner="Loading and validating the verified Mysuru scene…")
def load_scene() -> dict[str, Any]:
    return load_verified_scene(PROJECT_ROOT)


def inject_styles() -> None:
    if not STYLE_FILE.is_file():
        raise FileNotFoundError(f"Application stylesheet not found: {STYLE_FILE}")
    st.markdown(f"<style>{STYLE_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_header(scene: dict[str, Any], section: str) -> None:
    st.markdown(
        f"""
        <div class="agri-topline">
          <div>
            <div class="agri-kicker">AGRIVISION &nbsp;·&nbsp; {section.upper()}</div>
            <h1 class="agri-title">Satellite Intelligence for Smarter Agriculture</h1>
          </div>
          <div class="scene-badge">
            <span class="scene-live"></span>
            <span><b>Mysuru, Karnataka</b><small>Sentinel-2 · 06 Feb 2025 · 20 m</small></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Spectral measurements describe reflectance patterns; they are not confirmed crop-health diagnoses."
    )


def render_index_map(scene: dict[str, Any], index_name: str, caption: str | None = None) -> None:
    from src.crop_health_data import index_rgba

    st.image(
        index_rgba(scene, index_name),
        caption=caption or f"{index_name} · gray pixels are invalid or masked",
        use_container_width=True,
    )


def render_metric_row(scene: dict[str, Any], index_names: tuple[str, ...]) -> None:
    columns = st.columns(len(index_names))
    for column, name in zip(columns, index_names):
        stat = scene["statistics"][name]
        column.metric(f"Mean {name}", f'{stat["Mean"]:.4f}')


def gee_project_from_secrets() -> str | None:
    import os

    return os.environ.get("EARTHENGINE_PROJECT")
