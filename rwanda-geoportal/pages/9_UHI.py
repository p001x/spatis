import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from datetime import date, timedelta

from gee_scripts.auth import initialize_gee
from gee_scripts.uhi import compute_uhi
from gee_scripts.ndvi import RWANDA_DISTRICTS
from reports.report_builder import build_uhi_report
from utils.style import apply_style, material

initialize_gee()
apply_style()

st.title(":material/location_city: Urban Heat Island — LST vs Impervious Surface")
st.markdown(
    "Relationship between **Land Surface Temperature (LST)** and **impervious surface extent (NDBI)** "
    "derived from Landsat 9. Zonal means are computed over a grid clipped to the district boundary, "
    "classified bivariately (Low/Mid/High per axis), and related via OLS regression — the same workflow "
    "used in sector-level UHI studies, adapted here to a grid since no sector shapefile is loaded."
)

with st.sidebar:
    st.header("Analysis Controls")
    district = st.selectbox("District", RWANDA_DISTRICTS, index=RWANDA_DISTRICTS.index("Gasabo"))
    col_a, col_b = st.columns(2)
    with col_a:
        start = st.date_input("Start date", value=date.today() - timedelta(days=180))
    with col_b:
        end = st.date_input("End date", value=date.today())
    grid_size = st.slider(
        "Grid resolution (N×N zonal cells)", min_value=3, max_value=12, value=6, step=1,
        help="Higher = more zonal cells for the bivariate/regression analysis, but slower to compute.",
    )
    run = st.button(f"{material('play_arrow')} Calculate UHI", width='stretch', type="primary")

if run:
    st.session_state.pop("uhi_result", None)
    st.session_state.pop("uhi_error", None)
    with st.spinner(f"Computing LST × NDBI for {district}…"):
        try:
            result = compute_uhi(district, str(start), str(end), grid_size=grid_size)
            st.session_state["uhi_result"] = result
        except Exception as e:
            st.session_state["uhi_error"] = str(e)

if "uhi_error" in st.session_state:
    st.error(f"GEE computation failed: {st.session_state['uhi_error']}")
    st.caption("Fix the issue above, then click **Calculate UHI** again.")
elif "uhi_result" in st.session_state:
    result = st.session_state["uhi_result"]

    tab_map, tab_bivar, tab_report = st.tabs([":material/map: Maps", ":material/trending_up: Bivariate & Regression", ":material/description: Report"])

    with tab_map:
        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(tiles=result["lst_tile_url"], attr="GEE", name="LST", overlay=True, show=True).add_to(m)
        folium.TileLayer(tiles=result["ndbi_tile_url"], attr="GEE", name="NDBI", overlay=True, show=False).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])
        st.caption("Use the layer control (top-right of the map) to toggle between LST and NDBI.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**LST statistics**")
            st.dataframe(pd.DataFrame(result["lst_stats"].items(), columns=["Metric", "Value"]),
                         width='stretch', hide_index=True)
        with c2:
            st.markdown("**NDBI statistics**")
            st.dataframe(pd.DataFrame(result["ndbi_stats"].items(), columns=["Metric", "Value"]),
                         width='stretch', hide_index=True)

    with tab_bivar:
        st.caption(
            f"Grid: {result['grid_size']}×{result['grid_size']} cells · "
            f"{result['n_cells_with_data']} with valid data, {result['n_cells_no_data']} outside imagery footprint."
        )
        if not result.get("regression"):
            st.warning("Not enough grid cells with valid data to run a bivariate classification/regression.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.image(result["bivariate_png"], caption="Bivariate classification per grid cell", width='stretch')
            with c2:
                st.image(result["scatter_png"], caption="OLS regression: LST vs NDBI", width='stretch')

            reg = result["regression"]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("R²", reg["r2"])
            m2.metric("Slope", reg["slope"])
            m3.metric("p-value", f"{reg['p_value']:.4g}")
            m4.metric("n (cells)", reg["n"])

            if result["grid_table"]:
                st.markdown("**Grid cell zonal means**")
                st.dataframe(pd.DataFrame(result["grid_table"]), width='stretch', hide_index=True)

    with tab_report:
        st.subheader("Download PDF Report")
        if not result.get("regression"):
            st.info("Run an analysis with enough valid grid cells to generate the bivariate/regression report.")
        else:
            notes = (
                f"LST is derived from Landsat 9 Band 10 using the mono-window algorithm; NDBI is computed as "
                f"(SWIR1 − NIR) / (SWIR1 + NIR), a standard proxy for impervious/built-up surface extent. "
                f"Zonal means are aggregated over a {result['grid_size']}×{result['grid_size']} grid clipped to "
                f"the {result['district']} district boundary, classified into Low/Mid/High tertiles per axis, "
                f"and related via ordinary least squares regression. A positive slope indicates warmer "
                f"temperatures are associated with more impervious surface (a classic urban heat island signal)."
            )
            pdf_bytes = build_uhi_report(
                district=result["district"],
                date_range=f"{result['start_date']} to {result['end_date']}",
                lst_stats=result["lst_stats"],
                ndbi_stats=result["ndbi_stats"],
                regression=result["regression"],
                bivariate_png=result["bivariate_png"],
                scatter_png=result["scatter_png"],
                lst_thumb_url=result["lst_thumb_url"],
                ndbi_thumb_url=result["ndbi_thumb_url"],
                grid_size=result["grid_size"],
                n_cells_no_data=result["n_cells_no_data"],
                extra_notes=notes,
            )
            st.download_button(
                label=":material/download: Download PDF Report",
                data=pdf_bytes,
                file_name=f"UHI_{result['district']}_{result['start_date']}.pdf",
                mime="application/pdf",
                width='stretch',
            )
else:
    st.info("Select a district and date range, then click **Calculate UHI** to begin.")
