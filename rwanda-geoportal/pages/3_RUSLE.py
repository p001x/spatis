import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import pandas as pd
from gee_scripts.auth import initialize_gee
from gee_scripts.rusle import compute_rusle, FACTOR_VIS, _class_palette
from gee_scripts.ndvi import RWANDA_DISTRICTS
from reports.report_builder import build_rusle_report
from utils.style import apply_style, material, material_html

initialize_gee()
apply_style()

st.title(":material/rainy: RUSLE — Soil Erosion Risk")
st.markdown(
    "**Revised Universal Soil Loss Equation: A = R × K × LS × C × P** (t·ha⁻¹·yr⁻¹)  \n"
    "R: Roose (1977) · K: Williams (1995) EPIC/SoilGrids · "
    "LS: Desmet & Govers (1996) + McCool · C: van der Knijff (2000) · P: Rwanda terracing"
)

RECLASS_KEYS = ["R", "K", "LS", "C", "P"]
FACTOR_ORDER  = ["A", "R", "K", "LS", "C", "P"]

# Fixed 6-class palette for the statistics tab
PALETTE_6 = ["#1a9641", "#a6d96a", "#ffffbf", "#fdae61", "#d7191c", "#730000"]

if "rusle_reverse" not in st.session_state:
    st.session_state["rusle_reverse"] = {k: False for k in RECLASS_KEYS}


def _rusle_reverse_kwargs():
    flags = st.session_state["rusle_reverse"]
    return {
        "reverse_r":  flags["R"],
        "reverse_k":  flags["K"],
        "reverse_ls": flags["LS"],
        "reverse_c":  flags["C"],
        "reverse_p":  flags["P"],
    }


with st.sidebar:
    st.header("Analysis Controls")

    district = st.selectbox(
        "Study Area (District)",
        RWANDA_DISTRICTS,
        index=RWANDA_DISTRICTS.index("Huye"),
    )
    year = st.slider("Year", min_value=2018, max_value=2024, value=2023)

    st.markdown("---")
    st.subheader("Classification")
    n_classes = st.slider(
        "Number of classes",
        min_value=2, max_value=10, value=5,
        help=(
            "How many classes to use for the quantile-based factor reclassification. "
            "Class boundaries are computed from the data distribution inside the "
            "selected district — so each run is calibrated to that study area."
        ),
    )

    run = st.button(f"{material('play_arrow')} Calculate RUSLE", width='stretch', type="primary")

    st.markdown("---")
    st.caption(
        "**Data sources**\n"
        "- CHIRPS daily rainfall (UCSB)\n"
        "- SRTM 30 m DEM (USGS)\n"
        "- HydroSHEDS 15-arc-sec flow acc.\n"
        "- Sentinel-2 SR (Copernicus)\n"
        "- OpenLandMap clay & sand (SoilGrids)\n"
        "- FAO GAUL 2015 admin boundaries"
    )


if run:
    st.session_state.pop("rusle_result", None)
    st.session_state.pop("rusle_error", None)
    with st.spinner(f"Computing RUSLE for {district} ({year}) — 20–40 s…"):
        try:
            result = compute_rusle(
                district, year, n_classes=n_classes, **_rusle_reverse_kwargs()
            )
            st.session_state["rusle_result"] = result
        except Exception as e:
            st.session_state["rusle_error"] = str(e)

if "rusle_error" in st.session_state:
    st.error(f"GEE computation failed: {st.session_state['rusle_error']}")
    st.caption("Fix the issue above, then click **Calculate RUSLE** again.")
