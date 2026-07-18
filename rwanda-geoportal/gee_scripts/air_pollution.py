from datetime import date as _date

import ee
import streamlit as st
from gee_scripts.classify_utils import quantile_classify


WHO_NO2_ANNUAL_THRESHOLD = 10.0


def _month_range(start_date: str, end_date: str):
    """List of (year, month) tuples spanning start_date..end_date inclusive."""
    start = _date.fromisoformat(start_date)
    end = _date.fromisoformat(end_date)
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


@st.cache_data(ttl=3600, show_spinner=False)
def compute_no2(district_name: str, start_date: str, end_date: str, n_classes: int = 5):
    """
    Compute Sentinel-5P NO2 tropospheric column (mol/m²) monthly composite.
    Returns tile URL, stats vs. WHO threshold, and time-series data.

    Uses the OFFL (offline, reprocessed) L3_NO2 product rather than NRTI
    (near-real-time) — OFFL has far more complete historical coverage, which
    avoids empty-composite months. Any month/period with zero qualifying
    images degrades gracefully to null/0 instead of raising a GEE
    'Dictionary does not contain key' error.
    """
    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        )
    )
    aoi = rwanda.geometry()

    def _to_umol(img):
        # multiply()/rename() strip image properties (incl. system:time_start),
        # which would silently break any later .filterDate() on this collection
        # (e.g. the per-month split below) — copy them back explicitly.
        return img.multiply(1e6).rename("NO2_umol_m2").copyProperties(
            img, ["system:time_start", "system:time_end"]
        )

    s5p = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .select("tropospheric_NO2_column_number_density")
        .map(_to_umol)
    )

    collection_size = s5p.size().getInfo()
    if collection_size == 0:
        raise ValueError(
            f"No Sentinel-5P NO2 imagery is available for {district_name} between "
            f"{start_date} and {end_date}. Sentinel-5P data only exists from "
            f"~2018-07 onward — try a later date range."
        )

    composite = s5p.median().clip(aoi)

    vis_params = {
        "min": 0,
        "max": 200,
        "palette": ["#000080", "#0000ff", "#00ffff", "#ffff00", "#ff0000"],
    }
    map_id = composite.getMapId(vis_params)

    stats = composite.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            ee.Reducer.max(), sharedInputs=True
        ).combine(
            ee.Reducer.percentile([90]), sharedInputs=True
        ),
        geometry=aoi,
        scale=3500,
        maxPixels=1e9,
        tileScale=4,
    ).getInfo()

    # Batch every month's per-pixel mean image into ONE multi-band image and do a
    # single reduceRegion call, instead of one reduceRegion round-trip per month
    # (previously up to 12+ sequential server calls — the single biggest source
    # of latency in this module). Also fixes multi-year ranges: the old code
    # only varied `month` (1-12) against a single year, so e.g. Jan 2023 -
    # Feb 2024 would wrongly reduce all months against the start year.
    months = _month_range(start_date, end_date)
    month_images = []
    for i, (y, m) in enumerate(months):
        band = f"m{i}"
        start_m = ee.Date.fromYMD(y, m, 1)
        end_m = start_m.advance(1, "month")
        month_collection = s5p.filterDate(start_m, end_m)
        img = ee.Image(
            ee.Algorithms.If(
                month_collection.size().gt(0),
                month_collection.mean().rename(band),
                ee.Image.constant(0).rename(band).updateMask(ee.Image.constant(0)),
            )
        )
        month_images.append(img)

    monthly_img = ee.Image.cat(month_images)
    monthly_dict = monthly_img.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=aoi, scale=3500, maxPixels=1e9, tileScale=4
    ).getInfo()
    time_series = [
        {
            "month": m,
            "year": y,
            "NO2 (µmol/m²)": round(monthly_dict.get(f"m{i}") or 0, 2),
        }
        for i, (y, m) in enumerate(months)
    ]

    classify = quantile_classify(
        layers=[{"name": "NO2_umol_m2", "image": composite, "title": "NO₂ Column (µmol/m²)"}],
        aoi=aoi,
        scale=3500,
        n_classes=n_classes,
    )

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center_lon = (bounds[0][0] + bounds[2][0]) / 2
    center_lat = (bounds[0][1] + bounds[2][1]) / 2

    mean_no2 = round(stats.get("NO2_umol_m2_mean") or 0, 2)
    exceeds_who = mean_no2 > WHO_NO2_ANNUAL_THRESHOLD

    return {
        "tile_url": map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean NO2 (µmol/m²)": mean_no2,
            "Max NO2 (µmol/m²)":  round(stats.get("NO2_umol_m2_max") or 0, 2),
            "P90 NO2 (µmol/m²)":  round(stats.get("NO2_umol_m2_p90") or 0, 2),
            "WHO Threshold (µmol/m²)": WHO_NO2_ANNUAL_THRESHOLD,
        },
        "exceeds_who": exceeds_who,
        "time_series": time_series,
        "classify": classify,
        "center": [center_lat, center_lon],
        "district": district_name,
        "start_date": start_date,
        "end_date": end_date,
    }
