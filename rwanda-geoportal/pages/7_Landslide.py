import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from gee_scripts.auth import initialize_gee
from gee_scripts.ndvi import RWANDA_DISTRICTS
from gee_scripts.landslide import (
    compute_landslide_susceptibility,
    WEIGHTS,
    FACTOR_META,
    LSI_CLASS_NAMES,
    LITHOLOGY_ASSET,
)
from gee_scripts.classify_utils import class_palette, class_labels
from reports.report_builder import build_report
from utils.style import apply_style, material

initialize_gee()
apply_style()

st.title(":material/landslide: Landslide Susceptibility Analysis")
st.markdown(
    "Landslide Susceptibility Index (LSI) computed via **AHP-Weighted Overlay** using 7 conditioning "
    "factors: **slope** (30%), **rainfall** (20%), **lithology** (15%), **soil type** (14%), "
    "**land cover** (9%), **TWI** (7%), and **distance to roads** (5%).  \n"
    "Score 1 (Very Low) → 5 (Very High susceptibility)."
)


# ── shared panel-grid renderer ──────────────────────────────────────────────
def _render_panels(classify, district_name):
    n      = classify["n_classes"]
    pal    = class_palette(n)
    lbls   = class_labels(n)
    panels = classify["panels"]

    st.caption(
        f"**Quantile-based {n}-class classification** — breakpoints derived from the actual pixel "
        f"distribution within {district_name}.  "
        f"Panels: A=LSI, B=Slope, C=Rainfall, D=Lithology, E=Soil Type, F=Land Cover, G=TWI, H=Roads."
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
                    f"<span style='background:#5c1a1a;color:#fff;font-weight:700;"
                    f"padding:2px 9px;border-radius:4px;font-size:1rem'>{panel['letter']}</span>"
                    f"<span style='font-weight:600;font-size:1rem'>{panel['title']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if panel["breakpoints"]:
                    st.caption("Breakpoints: " + " | ".join(f"{b:.3g}" for b in panel["breakpoints"]))
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


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Analysis Controls")

    district = st.selectbox(
        "District",
        RWANDA_DISTRICTS,
        index=RWANDA_DISTRICTS.index("Musanze"),
    )

    st.markdown("##### CHIRPS Rainfall Period")
    col_a, col_b = st.columns(2)
    with col_a:
        start_year = st.number_input("Start year", min_value=1981, max_value=2024, value=2019, step=1)
    with col_b:
        end_year = st.number_input("End year", min_value=1981, max_value=2024, value=2024, step=1)
    if start_year > end_year:
        st.error("Start year must be ≤ end year.")

    st.markdown("##### AHP Weights (fixed)")
    for k, m in FACTOR_META.items():
        st.progress(m["weight_pct"], text=f"{material(m['icon'])} {m['label']}: {m['weight_pct']}%")

    st.markdown("##### Classification")
    n_classes = st.slider("Number of classes", min_value=2, max_value=10, value=5, step=1)

    run = st.button(f"{material('play_arrow')} Run Landslide Analysis", width='stretch', type="primary")

    st.markdown("---")
    st.caption(
        f"**Lithology asset:** `{LITHOLOGY_ASSET}`  \n"
        "The GEE service account must have **Viewer** access to this asset. "
        "Share it via the GEE Code Editor → Assets → ⋮ → Share."
    )

# ── Main content ─────────────────────────────────────────────────────────────
if run:
    st.session_state.pop("landslide_result", None)
    st.session_state.pop("landslide_error", None)
    if start_year > end_year:
        st.session_state["landslide_error"] = "Fix the year range before running."
    else:
        with st.spinner(
            f"Computing landslide susceptibility for **{district}** "
            f"({start_year}–{end_year} CHIRPS rainfall)…  "
            "First run may take 30–60 s."
        ):
            try:
                result = compute_landslide_susceptibility(
                    district_name=district,
                    start_year=int(start_year),
                    end_year=int(end_year),
                    n_classes=n_classes,
                )
                st.session_state["landslide_result"] = result
            except Exception as e:
                err = str(e)
                if "does not exist" in err or "not found" in err.lower() or "permission" in err.lower():
                    st.session_state["landslide_error"] = (
                        f"Cannot access the lithology asset. "
                        f"Share `{LITHOLOGY_ASSET}` with your GEE service account "
                        f"(GEE Code Editor → Assets → ⋮ → Share → add service account email as Viewer)."
                    )
                else:
                    st.session_state["landslide_error"] = f"GEE computation failed: {e}"

if "landslide_error" in st.session_state:
    st.error(st.session_state["landslide_error"])
    st.caption("Fix the issue above, then click **Run Landslide Analysis** again.")
elif "landslide_result" in st.session_state:
    result = st.session_state["landslide_result"]

    current_district = result.get("district", district)

    tab_map, tab_stats, tab_classify, tab_report = st.tabs(
        [":material/map: Map", ":material/bar_chart: Statistics", ":material/category: Classify A–H", ":material/description: Report"]
    )

    # ── Map ─────────────────────────────────────────────────────────────────
    with tab_map:
        layer_choice = st.radio(
            "Display layer",
            ["LSI (continuous 1–5)", "LSI Class (5 discrete zones)"],
            horizontal=True,
        )
        tile_url = (
            result["lsi_tile_url"]
            if layer_choice.startswith("LSI (")
            else result["lsi_class_tile_url"]
        )

        m = folium.Map(location=result["center"], zoom_start=11, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=tile_url,
            attr="Google Earth Engine",
            name="Landslide Susceptibility",
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=520, returned_objects=[])

        st.markdown(
            "**Legend:** "
            "<span style='color:#1a9850'>■</span> Very Low &nbsp;"
            "<span style='color:#91cf60'>■</span> Low &nbsp;"
            "<span style='color:#fee08b'>■</span> Moderate &nbsp;"
            "<span style='color:#fc8d59'>■</span> High &nbsp;"
            "<span style='color:#d73027'>■</span> Very High",
            unsafe_allow_html=True,
        )
        st.caption(
            f"District: **{current_district}**  |  "
            f"LSI = 0.30·Slope + 0.20·Rainfall + 0.15·Lithology + 0.14·SoilType "
            f"+ 0.09·LandCover + 0.07·TWI + 0.05·Roads  |  "
            f"Rainfall: {result['start_year']}–{result['end_year']}"
        )

    # ── Statistics ───────────────────────────────────────────────────────────
    with tab_stats:
        st.subheader(f"Landslide Susceptibility — {current_district}")
        st.caption(f"CHIRPS rainfall: {result['start_year']}–{result['end_year']}")

        cols = st.columns(4)
        for i, (label, val) in enumerate(result["stats"].items()):
            cols[i].metric(label, val)

        st.markdown("#### Area by Susceptibility Class")
        pal5 = ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"]
        df_class = pd.DataFrame(
            [{"Class": k, "Area (km²)": v} for k, v in result["class_areas_km2"].items()]
        )
        col_chart, col_pie = st.columns(2)
        with col_chart:
            fig_bar = px.bar(
                df_class, x="Class", y="Area (km²)", color="Class",
                color_discrete_sequence=pal5,
                title=f"Area by Susceptibility Class — {current_district}",
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, width='stretch')
        with col_pie:
            fig_pie = px.pie(
                df_class, names="Class", values="Area (km²)",
                color="Class",
                color_discrete_map={k: c for k, c in zip(LSI_CLASS_NAMES, pal5)},
                title="Proportional Area",
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, width='stretch')
        st.dataframe(df_class, width='stretch', hide_index=True)

        st.markdown("#### AHP Factor Weights")
        df_weights = pd.DataFrame([
            {
                "Factor": m["label"],
                "Weight": f'{m["weight_pct"]}%',
                "Weight (decimal)": WEIGHTS[k],
            }
            for k, m in FACTOR_META.items()
        ])
        fig_w = go.Figure(go.Bar(
            x=[m["label"] for m in FACTOR_META.values()],
            y=[m["weight_pct"] for m in FACTOR_META.values()],
            marker_color=["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#66bd63", "#1a9850"],
            text=[f'{m["weight_pct"]}%' for m in FACTOR_META.values()],
            textposition="outside",
        ))
        fig_w.update_layout(
            title="AHP Conditioning Factor Weights",
            yaxis_title="Weight (%)",
            xaxis_tickangle=-20,
            showlegend=False,
            margin=dict(t=50, b=60),
        )
        st.plotly_chart(fig_w, width='stretch')
        st.dataframe(df_weights, width='stretch', hide_index=True)

        st.info(
            "**Fixed LSI breaks:** <1.8 Very Low | 1.8–2.6 Low | 2.6–3.4 Moderate | "
            "3.4–4.2 High | ≥4.2 Very High.  \n"
            "CHIRPS: 5 km · Terrain: 30 m · GRIP4 roads (sat-io) · "
            "ISDA Africa soil texture · ESA WorldCover 2021."
        )

    # ── Classify A–H ─────────────────────────────────────────────────────────
    with tab_classify:
        st.subheader(f"Quantile Classification — {current_district}")
        if "classify" in result:
            _render_panels(result["classify"], current_district)
        else:
            st.info("Re-run the analysis to generate classification panels.")

    # ── Report ───────────────────────────────────────────────────────────────
    with tab_report:
        st.subheader("Download PDF Report")
        notes = (
            f"Landslide Susceptibility Index (LSI) computed via AHP-Weighted Overlay for "
            f"{current_district} district. "
            f"Factors and weights: Slope 30%, Rainfall 20%, Lithology 15%, Soil Type 14%, "
            f"Land Cover 9%, TWI 7%, Distance to Roads 5%. "
            f"CHIRPS mean annual rainfall averaged over {result['start_year']}–{result['end_year']}. "
            f"Lithology from GEE asset ({LITHOLOGY_ASSET}); soil texture from ISDA Africa v1; "
            f"land cover from ESA WorldCover 2021; roads from GRIP4 Africa (sat-io). "
            f"LSI classes: <1.8 Very Low, 1.8–2.6 Low, 2.6–3.4 Moderate, "
            f"3.4–4.2 High, ≥4.2 Very High."
        )
        pdf_bytes = build_report(
            module_name="Landslide Susceptibility",
            district=current_district,
            date_range=f"CHIRPS {result['start_year']}–{result['end_year']}",
            stats=result["stats"],
            class_areas=result["class_areas_km2"],
            extra_notes=notes,
        )
        st.download_button(
            label=":material/download: Download PDF Report",
            data=pdf_bytes,
            file_name=f"Landslide_{current_district}_{result['start_year']}_{result['end_year']}.pdf",
            mime="application/pdf",
            width='stretch',
        )

else:
    st.info(
        "Select a **district** and rainfall period in the sidebar, "
        "then click **Run Landslide Analysis** to begin."
    )

    st.markdown("---")
    st.markdown("### AHP Conditioning Factors")
    df_preview = pd.DataFrame([
        {"Factor": m["label"], "Weight": f'{m["weight_pct"]}%', "Description": desc}
        for (k, m), desc in zip(
            FACTOR_META.items(),
            [
                "Slope ≥35° → highest risk; <5° → lowest",
                "Rainfall ≥1500 mm/yr → highest; <900 mm → lowest",
                "Remapped from lithology classes 1–10 (GEE asset)",
                "ISDA texture: sandy = low, clay = high susceptibility",
                "Bare/sparse land = high risk; tree cover = low",
                "High flow accumulation → soil saturation risk",
                "Proximity to roads → destabilised slopes",
            ],
        )
    ])
    st.dataframe(df_preview, width='stretch', hide_index=True)
