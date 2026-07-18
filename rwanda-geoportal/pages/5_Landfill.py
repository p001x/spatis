import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import pandas as pd
from gee_scripts.auth import initialize_gee
from gee_scripts.landfill import compute_landfill_suitability, FACTOR_META, FACTOR_ORDER
from gee_scripts.ndvi import RWANDA_DISTRICTS
from gee_scripts.classify_utils import class_palette, class_labels
from reports.report_builder import build_report
from utils.style import apply_style, material, material_html

initialize_gee()
apply_style()

st.title(":material/delete: Landfill Siting — Suitability Analysis")
st.markdown(
    "GIS-based Spatial Multi-Criteria Evaluation (SMCE) with AHP-derived weights: "
    "**distance from rivers** (30%), **distance from residential areas** (25%), **slope** (20%), "
    "**road accessibility** (15%), and **land cover** (10%). "
    "SI = 0.30·River + 0.25·Residential + 0.20·Slope + 0.15·Roads + 0.10·LULC.  \n"
    "Score: 1 (unsuitable) → 5 (highly suitable)."
)

if "landfill_reverse" not in st.session_state:
    st.session_state["landfill_reverse"] = {k: False for k in FACTOR_ORDER}


def _landfill_reverse_kwargs():
    flags = st.session_state["landfill_reverse"]
    return {
        "reverse_river":       flags["river"],
        "reverse_residential": flags["residential"],
        "reverse_slope":       flags["slope"],
        "reverse_road":        flags["road"],
        "reverse_lulc":        flags["lulc"],
    }


