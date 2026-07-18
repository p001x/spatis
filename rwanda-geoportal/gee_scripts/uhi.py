"""
Urban Heat Island analysis: LST vs NDBI (impervious surface) bivariate relationship.

Mirrors the classic "LST vs Impervious Surface" workflow (Landsat 9 → LST + NDBI →
per-zone zonal means → bivariate classification → OLS regression → composite map),
but since this app has no sector-level shapefile, zones are a regular grid over the
district AOI, clipped to the boundary, instead of administrative sectors. Grid cells
with no valid pixels (e.g. outside the true boundary within a bounding grid cell) are
kept and flagged as "no data" — same treatment as sectors lacking data in the source
workflow.
"""
from __future__ import annotations

import io

import ee
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as scipy_stats
from shapely.geometry import shape as shapely_shape

from gee_scripts.lst import lst_image_and_aoi
from gee_scripts.ndbi import ndbi_image_and_aoi

BIVAR_COLORS = {
    ("Low", "Low"): "#e8e8e8", ("Low", "Mid"): "#ace4e4", ("Low", "High"): "#5ac8c8",
    ("Mid", "Low"): "#dfb0d6", ("Mid", "Mid"): "#a5add3", ("Mid", "High"): "#5698b9",
    ("High", "Low"): "#be64ac", ("High", "Mid"): "#8c62aa", ("High", "High"): "#3b4994",
}
NO_DATA_COLOR = "#d0d0d0"


def _grid_cells(aoi, grid_size: int) -> ee.FeatureCollection:
    """Split aoi's bounding box into grid_size x grid_size rectangles, clipped to aoi."""
    bounds = aoi.bounds().getInfo()["coordinates"][0]
    lon_min, lat_min = bounds[0]
    lon_max, lat_max = bounds[2]
    dx = (lon_max - lon_min) / grid_size
    dy = (lat_max - lat_min) / grid_size

    features = []
    cell_id = 0
    for i in range(grid_size):
        for j in range(grid_size):
            rect = ee.Geometry.Rectangle([
                lon_min + i * dx, lat_min + j * dy,
                lon_min + (i + 1) * dx, lat_min + (j + 1) * dy,
            ])
            clipped = rect.intersection(aoi, ee.ErrorMargin(1))
            features.append(ee.Feature(clipped, {"grid_id": cell_id}))
            cell_id += 1
    return ee.FeatureCollection(features)


