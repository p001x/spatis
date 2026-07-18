import ee
import streamlit as st
from gee_scripts.classify_utils import quantile_classify


@st.cache_data(ttl=86400, show_spinner=False)
def compute_slope(district_name: str, n_classes: int = 5):
    """
    Compute slope, aspect, and hillshade from SRTM DEM.
    Returns tile URLs and class area statistics.
    """
    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        )
    )
    aoi = rwanda.geometry()

    dem = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(aoi)
    terrain = ee.Terrain.products(dem)
    slope = terrain.select("slope").clip(aoi)
    aspect = terrain.select("aspect").clip(aoi)
    hillshade = terrain.select("hillshade").clip(aoi)

    slope_vis = {
        "min": 0,
        "max": 45,
        "palette": ["#2166ac", "#92c5de", "#f7f7f7", "#f4a582", "#d6604d", "#b2182b"],
    }
    hillshade_vis = {"min": 0, "max": 255, "palette": ["#000000", "#ffffff"]}
    aspect_vis = {
        "min": 0,
        "max": 360,
        "palette": ["#d53e4f", "#fc8d59", "#fee08b", "#e6f598", "#99d594", "#3288bd", "#d53e4f"],
    }

    slope_map_id = slope.getMapId(slope_vis)
    hillshade_map_id = hillshade.getMapId(hillshade_vis)
    aspect_map_id = aspect.getMapId(aspect_vis)

    # Slope + elevation stats batched into a single reduceRegion call (was 2 calls).
    combined_stats_img = slope.rename("slope").addBands(dem.rename("elevation"))
    combined_stats = combined_stats_img.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            ee.Reducer.max(), sharedInputs=True
        ).combine(
            ee.Reducer.percentile([25, 75]), sharedInputs=True
        ).combine(
            ee.Reducer.min(), sharedInputs=True
        ),
        geometry=aoi,
        scale=30,
        maxPixels=1e9,
        tileScale=4,
    ).getInfo()
    stats = combined_stats
    elev_stats = combined_stats

    classes = {
        "Flat (0–5°)": slope.lt(5),
        "Gentle (5–15°)": slope.gte(5).And(slope.lt(15)),
        "Moderate (15–25°)": slope.gte(15).And(slope.lt(25)),
        "Steep (25–35°)": slope.gte(25).And(slope.lt(35)),
        "Very Steep (>35°)": slope.gte(35),
    }
    # Single batched reduceRegion for all class areas instead of one call per class.
    labels = list(classes.keys())
    area_img = ee.Image.cat(
        [classes[label].multiply(ee.Image.pixelArea()).rename(f"c{i}") for i, label in enumerate(labels)]
    )
    area_dict = area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=30, maxPixels=1e9, tileScale=4
    ).getInfo()
    class_areas = {
        label: round((area_dict.get(f"c{i}", 0) or 0) / 1e6, 2) for i, label in enumerate(labels)
    }

    classify = quantile_classify(
        layers=[
            {"name": "slope",     "image": slope,  "title": "Slope (°)"},
            {"name": "elevation", "image": dem,     "title": "Elevation (m)"},
            {"name": "aspect",    "image": aspect,  "title": "Aspect (°)"},
        ],
        aoi=aoi,
        scale=30,
        n_classes=n_classes,
    )

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center_lon = (bounds[0][0] + bounds[2][0]) / 2
    center_lat = (bounds[0][1] + bounds[2][1]) / 2

    return {
        "slope_tile_url":     slope_map_id["tile_fetcher"].url_format,
        "hillshade_tile_url": hillshade_map_id["tile_fetcher"].url_format,
        "aspect_tile_url":    aspect_map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean Slope (°)":    round(stats.get("slope_mean") or 0, 2),
            "Max Slope (°)":     round(stats.get("slope_max") or 0, 2),
            "P25 Slope (°)":     round(stats.get("slope_p25") or 0, 2),
            "P75 Slope (°)":     round(stats.get("slope_p75") or 0, 2),
            "Mean Elevation (m)": round(elev_stats.get("elevation_mean") or 0, 0),
            "Min Elevation (m)":  round(elev_stats.get("elevation_min") or 0, 0),
            "Max Elevation (m)":  round(elev_stats.get("elevation_max") or 0, 0),
        },
        "class_areas_km2": class_areas,
        "classify": classify,
        "center": [center_lat, center_lon],
        "district": district_name,
    }