def _render_panels(classify, district_name):
    """Render A–F classified-map panels in a 2-column grid."""
    n      = classify["n_classes"]
    pal    = class_palette(n)
    lbls   = class_labels(n)
    panels = classify["panels"]

    st.caption(
        f"**Quantile-based {n}-class classification** — breakpoints computed from the actual "
        f"pixel distribution within {district_name}.  "
        f"Panels: A=Suitability Index, B=River Distance, C=Residential Distance, "
        f"D=Slope, E=Road Accessibility, F=Land Cover."
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


with st.sidebar:
    st.header("Analysis Controls")
    district = st.selectbox("District", RWANDA_DISTRICTS, index=RWANDA_DISTRICTS.index("Nyagatare"))
    st.markdown("##### AHP Weights (fixed)")
    st.progress(30, text="Distance from rivers: 30%")
    st.progress(25, text="Distance from residential: 25%")
    st.progress(20, text="Slope: 20%")
    st.progress(15, text="Road accessibility: 15%")
    st.progress(10, text="Land cover: 10%")
    st.markdown("##### Classification")
    n_classes = st.slider("Number of classes", min_value=2, max_value=10, value=5, step=1)
    run = st.button(f"{material('play_arrow')} Run Suitability Analysis", width='stretch', type="primary")

if run:
    st.session_state.pop("landfill_result", None)
    st.session_state.pop("landfill_error", None)
    with st.spinner(f"Running suitability analysis for {district}…"):
        try:
            result = compute_landfill_suitability(
                district, **_landfill_reverse_kwargs(), n_classes=n_classes
            )
            st.session_state["landfill_result"] = result
        except Exception as e:
            st.session_state["landfill_error"] = str(e)

if "landfill_error" in st.session_state:
    st.error(f"GEE computation failed: {st.session_state['landfill_error']}")
    st.caption("Fix the issue above, then click **Run Suitability Analysis** again.")
elif "landfill_result" in st.session_state:
    result = st.session_state["landfill_result"]

    tab_directions, tab_map, tab_stats, tab_classify, tab_report = st.tabs(
        [":material/refresh: Factor Directions", ":material/map: Map", ":material/bar_chart: Statistics", ":material/category: Classify A–F", ":material/description: Report"]
    )

    with tab_directions:
        st.subheader("Factor scoring direction")
        st.caption(
            "Each criterion below is scored 1 (worst) → 5 (best) in the direction shown. "
            "Reverse any factor to flip its scoring, then click **Recalculate** to rerun the analysis."
        )

        factor_maps = result.get("factor_maps", {})
        for key in FACTOR_ORDER:
            meta = FACTOR_META[key]
            fmap = factor_maps.get(key, {})
            reversed_now = fmap.get("reversed", st.session_state["landfill_reverse"][key])
            direction_icon = material_html("repeat") if reversed_now else material_html("arrow_forward")
            desc = fmap.get(
                "description",
                meta["reversed_desc"] if reversed_now else meta["normal_desc"],
            )

            col_icon, col_body, col_toggle = st.columns([0.6, 3.4, 1.2])
            with col_icon:
                st.markdown(
                    f"<div style='text-align:center'>{material_html(meta['icon'], size=30)}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"<div style='text-align:center'>{direction_icon}</div>", unsafe_allow_html=True)
            with col_body:
                st.markdown(f"**{meta['label']}** ({meta['weight_pct']}% weight)")
                st.caption(desc)
                if fmap.get("thumb_url"):
                    st.image(fmap["thumb_url"], width=220)
            with col_toggle:
                st.session_state["landfill_reverse"][key] = st.checkbox(
                    "Reverse",
                    value=st.session_state["landfill_reverse"][key],
                    key=f"landfill_reverse_{key}",
                )
            st.divider()

        recalc = st.button(
            ":material/refresh: Recalculate with New Directions", width='stretch', type="primary"
        )
        if recalc:
            with st.spinner(f"Recalculating suitability for {district} with updated factor directions…"):
                try:
                    result = compute_landfill_suitability(
                        district, **_landfill_reverse_kwargs(), n_classes=n_classes
                    )
                    st.session_state["landfill_result"] = result
                    st.rerun()
                except Exception as e:
                    st.error(f"GEE computation failed: {e}")

    with tab_map:
        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=result["tile_url"],
            attr="Google Earth Engine",
            name="Suitability Score",
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])
        st.markdown(
            "**Legend (score 1–5):** "
            "<span style='color:#d73027'>■</span> Not Suitable (1) &nbsp;"
            "<span style='color:#f46d43'>■</span> Low (2) &nbsp;"
            "<span style='color:#fee08b'>■</span> Moderate (3) &nbsp;"
            "<span style='color:#d9ef8b'>■</span> High (4) &nbsp;"
            "<span style='color:#1a9850'>■</span> Very High (5)",
            unsafe_allow_html=True,
        )
        if any(result.get("reverse_flags", {}).values()):
            reversed_labels = [FACTOR_META[k]["label"] for k, v in result["reverse_flags"].items() if v]
            st.warning(f":material/warning: Reversed factors applied: {', '.join(reversed_labels)}")

    with tab_stats:
        st.subheader(f"Suitability Summary — {result['district']}")
        cols = st.columns(3)
        for i, (label, val) in enumerate(result["stats"].items()):
            cols[i].metric(label, val)
        st.markdown("#### Area by Suitability Class")
        df = pd.DataFrame(
            [{"Class": k, "Area (km²)": v} for k, v in result["class_areas_km2"].items()]
        )
        fig = px.bar(
            df, x="Class", y="Area (km²)",
            color="Class",
            color_discrete_sequence=["#d73027", "#f46d43", "#fee08b", "#1a9850"],
            title=f"Landfill Suitability Classes — {result['district']}",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width='stretch')
        st.dataframe(df, width='stretch', hide_index=True)
        st.info(
            "**Note:** Highly suitable areas should be validated on the ground. "
            "Exclusion zones (protected areas, wetlands, flood plains) are not yet incorporated. "
            "Road accessibility is proxied via distance to built-up areas — replace with actual "
            "OSM/RTDA road vectors when available."
        )

    with tab_classify:
        st.subheader(f"Quantile Classification — {result['district']}")
        if "classify" in result:
            _render_panels(result["classify"], result["district"])
        else:
            st.info("Re-run analysis to generate classification panels.")

    with tab_report:
        st.subheader("Download PDF Report")
        reversed_labels = [FACTOR_META[k]["label"] for k, v in result.get("reverse_flags", {}).items() if v]
        reverse_note = (
            f" Reversed factor directions applied: {', '.join(reversed_labels)}."
            if reversed_labels else " All factors use standard scoring directions."
        )
        notes = (
            f"SMCE-AHP weights: Distance from rivers 30%, Distance from residential areas 25%, "
            f"Slope 20%, Road accessibility 15%, Land cover 10%. "
            f"SI = 0.30(RIVER) + 0.25(RESIDENTIAL) + 0.20(SLOPE) + 0.15(ROADS) + 0.10(LULC). "
            f"Rivers/water from JRC Global Surface Water + ESA WorldCover; residential & road-accessibility "
            f"proxy from ESA WorldCover built-up class; slope (%) from SRTM 30 m DEM; land cover from "
            f"ESA WorldCover 2021 (10 m). AHP consistency ratio CR = 0.016 (< 0.10, acceptable)."
            f"{reverse_note} "
            f"Highly suitable areas require ground validation and regulatory review before use."
        )
        pdf_bytes = build_report(
            module_name="Landfill Siting Suitability",
            district=result["district"],
            date_range="Current (ESA WorldCover 2021 + SRTM)",
            stats=result["stats"],
            class_areas=result["class_areas_km2"],
            extra_notes=notes,
        )
        st.download_button(
            label=":material/download: Download PDF Report",
            data=pdf_bytes,
            file_name=f"Landfill_{result['district']}.pdf",
            mime="application/pdf",
            width='stretch',
        )
else:
    st.info("Select a district and click **Run Suitability Analysis** to begin.")
