import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import pandas as pd
from datetime import date, timedelta
from gee_scripts.auth import initialize_gee
from gee_scripts.air_pollution import compute_no2, WHO_NO2_ANNUAL_THRESHOLD
from gee_scripts.ndvi import RWANDA_DISTRICTS
from gee_scripts.classify_utils import class_palette, class_labels
from reports.report_builder import build_report
from utils.style import apply_style, material

initialize_gee()
apply_style()

S5P_MIN_DATE = date(2018, 7, 1)

st.title(":material/air: Air Pollution — NO₂ Analysis")
st.markdown(
    "Tropospheric NO₂ column from **Sentinel-5P OFFL** (offline, reprocessed — ~3.5 km resolution). "
    f"WHO annual guideline: **{WHO_NO2_ANNUAL_THRESHOLD} µg/m³** (≈10 µmol/m²)."
)


def _render_panels(classify, district_name):
    n      = classify["n_classes"]
    pal    = class_palette(n)
    lbls   = class_labels(n)
    panels = classify["panels"]

    st.caption(
        f"**Quantile-based {n}-class classification** — breakpoints computed from the actual "
        f"pixel distribution within {district_name} (µmol/m²)."
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
                    st.caption("Breakpoints (µmol/m²): " + " | ".join(f"{b:.3g}" for b in panel["breakpoints"]))
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
    district = st.selectbox("District", RWANDA_DISTRICTS, index=RWANDA_DISTRICTS.index("Nyarugenge"))
    col_a, col_b = st.columns(2)
    with col_a:
        start = st.date_input("Start date", value=date.today() - timedelta(days=365), min_value=S5P_MIN_DATE)
    with col_b:
        end = st.date_input("End date", value=date.today(), min_value=S5P_MIN_DATE)
    st.caption("Sentinel-5P NO₂ data is only available from July 2018 onward.")
    st.markdown("##### Classification")
    n_classes = st.slider("Number of classes", min_value=2, max_value=10, value=5, step=1)
    run = st.button(f"{material('play_arrow')} Analyse NO₂", width='stretch', type="primary")

if run:
    st.session_state.pop("no2_result", None)
    st.session_state.pop("no2_error", None)
    if start >= end:
        st.session_state["no2_error"] = "Start date must be before end date."
    elif start < S5P_MIN_DATE:
        st.session_state["no2_error"] = (
            "Sentinel-5P NO₂ data is only available from July 2018 onward — "
            "please choose a later start date."
        )
    else:
        with st.spinner(f"Computing NO₂ for {district} ({start} → {end})…"):
            try:
                result = compute_no2(district, str(start), str(end), n_classes=n_classes)
                st.session_state["no2_result"] = result
            except ValueError as e:
                st.session_state["no2_error"] = str(e)
            except Exception as e:
                st.session_state["no2_error"] = f"GEE computation failed: {e}"

if "no2_error" in st.session_state:
    st.error(st.session_state["no2_error"])
    st.caption("Fix the issue above, then click **Analyse NO₂** again.")
elif "no2_result" in st.session_state:
    result = st.session_state["no2_result"]

    if result["exceeds_who"]:
        st.warning(
            f":material/warning: Mean NO₂ ({result['stats']['Mean NO2 (µmol/m²)']} µmol/m²) **exceeds** the WHO annual threshold "
            f"of {WHO_NO2_ANNUAL_THRESHOLD} µmol/m²."
        )
    else:
        st.success(
            f":material/check_circle: Mean NO₂ ({result['stats']['Mean NO2 (µmol/m²)']} µmol/m²) is **within** the WHO annual threshold."
        )

    tab_map, tab_trend, tab_classify, tab_report = st.tabs(
        [":material/map: Map", ":material/trending_up: Trend", ":material/category: Classify", ":material/description: Report"]
    )

    with tab_map:
        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=result["tile_url"],
            attr="Google Earth Engine",
            name="NO₂ (µmol/m²)",
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])
        st.markdown(
            "**Legend (µmol/m²):** "
            "<span style='color:#000080'>■</span> Very Low &nbsp;"
            "<span style='color:#0000ff'>■</span> Low &nbsp;"
            "<span style='color:#00ffff'>■</span> Moderate &nbsp;"
            "<span style='color:#ffff00'>■</span> High &nbsp;"
            "<span style='color:#ff0000'>■</span> Very High",
            unsafe_allow_html=True,
        )
        st.subheader("Key Statistics")
        cols = st.columns(4)
        for i, (label, val) in enumerate(result["stats"].items()):
            cols[i].metric(label, val)

    with tab_trend:
        st.subheader(f"Monthly NO₂ Trend — {result['district']}")
        ts = result.get("time_series", [])
        if ts:
            df_ts = pd.DataFrame(ts)
            MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if "year" in df_ts.columns and df_ts["year"].nunique() > 1:
                df_ts["Month Name"] = df_ts.apply(
                    lambda r: f"{MONTH_NAMES[int(r['month']) - 1]} {int(r['year'])}", axis=1
                )
            else:
                df_ts["Month Name"] = df_ts["month"].apply(lambda m: MONTH_NAMES[int(m) - 1])
            fig = px.line(
                df_ts, x="Month Name", y="NO2 (µmol/m²)",
                markers=True,
                title=f"Monthly Mean NO₂ — {result['district']} ({result['start_date'][:4]}–{result['end_date'][:4]})",
            )
            fig.add_hline(
                y=WHO_NO2_ANNUAL_THRESHOLD,
                line_dash="dash",
                line_color="red",
                annotation_text="WHO Threshold",
            )
            st.plotly_chart(fig, width='stretch')
            st.dataframe(df_ts[["Month Name", "NO2 (µmol/m²)"]], width='stretch', hide_index=True)
        else:
            st.info("No monthly data available for the selected period.")

    with tab_classify:
        st.subheader(f"Quantile Classification — {result['district']}")
        if "classify" in result:
            _render_panels(result["classify"], result["district"])
        else:
            st.info("Re-run analysis to generate classification.")

    with tab_report:
        st.subheader("Download PDF Report")
        who_status = "exceeds" if result["exceeds_who"] else "is within"
        notes = (
            f"Sentinel-5P OFFL NO₂ tropospheric column density at ~3.5 km resolution. "
            f"Mean NO₂ for {result['district']} ({result['start_date']} to {result['end_date']}) "
            f"{who_status} the WHO annual guideline of {WHO_NO2_ANNUAL_THRESHOLD} µmol/m²."
        )
        pdf_bytes = build_report(
            module_name="Air Pollution — NO₂",
            district=result["district"],
            date_range=f"{result['start_date']} to {result['end_date']}",
            stats=result["stats"],
            class_areas={},
            extra_notes=notes,
        )
        st.download_button(
            label=":material/download: Download PDF Report",
            data=pdf_bytes,
            file_name=f"NO2_{result['district']}_{result['start_date']}.pdf",
            mime="application/pdf",
            width='stretch',
        )
else:
    st.info("Select a district and date range, then click **Analyse NO₂** to begin.")
