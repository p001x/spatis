import streamlit as st
from utils.style import apply_style

st.set_page_config(
    page_title="GEOPORTAL ANALYSIS",
    page_icon=":material/public:",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_style()

home_page = st.Page("app_home.py", title="Overview", icon=":material/space_dashboard:", default=True)

project_pages = [
    st.Page("pages/1_NDVI.py", title="NDVI", icon=":material/eco:"),
    st.Page("pages/2_LST.py", title="LST", icon=":material/device_thermostat:"),
    st.Page("pages/3_RUSLE.py", title="RUSLE", icon=":material/rainy:"),
    st.Page("pages/4_Slope.py", title="Slope", icon=":material/terrain:"),
    st.Page("pages/5_Landfill.py", title="Landfill", icon=":material/delete:"),
    st.Page("pages/6_AirPollution.py", title="AirPollution", icon=":material/air:"),
    st.Page("pages/7_Landslide.py", title="Landslide", icon=":material/landslide:"),
    st.Page("pages/9_UHI.py", title="UHI", icon=":material/location_city:"),
    st.Page("pages/10_Sample_Digitization.py", title="Sample Digitization", icon=":material/draw:"),
]

rare_data_pages = [
    st.Page("pages/8_RARE_DATA.py", title="RARE DATA", icon=":material/database:"),
]

nav = st.navigation({
    "": [home_page],
    "PROJECT": project_pages,
    "RARE DATA": rare_data_pages,
})

nav.run()
