"""Land Surface Temperature (LST) — no Streamlit dependency."""
import ee
from cachetools import TTLCache
from threading import Lock
from gee.classify_utils import quantile_classify

_cache: TTLCache = TTLCache(maxsize=128, ttl=3600)
_lock = Lock()


def lst_image_and_aoi(district_name: str, start_date: str, end_date: str):
    """Build the median LST image (°C, Landsat 9 mono-window) and the AOI geometry.
    Shared with uhi.py which needs the raw ee.Image for further composition.
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
        thermal = image.select("ST_B10").multiply(0.00341802).add(149.0)
        return image.addBands(optical, None, True).addBands(thermal, None, True)

    def compute_lst_image(image):
        ndvi = image.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")
        fvc = ndvi.subtract(0.2).divide(0.5 - 0.2).pow(2).rename("FVC")
        fvc = fvc.where(ndvi.lt(0.2), 0).where(ndvi.gt(0.5), 1)
        emissivity = fvc.multiply(0.004).add(0.986).rename("emissivity")
        thermal_k = image.select("ST_B10")
        lst_celsius = (
            thermal_k.divide(
                ee.Image(1).add(
                    ee.Image(10.895e-6)
                    .multiply(thermal_k)
                    .divide(14388)
                    .multiply(emissivity.log())
                )
            )
            .subtract(273.15)
            .rename("LST")
        )
        return lst_celsius.copyProperties(image, ["system:time_start"])

    collection = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUD_COVER", 20))
        .map(apply_scale_factors)
        .map(compute_lst_image)
    )
    lst_median = collection.median().clip(aoi)
    return lst_median, aoi


def compute_lst(district_name: str, start_date: str, end_date: str, n_classes: int = 5) -> dict:
    cache_key = (district_name, start_date, end_date, n_classes)
    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

    lst_median, aoi = lst_image_and_aoi(district_name, start_date, end_date)

    vis_params = {
        "min": 15, "max": 40,
        "palette": ["#313695", "#74add1", "#fee090", "#f46d43", "#a50026"],
    }
    map_id = lst_median.getMapId(vis_params)

    stats = lst_median.reduceRegion(
        reducer=ee.Reducer.mean()
        .combine(ee.Reducer.min(), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=aoi, scale=100, maxPixels=1e9, tileScale=4,
    ).getInfo()

    classes = {
        "Cool (<20°C)": lst_median.lt(20),
        "Moderate (20–25°C)": lst_median.gte(20).And(lst_median.lt(25)),
        "Warm (25–30°C)": lst_median.gte(25).And(lst_median.lt(30)),
        "Hot (30–35°C)": lst_median.gte(30).And(lst_median.lt(35)),
        "Very Hot (>35°C)": lst_median.gte(35),
    }
    labels = list(classes.keys())
    area_img = ee.Image.cat(
        [classes[lbl].multiply(ee.Image.pixelArea()).rename(f"c{i}") for i, lbl in enumerate(labels)]
    )
    area_dict = area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=100, maxPixels=1e9, tileScale=4
    ).getInfo()
    class_areas = {lbl: round((area_dict.get(f"c{i}", 0) or 0) / 1e6, 2) for i, lbl in enumerate(labels)}

    classify = quantile_classify(
        layers=[{"name": "LST", "image": lst_median, "title": "Land Surface Temperature (°C)"}],
        aoi=aoi, scale=100, n_classes=n_classes,
    )

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center = [(bounds[0][1] + bounds[2][1]) / 2, (bounds[0][0] + bounds[2][0]) / 2]

    result = {
        "tile_url": map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean LST (°C)": round(stats.get("LST_mean") or 0, 2),
            "Min LST (°C)": round(stats.get("LST_min") or 0, 2),
            "Max LST (°C)": round(stats.get("LST_max") or 0, 2),
            "Std Dev": round(stats.get("LST_stdDev") or 0, 2),
        },
        "class_areas_km2": class_areas,
        "classify": classify,
        "center": center,
        "district": district_name,
        "start_date": start_date,
        "end_date": end_date,
    }
    with _lock:
        _cache[cache_key] = result
    return result
