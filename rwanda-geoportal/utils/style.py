"""Shared visual styling for GEOPORTAL ANALYSIS.

Call `apply_style()` once near the top of every page (after `st.set_page_config`
in app.py, and at the top of each page script) to get a consistent,
professional look across the app.
"""

import streamlit as st

_CSS = """<style>
.material-symbols-outlined {
    font-family: 'Material Symbols Rounded';
    font-weight: normal;
    font-style: normal;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    -webkit-font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
}
:root {
    --brand-ink: #16241E;
    --brand-green: #0F6E4F;
    --brand-green-dark: #0B4F3A;
    --brand-mist: #F4F7F5;
    --brand-border: #E3E9E5;
}

/* ---- Base typography ---- */
html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background-color: var(--brand-mist);
    border-right: 1px solid var(--brand-border);
}
[data-testid="stSidebarNav"] ul { padding-top: 0.25rem; }
[data-testid="stSidebarNavLink"] {
    border-radius: 8px;
    margin: 1px 6px;
}
[data-testid="stSidebarNavLink"]:hover {
    background-color: rgba(15, 110, 79, 0.08);
}
[data-testid="stSidebarNavSectionHeader"] {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #5B6B62;
    text-transform: uppercase;
    padding-top: 0.6rem;
}

/* ---- Page titles ---- */
h1 {
    font-weight: 800 !important;
    color: var(--brand-ink) !important;
    letter-spacing: -0.02em;
}
h2, h3 { color: var(--brand-ink) !important; font-weight: 700 !important; }

/* ---- Buttons ---- */
.stButton > button, .stDownloadButton > button {
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid var(--brand-border);
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background-color: var(--brand-green);
    border-color: var(--brand-green);
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
    background-color: var(--brand-green-dark);
    border-color: var(--brand-green-dark);
}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    border-radius: 8px 8px 0 0;
}

/* ---- Metrics ---- */
[data-testid="stMetric"] {
    background: var(--brand-mist);
    border: 1px solid var(--brand-border);
    border-radius: 12px;
    padding: 14px 16px;
}

/* ---- Custom card components ---- */
.gp-hero {
    background: linear-gradient(135deg, var(--brand-green) 0%, var(--brand-green-dark) 100%);
    border-radius: 16px;
    padding: 2.6rem 2.4rem;
    color: white;
    margin-bottom: 1.6rem;
}
.gp-hero h1 { color: white !important; margin-bottom: 0.5rem; }
.gp-hero p { color: rgba(255,255,255,0.9); font-size: 1.05rem; max-width: 640px; margin: 0; }
.gp-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem;
    font-weight: 700;
    color: rgba(255,255,255,0.75);
    margin-bottom: 0.6rem;
}

.gp-card {
    background: white;
    border: 1px solid var(--brand-border);
    border-radius: 14px;
    padding: 1.3rem 1.4rem;
    height: 100%;
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}
.gp-card:hover {
    box-shadow: 0 8px 24px rgba(15, 110, 79, 0.12);
    transform: translateY(-2px);
}
.gp-card-icon {
    width: 42px;
    height: 42px;
    border-radius: 10px;
    background: rgba(15, 110, 79, 0.1);
    color: var(--brand-green);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 0.7rem;
}
.gp-card-icon .material-symbols-outlined { font-size: 24px; }
.gp-card h4 {
    margin: 0 0 0.35rem 0;
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--brand-ink);
}
.gp-card p { margin: 0; font-size: 0.88rem; color: #4A5850; line-height: 1.45; }

.gp-badge {
    display: inline-block;
    background: rgba(15, 110, 79, 0.1);
    color: var(--brand-green-dark);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 999px;
    margin-bottom: 0.4rem;
}

.gp-section-title {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #5B6B62;
    margin: 1.6rem 0 0.7rem 0;
}
</style>
"""


def apply_style() -> None:
    """Inject the shared CSS for a consistent, professional visual style."""
    st.markdown(_CSS, unsafe_allow_html=True)


def material(name: str) -> str:
    """Return the Streamlit markdown shortcode for a Material icon, e.g. ':material/eco:'."""
    return f":material/{name}:"


def material_html(name: str, size: int = 20) -> str:
    """Return a raw <span> for a Material icon, for use inside unsafe_allow_html blocks."""
    return (
        f'<span class="material-symbols-outlined" '
        f'style="font-size:{size}px;vertical-align:middle">{name}</span>'
    )
