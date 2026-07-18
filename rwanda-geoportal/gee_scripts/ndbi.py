import ee
import streamlit as st
from gee_scripts.classify_utils import quantile_classify


def ndbi_image_and_aoi(district_name: str, start_date: str, end_date: str):
    """
    Build the median NDBI (Normalized Difference Built-up Index) image and the
    district AOI geometry, without caching. NDBI = (SWIR1 - NIR) / (SWIR1 + NIR),
    a widely used proxy for impervious/built-up surface extent. Shared by
    compute_ndbi() and by uhi.py for the LST-vs-NDBI bivariate analysis.
    """
    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        )
    )
    aoi = rwanda.geometry()

    def apply_scale_factors(image):
        optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
        return image.addBands(optical, None, True)

    def compute_ndbi_image(image):
        ndbi = image.normalizedDifference(["SR_B6", "SR_B5"]).rename("NDBI")
        return ndbi.copyProperties(image, ["system:time_start"])

    collection = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUD_COVER", 20))
        .map(apply_scale_factors)
        .map(compute_ndbi_image)
    )

    ndbi_median = collection.median().clip(aoi)
    return ndbi_median, aoi


@st.cache_data(ttl=3600, show_spinner=False)
def compute_ndbi(district_name: str, start_date: str, end_date: str, n_classes: int = 5):
    """
    Compute NDBI (impervious/built-up surface proxy) for a district and date range.
    Returns tile URL, stats, and class area breakdown — same shape as compute_lst().
    """
    ndbi_median, aoi = ndbi_image_and_aoi(district_name, start_date, end_date)

    vis_params = {
        "min": -0.3,
        "max": 0.3,
        "palette": ["#1a9850", "#d9ef8b", "#fee08b", "#f46d43", "#a50026"],
    }
    map_id = ndbi_median.getMapId(vis_params)

    stats = ndbi_median.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            ee.Reducer.min(), sharedInputs=True
        ).combine(
            ee.Reducer.max(), sharedInputs=True
        ).combine(
            ee.Reducer.stdDev(), sharedInputs=True
        ),
        geometry=aoi,
        scale=100,
        maxPixels=1e9,
        tileScale=4,
    ).getInfo()

    classes = {
        "Water / Vegetation (<-0.1)": ndbi_median.lt(-0.1),
        "Vegetated (-0.1–0)": ndbi_median.gte(-0.1).And(ndbi_median.lt(0)),
        "Mixed (0–0.1)": ndbi_median.gte(0).And(ndbi_median.lt(0.1)),
        "Built-up (0.1–0.2)": ndbi_median.gte(0.1).And(ndbi_median.lt(0.2)),
        "Dense Built-up (>0.2)": ndbi_median.gte(0.2),
    }
    labels = list(classes.keys())
    area_img = ee.Image.cat(
        [classes[label].multiply(ee.Image.pixelArea()).rename(f"c{i}") for i, label in enumerate(labels)]
    )
    area_dict = area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=100, maxPixels=1e9, tileScale=4
    ).getInfo()
    class_areas = {
        label: round((area_dict.get(f"c{i}", 0) or 0) / 1e6, 2) for i, label in enumerate(labels)
    }

    classify = quantile_classify(
        layers=[{"name": "NDBI", "image": ndbi_median, "title": "Impervious Surface Index (NDBI)"}],
        aoi=aoi,
        scale=100,
        n_classes=n_classes,
    )

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center_lon = (bounds[0][0] + bounds[2][0]) / 2
    center_lat = (bounds[0][1] + bounds[2][1]) / 2

    return {
        "tile_url": map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean NDBI": round(stats.get("NDBI_mean") or 0, 4),
            "Min NDBI": round(stats.get("NDBI_min") or 0, 4),
            "Max NDBI": round(stats.get("NDBI_max") or 0, 4),
            "Std Dev": round(stats.get("NDBI_stdDev") or 0, 4),
        },
        "class_areas_km2": class_areas,
        "classify": classify,
        "center": [center_lat, center_lon],
        "district": district_name,
        "start_date": start_date,
        "end_date": end_date,
    }
