import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import pandas as pd
from datetime import date, timedelta
from gee_scripts.auth import initialize_gee
from gee_scripts.ndvi import compute_ndvi, RWANDA_DISTRICTS
from gee_scripts.classify_utils import class_palette, class_labels
from reports.report_builder import build_report
from utils.style import apply_style, material

initialize_gee()
apply_style()

st.title(":material/eco: NDVI — Vegetation Health Analysis")
st.markdown(
    "Normalized Difference Vegetation Index computed from **Sentinel-2 SR** 10 m imagery. "
    "Cloud-masked median composite over the selected date range."
)


def _render_panels(classify, district_name):
    """Render A/B/C classified-map panels in a 2-column grid."""
    n   = classify["n_classes"]
    pal = class_palette(n)
    lbls = class_labels(n)
    panels = classify["panels"]

    st.caption(
        f"**Quantile-based {n}-class classification** — breakpoints are computed from the actual "
        f"pixel distribution within {district_name} so classes always span equal-frequency intervals."
    )

    # Colour legend strip
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
    district = st.selectbox("District", RWANDA_DISTRICTS, index=RWANDA_DISTRICTS.index("Gasabo"))
    col_a, col_b = st.columns(2)
    with col_a:
        start = st.date_input("Start date", value=date.today() - timedelta(days=180))
    with col_b:
        end = st.date_input("End date", value=date.today())
    st.markdown("##### Classification")
    n_classes = st.slider("Number of classes", min_value=2, max_value=10, value=5, step=1)
    run = st.button(f"{material('play_arrow')} Calculate NDVI", width='stretch', type="primary")

if run:
    st.session_state.pop("ndvi_result", None)
    st.session_state.pop("ndvi_error", None)
    with st.spinner(f"Computing NDVI for {district}…"):
        try:
            result = compute_ndvi(district, str(start), str(end), n_classes=n_classes)
            st.session_state["ndvi_result"] = result
        except Exception as e:
            st.session_state["ndvi_error"] = str(e)

if "ndvi_error" in st.session_state:
    st.error(f"GEE computation failed: {st.session_state['ndvi_error']}")
    st.caption("Fix the issue above (e.g. check your GEE credentials or date range), then click **Calculate NDVI** again.")
elif "ndvi_result" in st.session_state:
    result = st.session_state["ndvi_result"]

    tab_map, tab_stats, tab_classify, tab_report = st.tabs(
        [":material/map: Map", ":material/bar_chart: Statistics", ":material/category: Classify", ":material/description: Report"]
    )

    with tab_map:
        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=result["tile_url"],
            attr="Google Earth Engine",
            name="NDVI",
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])
        st.markdown(
            "**Legend:** "
            "<span style='color:#a50026'>■</span> Very Low &nbsp;"
            "<span style='color:#fc8d59'>■</span> Low &nbsp;"
            "<span style='color:#fee090'>■</span> Moderate &nbsp;"
            "<span style='color:#91cf60'>■</span> High &nbsp;"
            "<span style='color:#1a9850'>■</span> Very High",
            unsafe_allow_html=True,
        )

    with tab_stats:
        st.subheader(f"Statistics — {result['district']}")
        st.caption(f"Period: {result['start_date']} → {result['end_date']}")
        cols = st.columns(4)
        for i, (label, val) in enumerate(result["stats"].items()):
            cols[i].metric(label, val)
        st.markdown("#### Vegetation Class Areas")
        df = pd.DataFrame(
            [{"Class": k, "Area (km²)": v} for k, v in result["class_areas_km2"].items()]
        )
        fig = px.bar(
            df, x="Class", y="Area (km²)", color="Class",
            color_discrete_sequence=["#d73027", "#fc8d59", "#fee08b", "#91cf60", "#1a9850"],
            title=f"NDVI Class Areas — {result['district']}",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width='stretch')
        st.dataframe(df, width='stretch', hide_index=True)

    with tab_classify:
        st.subheader(f"Quantile Classification — {result['district']}")
        if "classify" in result:
            _render_panels(result["classify"], result["district"])
        else:
            st.info("Re-run analysis to generate classification.")

    with tab_report:
        st.subheader("Download PDF Report")
        notes = (
            f"NDVI values range from -1 to 1. Values above 0.4 indicate healthy dense vegetation. "
            f"The analysis covers {result['district']} district from {result['start_date']} to {result['end_date']} "
            f"using Sentinel-2 SR cloud-masked median composite at 10 m resolution."
        )
        pdf_bytes = build_report(
            module_name="NDVI Vegetation Health",
            district=result["district"],
            date_range=f"{result['start_date']} to {result['end_date']}",
            stats=result["stats"],
            class_areas=result["class_areas_km2"],
            extra_notes=notes,
        )
        st.download_button(
            label=":material/download: Download PDF Report",
            data=pdf_bytes,
            file_name=f"NDVI_{result['district']}_{result['start_date']}.pdf",
            mime="application/pdf",
            width='stretch',
        )
else:
    st.info("Select a district and date range, then click **Calculate NDVI** to begin.")
