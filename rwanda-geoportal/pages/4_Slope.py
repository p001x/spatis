import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import pandas as pd
from gee_scripts.auth import initialize_gee
from gee_scripts.slope import compute_slope
from gee_scripts.ndvi import RWANDA_DISTRICTS
from gee_scripts.classify_utils import class_palette, class_labels
from reports.report_builder import build_report
from utils.style import apply_style, material

initialize_gee()
apply_style()

st.title(":material/terrain: Slope & Terrain Analysis")
st.markdown(
    "Slope (degrees), aspect, and hillshade derived from the **SRTM 30 m DEM**. "
    "Useful for erosion risk, accessibility, and land use planning."
)


def _render_panels(classify, district_name):
    """Render A/B/C classified-map panels in a 2-column grid (reference-image layout)."""
    n      = classify["n_classes"]
    pal    = class_palette(n)
    lbls   = class_labels(n)
    panels = classify["panels"]

    st.caption(
        f"**Quantile-based {n}-class classification** — breakpoints computed from the actual pixel "
        f"distribution within {district_name}.  Panels A=Slope, B=Elevation, C=Aspect."
    )
    swatches = "".join(
        f"<span style='display:inline-flex;align-items:center;margin:2px 8px 2px 0'>"
        f"<span style='background:{c};width:14px;height:14px;border-radius:3px;"
        f"display:inline-block;margin-right:5px'></span>"
        f"<span style='font-size:0.82rem'>{lbl}</span></span>"
        for c, lbl in zip(pal, lbls)
    )
    st.markdown(f"<div style='margin:4px 0 12px'><b>Legend:</b> {swatches}</div>",
                unsafe_allow_html=True)

    for i in range(0, len(panels), 2):
        row  = panels[i : i + 2]
        cols = st.columns(len(row))
        for col, panel in zip(cols, row):
            with col:
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
                    f"<span style='background:#1a3a5c;color:#fff;font-weight:700;"
                    f"padding:2px 9px;border-radius:4px;font-size:1rem'>{panel['letter']}</span>"
                    f"<span style='font-weight:600;font-size:1rem'>{panel['title']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if panel["breakpoints"]:
                    st.caption("Breakpoints: " + " | ".join(f"{b:.4g}" for b in panel["breakpoints"]))
                try:
                    st.image(panel["thumb_url"], width='stretch')
                except Exception:
                    st.info("Thumbnail loading…")
                df_cls = pd.DataFrame(
                    [{"Class": k, "Area (km²)": v} for k, v in panel["areas"].items()]
                )
                fig = px.bar(
                    df_cls, x="Class", y="Area (km²)", color="Class",
                    color_discrete_sequence=pal, height=220,
                )
                fig.update_layout(
                    showlegend=False, margin=dict(t=10, b=0, l=0, r=0),
                    xaxis_tickangle=-30, xaxis_tickfont_size=10,
                )
                st.plotly_chart(fig, width='stretch')
                st.dataframe(df_cls, width='stretch', hide_index=True)
                st.markdown("---")


with st.sidebar:
    st.header("Analysis Controls")
    district = st.selectbox("District", RWANDA_DISTRICTS, index=RWANDA_DISTRICTS.index("Musanze"))
    layer = st.radio("Display Layer", ["Slope", "Hillshade", "Aspect"], index=0)
    st.markdown("##### Classification")
    n_classes = st.slider("Number of classes", min_value=2, max_value=10, value=5, step=1)
    run = st.button(f"{material('play_arrow')} Analyse Terrain", width='stretch', type="primary")

if run:
    st.session_state.pop("slope_result", None)
    st.session_state.pop("slope_error", None)
    with st.spinner(f"Computing terrain for {district}…"):
        try:
            result = compute_slope(district, n_classes=n_classes)
            st.session_state["slope_result"] = result
        except Exception as e:
            st.session_state["slope_error"] = str(e)

if "slope_error" in st.session_state:
    st.error(f"GEE computation failed: {st.session_state['slope_error']}")
    st.caption("Fix the issue above, then click **Analyse Terrain** again.")
elif "slope_result" in st.session_state:
    result = st.session_state["slope_result"]

    tab_map, tab_stats, tab_classify, tab_report = st.tabs(
        [":material/map: Map", ":material/bar_chart: Statistics", ":material/category: Classify A/B/C", ":material/description: Report"]
    )

    with tab_map:
        tile_url = {
            "Slope":     result["slope_tile_url"],
            "Hillshade": result["hillshade_tile_url"],
            "Aspect":    result["aspect_tile_url"],
        }[layer]

        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=tile_url,
            attr="Google Earth Engine",
            name=layer,
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])

        if layer == "Slope":
            st.markdown(
                "**Legend (degrees):** "
                "<span style='color:#2166ac'>■</span> Flat (0–5°) &nbsp;"
                "<span style='color:#92c5de'>■</span> Gentle (5–15°) &nbsp;"
                "<span style='color:#f7f7f7'>■</span> Moderate (15–25°) &nbsp;"
                "<span style='color:#f4a582'>■</span> Steep (25–35°) &nbsp;"
                "<span style='color:#b2182b'>■</span> Very Steep (&gt;35°)",
                unsafe_allow_html=True,
            )

    with tab_stats:
        st.subheader(f"Terrain Statistics — {result['district']}")
        cols = st.columns(4)
        stat_items = list(result["stats"].items())
        for i, (label, val) in enumerate(stat_items[:4]):
            cols[i].metric(label, val)
        if len(stat_items) > 4:
            cols2 = st.columns(len(stat_items) - 4)
            for i, (label, val) in enumerate(stat_items[4:]):
                cols2[i].metric(label, val)
        st.markdown("#### Slope Class Areas")
        df = pd.DataFrame(
            [{"Class": k, "Area (km²)": v} for k, v in result["class_areas_km2"].items()]
        )
        fig = px.bar(
            df, x="Class", y="Area (km²)", color="Class",
            color_discrete_sequence=["#2166ac", "#92c5de", "#f7f7f7", "#f4a582", "#b2182b"],
            title=f"Slope Class Distribution — {result['district']}",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width='stretch')
        st.dataframe(df, width='stretch', hide_index=True)

    with tab_classify:
        st.subheader(f"Quantile Classification — {result['district']}")
        if "classify" in result:
            _render_panels(result["classify"], result["district"])
        else:
            st.info("Re-run analysis to generate classification panels.")

    with tab_report:
        st.subheader("Download PDF Report")
        notes = (
            f"Terrain analysis derived from USGS SRTM 30 m DEM. "
            f"Slope calculated using ee.Terrain.slope(). "
            f"District: {result['district']}. Data source: USGS/SRTMGL1_003."
        )
        pdf_bytes = build_report(
            module_name="Slope & Terrain Analysis",
            district=result["district"],
            date_range="SRTM (static)",
            stats=result["stats"],
            class_areas=result["class_areas_km2"],
            extra_notes=notes,
        )
        st.download_button(
            label=":material/download: Download PDF Report",
            data=pdf_bytes,
            file_name=f"Slope_{result['district']}.pdf",
            mime="application/pdf",
            width='stretch',
        )
else:
    st.info("Select a district and click **Analyse Terrain** to begin.")