@st.cache_data(ttl=3600, show_spinner=False)
def compute_uhi(district_name: str, start_date: str, end_date: str, grid_size: int = 6):
    """
    Compute the LST-vs-NDBI Urban Heat Island bivariate analysis for a district.

    Returns tile/thumb URLs for both layers, per-grid-cell zonal means, bivariate
    classification, OLS regression statistics, and rendered PNG figures (bivariate
    grid map + regression scatter) as raw bytes for direct embedding in the UI/report.
    """
    grid_size = max(3, min(grid_size, 12))

    lst_median, aoi = lst_image_and_aoi(district_name, start_date, end_date)
    ndbi_median, _ = ndbi_image_and_aoi(district_name, start_date, end_date)

    lst_pct = lst_median.reduceRegion(
        reducer=ee.Reducer.percentile([2, 98]), geometry=aoi, scale=100, maxPixels=1e9, tileScale=4, bestEffort=True,
    ).getInfo()
    ndbi_pct = ndbi_median.reduceRegion(
        reducer=ee.Reducer.percentile([2, 98]), geometry=aoi, scale=100, maxPixels=1e9, tileScale=4, bestEffort=True,
    ).getInfo()

    lst_vis = {"min": lst_pct.get("LST_p2", 15), "max": lst_pct.get("LST_p98", 40),
               "palette": ["#313695", "#74add1", "#fee090", "#f46d43", "#a50026"]}
    ndbi_vis = {"min": ndbi_pct.get("NDBI_p2", -0.3), "max": ndbi_pct.get("NDBI_p98", 0.3),
                "palette": ["#1a9850", "#d9ef8b", "#fee08b", "#f46d43", "#a50026"]}

    lst_map_id = lst_median.getMapId(lst_vis)
    ndbi_map_id = ndbi_median.getMapId(ndbi_vis)
    lst_thumb = lst_median.getThumbURL({**lst_vis, "region": aoi, "dimensions": 640, "format": "png"})
    ndbi_thumb = ndbi_median.getThumbURL({**ndbi_vis, "region": aoi, "dimensions": 640, "format": "png"})

    # ── Grid zonal stats: one reduceRegions call for both bands at once ────────
    grid_fc = _grid_cells(aoi, grid_size)
    combined = lst_median.rename("LST").addBands(ndbi_median.rename("NDBI"))
    stats_fc = combined.reduceRegions(collection=grid_fc, reducer=ee.Reducer.mean(), scale=100)
    features = stats_fc.getInfo()["features"]

    rows = []
    for f in features:
        props = f["properties"]
        geom = f.get("geometry")
        rows.append({
            "grid_id": props.get("grid_id"),
            "LST": props.get("LST"),
            "NDBI": props.get("NDBI"),
            "geometry": shapely_shape(geom) if geom and geom.get("coordinates") else None,
        })
    df = pd.DataFrame(rows)
    df = df[df["geometry"].apply(lambda g: g is not None and not g.is_empty)]

    has_data = df.dropna(subset=["LST", "NDBI"]).copy()
    no_data = df[df["LST"].isna() | df["NDBI"].isna()].copy()

    regression = None
    bivar_png = b""
    scatter_png = b""

    if len(has_data) >= 4:
        # Quantile tertiles (Low/Mid/High) per axis — falls back gracefully with few unique values.
        try:
            has_data["LST_class"] = pd.qcut(has_data["LST"], q=3, labels=["Low", "Mid", "High"], duplicates="drop")
            has_data["NDBI_class"] = pd.qcut(has_data["NDBI"], q=3, labels=["Low", "Mid", "High"], duplicates="drop")
        except ValueError:
            has_data["LST_class"] = "Mid"
            has_data["NDBI_class"] = "Mid"
        has_data["bivar_color"] = has_data.apply(
            lambda r: BIVAR_COLORS.get((str(r["LST_class"]), str(r["NDBI_class"])), "#cccccc"), axis=1
        )

        slope, intercept, r, p, _ = scipy_stats.linregress(has_data["NDBI"], has_data["LST"])
        n = len(has_data)
        regression = {
            "slope": round(float(slope), 4), "intercept": round(float(intercept), 4),
            "r2": round(float(r) ** 2, 4), "p_value": float(p), "n": int(n),
        }

        bivar_png = _render_bivariate_map(has_data, no_data, aoi, district_name)
        scatter_png = _render_scatter(has_data, slope, intercept, r, p, n)

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center = [(bounds[0][1] + bounds[2][1]) / 2, (bounds[0][0] + bounds[2][0]) / 2]

    return {
        "district": district_name,
        "start_date": start_date,
        "end_date": end_date,
        "grid_size": grid_size,
        "center": center,
        "lst_tile_url": lst_map_id["tile_fetcher"].url_format,
        "ndbi_tile_url": ndbi_map_id["tile_fetcher"].url_format,
        "lst_thumb_url": lst_thumb,
        "ndbi_thumb_url": ndbi_thumb,
        "lst_stats": {
            "Mean (°C)": round(has_data["LST"].mean(), 2) if len(has_data) else None,
            "Min (°C)": round(has_data["LST"].min(), 2) if len(has_data) else None,
            "Max (°C)": round(has_data["LST"].max(), 2) if len(has_data) else None,
        },
        "ndbi_stats": {
            "Mean": round(has_data["NDBI"].mean(), 4) if len(has_data) else None,
            "Min": round(has_data["NDBI"].min(), 4) if len(has_data) else None,
            "Max": round(has_data["NDBI"].max(), 4) if len(has_data) else None,
        },
        "n_cells_total": int(len(df)),
        "n_cells_with_data": int(len(has_data)),
        "n_cells_no_data": int(len(no_data)),
        "regression": regression,
        "bivariate_png": bivar_png,
        "scatter_png": scatter_png,
        "grid_table": has_data[["grid_id", "LST", "NDBI"]].round(3).to_dict("records") if len(has_data) else [],
    }


