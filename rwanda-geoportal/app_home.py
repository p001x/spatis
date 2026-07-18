import streamlit as st
from gee_scripts.auth import initialize_gee
from utils.style import apply_style

initialize_gee()
apply_style()

st.markdown(
    """
    <div class="gp-hero">
        <div class="gp-eyebrow">Google Earth Engine · Rwanda</div>
        <h1>GEOPORTAL ANALYSIS</h1>
        <p>
            An interactive platform for satellite-based environmental analysis —
            vegetation, temperature, erosion, terrain, air quality, and hazard
            risk across Rwanda's 30 districts. Choose a module from the sidebar
            to begin.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

modules = [
    {
        "icon": "eco",
        "title": "NDVI",
        "desc": "Vegetation health mapping from Sentinel-2 — cloud-masked "
                "composites, change detection, and vegetation class maps.",
    },
    {
        "icon": "device_thermostat",
        "title": "Land Surface Temperature",
        "desc": "LST in °C from Landsat 9 via the mono-window algorithm — "
                "hot/cool zone mapping and heat analysis.",
    },
    {
        "icon": "rainy",
        "title": "RUSLE Soil Erosion",
        "desc": "Soil loss (t/ha/yr) using the Revised Universal Soil Loss "
                "Equation — identifies high-erosion risk zones.",
    },
    {
        "icon": "terrain",
        "title": "Slope & Terrain",
        "desc": "Slope, aspect, and hillshade from SRTM DEM — terrain "
                "classification and elevation statistics.",
    },
    {
        "icon": "delete",
        "title": "Landfill Siting",
        "desc": "AHP-weighted multi-criteria suitability — combines slope, "
                "land cover, and distance from water, roads, settlements.",
    },
    {
        "icon": "air",
        "title": "Air Pollution (NO₂)",
        "desc": "Sentinel-5P NO₂ tropospheric column — monthly composites, "
                "hotspots, and comparison against WHO thresholds.",
    },
    {
        "icon": "landslide",
        "title": "Landslide Susceptibility",
        "desc": "AHP-weighted overlay of 7 conditioning factors → LSI map "
                "with Very Low–Very High risk classes.",
    },
    {
        "icon": "location_city",
        "title": "Urban Heat Island",
        "desc": "LST vs. impervious surface comparison to reveal urban "
                "heat concentration.",
    },
]

st.markdown('<div class="gp-section-title">Analysis Modules</div>', unsafe_allow_html=True)

cols = st.columns(4)
for i, m in enumerate(modules):
    with cols[i % 4]:
        st.markdown(
            f"""
            <div class="gp-card">
                <div class="gp-card-icon">
                    <span class="material-symbols-outlined">{m['icon']}</span>
                </div>
                <h4>{m['title']}</h4>
                <p>{m['desc']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:0.9rem'></div>", unsafe_allow_html=True)

st.markdown('<div class="gp-section-title">Data Sources</div>', unsafe_allow_html=True)
st.caption(
    "Google Earth Engine · Sentinel-2 · Sentinel-5P · Landsat 9 · SRTM DEM · CHIRPS · "
    "ESA WorldCover · iSDA Africa · HydroSHEDS · GRIP4 · FAO GAUL 2015 admin boundaries"
)
