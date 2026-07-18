"""NDVI computation — no Streamlit dependency. Uses in-memory TTL cache."""
import ee
from cachetools import TTLCache
from threading import Lock
from gee.classify_utils import quantile_classify

RWANDA_DISTRICTS = [
    "Bugesera", "Burera", "Gakenke", "Gasabo", "Gatsibo",
    "Gicumbi", "Gisagara", "Huye", "Kamonyi", "Karongi",
    "Kayonza", "Kicukiro", "Kirehe", "Muhanga", "Musanze",
    "Ngoma", "Ngororero", "Nyabihu", "Nyagatare", "Nyamagabe",
    "Nyamasheke", "Nyanza", "Nyarugenge", "Nyaruguru", "Rubavu",
    "Ruhango", "Rulindo", "Rusizi", "Rutsiro", "Rwamagana",
]

_cache: TTLCache = TTLCache(maxsize=128, ttl=3600)
_lock = Lock()


def compute_ndvi(
    district_name: str,
    start_date: str,
    end_date: str,
    n_classes: int = 5,
) -> dict:
    """
    Compute NDVI median composite for a given district and date range.

    Returns a dict with tile_url, stats, class_areas_km2, classify, center,
    district, start_date, end_date.  Results are cached for 1 hour per unique
    (district, start_date, end_date, n_classes) combination.
    """
    cache_key = (district_name, start_date, end_date, n_classes)

    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        )
    )
    aoi = rwanda.geometry()

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .map(
            lambda img: img.normalizedDifference(["B8", "B4"])
            .rename("NDVI")
            .copyProperties(img, ["system:time_start"])
        )
    )

    median = s2.median().clip(aoi)

    vis_params = {
        "min": -0.2,
        "max": 0.8,
        "palette": ["#d73027", "#fc8d59", "#fee08b", "#91cf60", "#1a9850"],
    }
    map_id = median.getMapId(vis_params)

    # Stats — one batched reduceRegion call
    stats = median.reduceRegion(
        reducer=ee.Reducer.mean()
        .combine(ee.Reducer.min(), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=aoi,
        scale=100,
        maxPixels=1e9,
        tileScale=4,
    ).getInfo()

    # Class areas — one batched multi-band reduceRegion
    classes = {
        "Water / Bare (<0)": median.lt(0),
        "Very Low (0–0.2)": median.gte(0).And(median.lt(0.2)),
        "Low (0.2–0.4)": median.gte(0.2).And(median.lt(0.4)),
        "Moderate (0.4–0.6)": median.gte(0.4).And(median.lt(0.6)),
        "High (>0.6)": median.gte(0.6),
    }
    labels = list(classes.keys())
    area_img = ee.Image.cat(
        [classes[lbl].multiply(ee.Image.pixelArea()).rename(f"c{i}")
         for i, lbl in enumerate(labels)]
    )
    area_dict = area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=100, maxPixels=1e9, tileScale=4
    ).getInfo()
    class_areas = {
        lbl: round((area_dict.get(f"c{i}", 0) or 0) / 1e6, 2)
        for i, lbl in enumerate(labels)
    }

    classify = quantile_classify(
        layers=[{"name": "NDVI", "image": median, "title": "NDVI Vegetation Index"}],
        aoi=aoi,
        scale=100,
        n_classes=n_classes,
    )

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center_lon = (bounds[0][0] + bounds[2][0]) / 2
    center_lat = (bounds[0][1] + bounds[2][1]) / 2

    result = {
        "tile_url": map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean NDVI": round(stats.get("NDVI_mean") or 0, 4),
            "Min NDVI": round(stats.get("NDVI_min") or 0, 4),
            "Max NDVI": round(stats.get("NDVI_max") or 0, 4),
            "Std Dev": round(stats.get("NDVI_stdDev") or 0, 4),
        },
        "class_areas_km2": class_areas,
        "classify": classify,
        "center": [center_lat, center_lon],
        "district": district_name,
        "start_date": start_date,
        "end_date": end_date,
    }

    with _lock:
        _cache[cache_key] = result

    return result