elif "rusle_result" in st.session_state:
    result = st.session_state["rusle_result"]

    fm       = result["factor_maps"]
    nc       = result["n_classes"]
    pal_n    = _class_palette(nc)
    pct_steps = result["percentile_steps"]

    tabs = st.tabs([
        ":material/map: Map",
        ":material/bar_chart: Statistics",
        ":material/science: Factor Breakdown",
        ":material/refresh: Classify Factors",
        ":material/folder: Factor Maps & Exports",
        ":material/description: Report",
    ])

    # ── 1. Map ─────────────────────────────────────────────────────────────────
    with tabs[0]:
        layer_key = st.selectbox(
            "Display layer",
            FACTOR_ORDER,
            format_func=lambda k: fm[k]["label"],
            key="rusle_layer",
        )
        selected = fm[layer_key]
        m = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
        folium.TileLayer(
            tiles=selected["tile_url"],
            attr="Google Earth Engine",
            name=selected["label"],
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=520, returned_objects=[])

        palette = selected["palette"]
        n = len(palette)
        vis_min, vis_max = selected["min"], selected["max"]
        step = (vis_max - vis_min) / n
        swatches = " &nbsp; ".join(
            f"<span style='background:{c};padding:2px 9px;border-radius:3px;"
            f"font-size:0.75rem;color:#111'>"
            f"{vis_min + i*step:.0f}–{vis_min + (i+1)*step:.0f}</span>"
            for i, c in enumerate(palette)
        )
        st.markdown(
            f"<div style='margin-top:4px'><b>{selected['label']}</b> "
            f"({selected['unit']}): {swatches}</div>",
            unsafe_allow_html=True,
        )

    # ── 2. Statistics ──────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader(f"Soil Loss Statistics — {result['district']} ({result['year']})")
        cols = st.columns(4)
        for i, (label, val) in enumerate(result["stats"].items()):
            cols[i].metric(label, f"{val:,.2f}")

        mean_val = result["stats"].get("Mean  (t/ha/yr)", 0)
        if mean_val > 200:
            st.error(f":material/warning: Mean erosion **{mean_val:.0f} t/ha/yr** — catastrophic (>200). Urgent intervention needed.")
        elif mean_val > 50:
            st.warning(f":material/warning: Mean erosion **{mean_val:.0f} t/ha/yr** — high risk (>50). Conservation measures required.")
        else:
            st.success(f"Mean erosion **{mean_val:.1f} t/ha/yr** — moderate to low risk.")

        st.markdown("#### Erosion Risk Class Distribution (standard 6-class)")
        df = pd.DataFrame(
            [{"Class": k, "Area (km²)": v} for k, v in result["class_areas_km2"].items()]
        )
        col_pie, col_bar = st.columns(2)
        with col_pie:
            fig = px.pie(df, names="Class", values="Area (km²)",
                         color_discrete_sequence=PALETTE_6, hole=0.35,
                         title="Area by Erosion Class")
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig, width='stretch')
        with col_bar:
            fig2 = px.bar(df, x="Area (km²)", y="Class", orientation="h",
                          color="Class", color_discrete_sequence=PALETTE_6,
                          title="Area (km²) by Class")
            fig2.update_layout(
                showlegend=False,
                yaxis=dict(categoryorder="array",
                           categoryarray=list(result["class_areas_km2"].keys())),
                margin=dict(t=40, b=0, l=0, r=0),
            )
            st.plotly_chart(fig2, width='stretch')
        st.dataframe(df, width='stretch', hide_index=True)

    # ── 3. Factor Breakdown ────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("RUSLE Factor Spatial Means")
        factor_colors = {"R": "#2196F3", "K": "#FF9800", "LS": "#9C27B0",
                         "C": "#4CAF50", "P": "#F44336"}
        fcols = st.columns(5)
        for col, key in zip(fcols, ["R", "K", "LS", "C", "P"]):
            fmeta = fm[key]
            fmean = result["factor_means"].get(
                next((k for k in result["factor_means"] if k.startswith(key)), ""), 0
            )
            c = factor_colors[key]
            col.markdown(
                f"<div style='border:1px solid {c};border-radius:8px;padding:10px;text-align:center'>"
                f"<div style='font-size:1.5rem;font-weight:bold;color:{c}'>{fmean}</div>"
                f"<div style='font-size:0.72rem;color:#888'>{fmeta['unit']}</div>"
                f"<div style='font-size:0.85rem;font-weight:600;margin-top:4px'>{key} factor</div>"
                f"</div>", unsafe_allow_html=True,
            )
            with col.expander(material("info")):
                st.caption(fmeta["description"])

        st.markdown("---")
        ref_data = {
            "Factor": ["R", "K", "LS", "C", "P"],
            "This district (mean)": [
                result["factor_means"].get(
                    next((k for k in result["factor_means"] if k.startswith(key)), ""), 0
                )
                for key in ["R", "K", "LS", "C", "P"]
            ],
            "Nyagisozi study (mean)": [981.12, 0.0347, 51.02, 0.178, 0.367],
            "Study range": ["796–1 188", "0.026–0.039", "0–295", "0.0002–0.998", "0.12–1.00"],
        }
        st.dataframe(pd.DataFrame(ref_data), width='stretch', hide_index=True)
        st.markdown(
            "> **Note:** High R×LS drives most erosion in Rwanda's highlands. "
            "Low C (dense vegetation) and low P (terracing) substantially reduce actual loss."
        )

    # ── 4. Classify Factors ─────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader(f"Quantile-based Factor Classification — {nc} classes")
        st.markdown(
            f"Each factor and the final soil loss layer (A) are independently reclassified "
            f"into **{nc} classes** using **{nc - 1} percentile breakpoints** "
            f"({', '.join(str(p) + 'th' for p in pct_steps)}) **computed from the data "
            f"within the selected district** ({result['district']}). "
            "Class 1 = lowest values, highest class = highest values. "
            "Change the **Number of classes** slider in the sidebar and recalculate to update."
        )

        # Legend swatches
        swatch_html = " &nbsp; ".join(
            f"<span style='background:{c};padding:3px 10px;border-radius:3px;"
            f"font-size:0.78rem;color:#111'>Class {i+1}</span>"
            for i, c in enumerate(pal_n)
        )
        st.markdown(
            f"<div style='margin-bottom:10px'><b>Legend:</b> {swatch_html} "
            f"(low → high within study area)</div>",
            unsafe_allow_html=True,
        )

        # ── Per-factor classification maps ────────────────────────────────────
        st.markdown("### Factor Classification Maps")
        for i in range(0, len(RECLASS_KEYS), 2):
            row_keys = RECLASS_KEYS[i: i + 2]
            row_cols = st.columns(len(row_keys))
            for col, key in zip(row_cols, row_keys):
                fmeta = fm[key]
                direction_icon = material_html("repeat" if fmeta.get("reversed") else "arrow_forward")
                bps = fmeta.get("class_breakpoints", [])
                with col:
                    st.markdown(
                        f"**{material_html(fmeta['icon'])} {fmeta['label']}** {direction_icon}  \n"
                        f"<span style='font-size:0.78rem;color:#888'>{fmeta['unit']}</span>",
                        unsafe_allow_html=True,
                    )
                    if bps:
                        bp_strs = [f"{v:.3g}" for v in bps]
                        st.caption(
                            f"Breakpoints (within {result['district']}): "
                            + " | ".join(bp_strs)
                        )
                    try:
                        st.image(fmeta["class_thumb_url"], width='stretch')
                    except Exception:
                        st.info("Thumbnail loading…")

                    col_toggle, col_reverse = st.columns([3, 2])
                    with col_toggle:
                        st.session_state["rusle_reverse"][key] = st.checkbox(
                            "Reverse class direction",
                            value=st.session_state["rusle_reverse"][key],
                            key=f"rusle_reverse_{key}",
                            help=fmeta.get("reversed_desc") if fmeta.get("reversed") else fmeta.get("normal_desc"),
                        )
                    st.markdown("---")

        # ── Soil Loss N-class map ──────────────────────────────────────────────
        st.markdown("### Soil Loss Classification Map")
        st.caption(
            f"Soil loss (A) reclassified into {nc} quantile classes within "
            f"{result['district']}. Class labels show the data-driven thresholds."
        )
        a_tile = result.get("n_class_soil_loss_tile")
        if a_tile:
            m_a = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
            folium.TileLayer(
                tiles=a_tile, attr="Google Earth Engine",
                name=f"Soil Loss — {nc} Classes", overlay=True,
            ).add_to(m_a)
            folium.LayerControl().add_to(m_a)
            st_folium(m_a, width="100%", height=420, returned_objects=[])

        df_a = pd.DataFrame(
            [{"Class": k, "Area (km²)": v}
             for k, v in result.get("n_class_soil_loss_km2", {}).items()]
        )
        if not df_a.empty:
            col_p, col_b = st.columns(2)
            with col_p:
                fig_a_pie = px.pie(
                    df_a, names="Class", values="Area (km²)",
                    color_discrete_sequence=pal_n, hole=0.35,
                    title=f"Soil Loss — {nc} classes (area)",
                )
                fig_a_pie.update_traces(textposition="inside", textinfo="percent+label")
                fig_a_pie.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
                st.plotly_chart(fig_a_pie, width='stretch')
            with col_b:
                fig_a_bar = px.bar(
                    df_a, x="Class", y="Area (km²)", color="Class",
                    color_discrete_sequence=pal_n,
                    title=f"Area (km²) by Quantile Class",
                )
                fig_a_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_a_bar, width='stretch')
            st.dataframe(df_a, width='stretch', hide_index=True)

        # ── Composite Risk Index ───────────────────────────────────────────────
        recalc = st.button(
            ":material/refresh: Recalculate with New Class Directions", width='stretch', type="primary"
        )
        if recalc:
            with st.spinner(f"Recalculating for {district} ({year})…"):
                try:
                    result = compute_rusle(
                        district, year, n_classes=nc, **_rusle_reverse_kwargs()
                    )
                    st.session_state["rusle_result"] = result
                    st.rerun()
                except Exception as e:
                    st.error(f"GEE computation failed: {e}")

        risk = result.get("risk_index")
        if risk:
            st.markdown("---")
            st.markdown(f"#### Composite Risk Index ({nc} classes, equal-weighted)")
            m2 = folium.Map(location=result["center"], zoom_start=10, tiles="CartoDB positron")
            folium.TileLayer(
                tiles=risk["tile_url"],
                attr="Google Earth Engine",
                name="Composite Risk Index",
                overlay=True,
            ).add_to(m2)
            folium.LayerControl().add_to(m2)
            st_folium(m2, width="100%", height=400, returned_objects=[])

            c1, c2 = st.columns(2)
            c1.metric("Mean Risk Index", risk["mean"])
            c2.metric("Std Dev", risk["std_dev"])

            df_risk = pd.DataFrame(
                [{"Class": k, "Area (km²)": v} for k, v in risk["class_areas_km2"].items()]
            )
            fig_risk = px.bar(
                df_risk, x="Class", y="Area (km²)", color="Class",
                color_discrete_sequence=pal_n,
                title=f"Composite Risk Index Classes — {result['district']}",
            )
            fig_risk.update_layout(showlegend=False)
            st.plotly_chart(fig_risk, width='stretch')

            reversed_labels = [k for k, v in result.get("reverse_flags", {}).items() if v]
            if reversed_labels:
                st.warning(f":material/warning: Reversed factors: {', '.join(reversed_labels)}")

    # ── 5. Factor Maps & Exports ───────────────────────────────────────────────
    with tabs[4]:
        st.subheader("Individual Factor Maps & Downloads")
        st.markdown(
            "Each factor is computed as a spatially explicit raster clipped to the selected district. "
            "**Thumbnail** shows the spatial pattern. "
            "**GeoTIFF** downloads a ZIP at 100 m resolution. "
            "**PNG** downloads the map image at 512 px."
        )
        for i in range(0, len(FACTOR_ORDER), 2):
            row_keys = FACTOR_ORDER[i: i + 2]
            row_cols = st.columns(len(row_keys))
            for col, key in zip(row_cols, row_keys):
                fmeta = fm[key]
                with col:
                    st.markdown(f"#### {fmeta['label']}")
                    st.caption(f"{fmeta['description']}  \nUnit: **{fmeta['unit']}**")
                    try:
                        st.image(fmeta["thumb_url"], width='stretch')
                    except Exception:
                        st.info("Thumbnail loading…")
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        st.markdown(
                            f"<a href='{fmeta['download_url']}' target='_blank' "
                            f"style='display:block;text-align:center;padding:6px;border-radius:4px;"
                            f"background:#0e4c96;color:white;text-decoration:none;font-size:0.82rem'>"
                            f"{material_html('download')} GeoTIFF (ZIP)</a>",
                            unsafe_allow_html=True,
                        )
                    with btn_col2:
                        st.markdown(
                            f"<a href='{fmeta['thumb_url']}' target='_blank' "
                            f"style='display:block;text-align:center;padding:6px;border-radius:4px;"
                            f"background:#1a7a4a;color:white;text-decoration:none;font-size:0.82rem'>"
                            f"{material_html('image')} PNG Map</a>",
                            unsafe_allow_html=True,
                        )
                    st.markdown("---")

    # ── 6. Report ──────────────────────────────────────────────────────────────
    with tabs[5]:
        st.subheader("Download PDF Report")
        st.markdown(
            "The report includes: metadata, key statistics, erosion class table, "
            "methodology notes, the **final soil loss map**, and **all 5 factor maps**."
        )
        fmeans = result["factor_means"]

        def _fmean(key):
            return fmeans.get(next((k for k in fmeans if k.startswith(key)), ""), 0)

        notes = (
            f"RUSLE methodology — "
            f"R = Roose (1977) R=38.5+0.35×P from CHIRPS (mean {_fmean('R'):.0f} MJ·mm·ha⁻¹·h⁻¹·yr⁻¹); "
            f"K = Williams (1995) EPIC from OpenLandMap SoilGrids clay/sand (mean {_fmean('K'):.4f}); "
            f"LS = Desmet & Govers (1996) + McCool S via HydroSHEDS + SRTM (mean {_fmean('LS'):.2f}); "
            f"C = van der Knijff (2000) NDVI-exponential from Sentinel-2 SR (mean {_fmean('C'):.3f}); "
            f"P = slope-based Rwanda terracing classification (mean {_fmean('P'):.3f}). "
            f"Classification: quantile-based, {nc} classes within {result['district']} district extent. "
            f"Tolerable soil loss threshold: 10–12 t/ha/yr (FAO)."
        )

        if st.button(":material/description: Generate PDF Report", type="primary", width='stretch'):
            with st.spinner("Downloading factor map images and building PDF…"):
                try:
                    pdf_bytes = build_rusle_report(
                        district=result["district"],
                        year=result["year"],
                        stats=result["stats"],
                        class_areas=result["class_areas_km2"],
                        factor_maps=result["factor_maps"],
                        factor_means=result["factor_means"],
                        extra_notes=notes,
                    )
                    st.download_button(
                        label=":material/download: Download PDF",
                        data=pdf_bytes,
                        file_name=f"RUSLE_{result['district']}_{result['year']}.pdf",
                        mime="application/pdf",
                        width='stretch',
                    )
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")