def _render_bivariate_map(has_data: pd.DataFrame, no_data: pd.DataFrame, aoi, district_name: str) -> bytes:
    import geopandas as gpd

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_facecolor("#cce6ff")

    if len(has_data):
        gdf = gpd.GeoDataFrame(has_data, geometry="geometry", crs="EPSG:4326")
        gdf.plot(ax=ax, color=gdf["bivar_color"], edgecolor="white", linewidth=0.6)
    if len(no_data):
        gdf_nd = gpd.GeoDataFrame(no_data, geometry="geometry", crs="EPSG:4326")
        gdf_nd.plot(ax=ax, color=NO_DATA_COLOR, edgecolor="#999999", linewidth=0.4, hatch="///")

    ax.set_title(f"Bivariate: LST × NDBI (UHI Hotspots)\n{district_name} — Zonal Mean per Grid Cell",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("Longitude", fontsize=8)
    ax.set_ylabel("Latitude", fontsize=8)
    ax.tick_params(labelsize=7)

    legend_ax = ax.inset_axes([0.01, 0.01, 0.27, 0.27])
    legend_ax.set_xlim(0, 3)
    legend_ax.set_ylim(0, 3)
    for i, ll in enumerate(["Low", "Mid", "High"]):
        for j, nl in enumerate(["Low", "Mid", "High"]):
            legend_ax.add_patch(mpatches.Rectangle((j, i), 1, 1, color=BIVAR_COLORS[(ll, nl)], ec="white", lw=0.5))
    legend_ax.set_xticks([0.5, 1.5, 2.5]); legend_ax.set_xticklabels(["Lo", "Mi", "Hi"], fontsize=5.5)
    legend_ax.set_yticks([0.5, 1.5, 2.5]); legend_ax.set_yticklabels(["Lo", "Mi", "Hi"], fontsize=5.5)
    legend_ax.set_xlabel("NDBI →", fontsize=5.5, labelpad=1)
    legend_ax.set_ylabel("LST →", fontsize=5.5, labelpad=1)
    legend_ax.tick_params(length=0)

    if len(no_data):
        ax.legend(handles=[mpatches.Patch(facecolor=NO_DATA_COLOR, edgecolor="#999999", hatch="///",
                                           label=f"No data ({len(no_data)})")],
                  loc="upper right", fontsize=6.5, framealpha=0.8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _render_scatter(df: pd.DataFrame, slope, intercept, r, p, n) -> bytes:
    x_line = np.linspace(df["NDBI"].min(), df["NDBI"].max(), 100)
    y_line = slope * x_line + intercept
    residuals = df["LST"] - (slope * df["NDBI"] + intercept)
    se_resid = np.sqrt(np.sum(residuals ** 2) / max(n - 2, 1))
    ci = 1.96 * se_resid * np.sqrt(
        1 / n + (x_line - df["NDBI"].mean()) ** 2 / max(np.sum((df["NDBI"] - df["NDBI"].mean()) ** 2), 1e-9)
    )

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df["NDBI"], df["LST"], c=df["bivar_color"], edgecolors="black", linewidths=0.6, s=90, zorder=3)
    ax.plot(x_line, y_line, color="#1a1a2e", linewidth=2, linestyle="--",
            label=f"OLS: y = {slope:.2f}x + {intercept:.2f}", zorder=4)
    ax.fill_between(x_line, y_line - ci, y_line + ci, alpha=0.15, color="#1a1a2e", label="95% CI")

    ax.text(0.04, 0.97, f"R² = {r ** 2:.4f}\nSlope = {slope:.2f}\nIntercept = {intercept:.2f}\n"
                         f"p-value = {p:.4g}\nn = {n} grid cells",
            transform=ax.transAxes, fontsize=9, verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff8e7", edgecolor="#ccaa00", alpha=0.95))
    ax.set_xlabel("Mean NDBI per grid cell", fontsize=10)
    ax.set_ylabel("Mean LST (°C)", fontsize=10)
    ax.set_title("OLS Regression: LST vs NDBI", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
