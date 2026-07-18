import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import pandas as pd
from datetime import date, timedelta
from gee_scripts.auth import initialize_gee
from gee_scripts.lst import compute_lst
from gee_scripts.ndvi import RWANDA_DISTRICTS
from gee_scripts.classify_utils import class_palette, class_labels
from reports.report_builder import build_report
from utils.style import apply_style, material

initialize_gee()
apply_style()

st.title(":material/device_thermostat: Land Surface Temperature (LST)")
st.markdown(
    "LST in **°C** derived from **Landsat 9** using the mono-window algorithm. "
    "Emissivity is estimated from NDVI-based fractional vegetation cover."
)


def _render_panels(classify, district_name):
    n    = classify["n_classes"]
    pal  = class_palette(n)
    lbls = class_labels(n)
    panels = classify["panels"]

    st.caption(
        f"**Quantile-based {n}-class classification** — breakpoints are computed from the actual "
        f"pixel distribution within {district_name} so classes always span equal-frequency intervals."
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
                    st.caption("Breakpoints (°C): " + " | ".join(f"{b:.3g}" for b in panel["breakpoints"]))
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
    run = st.button(f"{material('play_arrow')} Calculate LST", width='stretch', type="primary")

if run:
    st.session_state.pop("lst_result", None)
    st.session_state.pop("lst_error", None)
    with st.spinner(f"Computing LST for {district}…"):
        try:
            result = compute_lst(district, str(start), str(end), n_classes=n_classes)
            st.session_state["lst_result"] = result
        except Exception as e:
            st.session_state["lst_error"] = str(e)

if "lst_error" in st.session_state:
    st.error(f"GEE computation failed: {st.session_state['lst_error']}")
    st.caption("Fix the issue above, then click **Calculate LST** again.")
elif "lst_result" in st.session_state:
    result = st.session_state["lst_result"]

    tab_map, tab_stats, tab_classify, tab_report = st.tabs(
        [":material/map: Map", ":material/bar_chart: Statistics", ":material/category: Classify", ":material/description: Report"]
    )

    with tab_map:
        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=result["tile_url"],
            attr="Google Earth Engine",
            name="LST",
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])
        st.markdown(
            "**Legend (°C):** "
            "<span style='color:#313695'>■</span> Cool (&lt;20) &nbsp;"
            "<span style='color:#74add1'>■</span> Moderate (20–25) &nbsp;"
            "<span style='color:#fee090'>■</span> Warm (25–30) &nbsp;"
            "<span style='color:#f46d43'>■</span> Hot (30–35) &nbsp;"
            "<span style='color:#a50026'>■</span> Very Hot (&gt;35)",
            unsafe_allow_html=True,
        )

    with tab_stats:
        st.subheader(f"Statistics — {result['district']}")
        st.caption(f"Period: {result['start_date']} → {result['end_date']}")
        cols = st.columns(4)
        for i, (label, val) in enumerate(result["stats"].items()):
            cols[i].metric(label, val)
        st.markdown("#### Temperature Zone Areas")
        df = pd.DataFrame(
            [{"Zone": k, "Area (km²)": v} for k, v in result["class_areas_km2"].items()]
        )
        fig = px.bar(
            df, x="Zone", y="Area (km²)", color="Zone",
            color_discrete_sequence=["#313695", "#74add1", "#fee090", "#f46d43", "#a50026"],
            title=f"LST Temperature Zone Areas — {result['district']}",
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
            f"Land Surface Temperature is derived from Landsat 9 Band 10 (thermal infrared) "
            f"using the mono-window algorithm with NDVI-based emissivity correction. "
            f"Analysis covers {result['district']} district from {result['start_date']} to {result['end_date']}."
        )
        pdf_bytes = build_report(
            module_name="Land Surface Temperature",
            district=result["district"],
            date_range=f"{result['start_date']} to {result['end_date']}",
            stats=result["stats"],
            class_areas=result["class_areas_km2"],
            extra_notes=notes,
        )
        st.download_button(
            label=":material/download: Download PDF Report",
            data=pdf_bytes,
            file_name=f"LST_{result['district']}_{result['start_date']}.pdf",
            mime="application/pdf",
            width='stretch',
        )
else:
    st.info("Select a district and date range, then click **Calculate LST** to begin.")