else:
    st.info("Select a district and year, then click **Calculate RUSLE** to begin.")
    st.markdown(
        """
        ### RUSLE factor overview

        | Factor | Variable | Formula / Source |
        |--------|----------|-----------------|
        | **R** | Rainfall Erosivity | `R = 38.5 + 0.35 × P` — Roose (1977), CHIRPS |
        | **K** | Soil Erodibility | Williams (1995) EPIC — OpenLandMap clay & sand |
        | **LS** | Slope Length & Steepness | HydroSHEDS 15-arc-sec + SRTM (McCool/Desmet) |
        | **C** | Cover Management | `exp(−2 × NDVI / (1−NDVI))` — Sentinel-2 SR |
        | **P** | Support Practice | Slope-based Rwanda terracing (0.10 – 1.00) |

        ### Classification approach
        Class breakpoints are computed from the **data distribution within the
        selected district** (quantile / percentile method) — not global fixed thresholds.
        This means boundaries automatically adapt to each study area. Choose 2–10 classes
        from the sidebar slider.

        **Standard 6-class fixed breakpoints (Statistics tab):**
        Very Low <10 · Low 10–30 · Moderate 30–50 · High 50–100 · Very High 100–200 · Extreme >200 t/ha/yr

        **Exports available after computation:** interactive map per factor · GeoTIFF download · PNG map · PDF report.
        """
    )
