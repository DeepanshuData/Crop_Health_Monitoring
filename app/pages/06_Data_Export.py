"""Download available district CSV and Earth Engine GeoTIFF results."""

from pathlib import Path

import streamlit as st

from bootstrap import setup_page


district, feature, region_name = setup_page("Data Export")
active_district = st.session_state["active_district"]
district_output = Path("outputs") / active_district

st.subheader("Local CSV and chart results")
if active_district == "custom":
    st.info("Custom-boundary exports are organized in the uploads and live-session exports.")
else:
    st.code(str(district_output.resolve()))

available = []
for directory in ("exports", "timeseries", "reports"):
    folder = district_output / directory
    if folder.exists():
        available.extend(sorted(folder.glob("*.csv")))

if not available:
    st.info("Run an analysis to generate available CSV results.")
else:
    for csv_path in available:
        st.download_button(
            f"Download {csv_path.name}",
            data=csv_path.read_bytes(),
            file_name=csv_path.name,
            mime="text/csv",
        )

st.subheader("Earth Engine GeoTIFF exports")
map_folder = district_output / "maps"
manifest_files = sorted(map_folder.glob("*exports*.csv")) if map_folder.exists() else []
if manifest_files:
    for manifest in manifest_files:
        st.dataframe(
            __import__("pandas").read_csv(manifest),
            use_container_width=True,
        )
        st.caption("GeoTIFFs are Google Drive export tasks; completed files are not exposed locally until exported.")
else:
    st.info("No completed or submitted export manifest is available for this district.")
