"""Landslide Susceptibility Index — no Streamlit dependency."""
import math
import ee
from cachetools import TTLCache
from threading import Lock
from gee.classify_utils import quantile_classify

LITHOLOGY_ASSET = "projects/ee-petersonyang87/assets/litodoloy"

WEIGHTS = {
    "slope": 0.30, "rainfall": 0.20, "lithology": 0.15,
    "soiltype": 0.14, "landcover": 0.09, "twi": 0.07, "dist_roads": 0.05,
}

LSI_VIS = {"min": 1, "max": 5, "palette": ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"]}
LSI_CLASS_NAMES = ["Very Low", "Low", "Moderate", "High", "Very High"]

_cache: TTLCache = TTLCache(maxsize=64, ttl=3600)
_lock = Lock()


def compute_landslide_susceptibility(
    district_name: str, start_year: int = 2019, end_year: int = 2024, n_classes: int = 5
) -> dict:
    cache_key = (district_name, start_year, end_year, n_classes)
    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

    aoi = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        ))
        .geometry()
    )

    lithology_img = ee.Image(LITHOLOGY_ASSET).clip(aoi)
    dem = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(aoi)
    slope = ee.Terrain.slope(dem)
    flow_acc = ee.Image("WWF/HydroSHEDS/15ACC").clip(aoi)
    slope_rad = slope.multiply(math.pi / 180)
    twi = flow_acc.add(1).log().subtract(slope_rad.tan().add(0.001).log()).rename("TWI")

    n_years = max(1, end_year - start_year + 1)
    rainfall = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
        .filterBounds(aoi).select("precipitation")
        .sum().divide(n_years).clip(aoi).rename("rainfall")
    )

    landcover = ee.Image("ESA/WorldCover/v200/2021").select("Map").clip(aoi)
    soiltype = ee.Image("ISDASOIL/Africa/v1/texture_class").select("texture_0_20").clip(aoi)

    roads = ee.FeatureCollection("projects/sat-io/open-datasets/GRIP4/Africa").filterBounds(aoi)
    roads_img = ee.Image().byte().paint(roads, 1).clip(aoi)
    dist_roads = roads_img.fastDistanceTransform(128).sqrt().multiply(ee.Image.pixelArea().sqrt()).rename("dist_roads")

    slope_r = (
        ee.Image(0).where(slope.lt(5), 1).where(slope.gte(5).And(slope.lt(15)), 2)
        .where(slope.gte(15).And(slope.lt(25)), 3).where(slope.gte(25).And(slope.lt(35)), 4)
        .where(slope.gte(35), 5).clip(aoi).rename("slope_r")
    )
    rainfall_r = (
        ee.Image(0).where(rainfall.lt(900), 1).where(rainfall.gte(900).And(rainfall.lt(1100)), 2)
        .where(rainfall.gte(1100).And(rainfall.lt(1300)), 3).where(rainfall.gte(1300).And(rainfall.lt(1500)), 4)
        .where(rainfall.gte(1500), 5).clip(aoi).rename("rainfall_r")
    )
    twi_r = (
        ee.Image(0).where(twi.lt(4), 1).where(twi.gte(4).And(twi.lt(6)), 2)
        .where(twi.gte(6).And(twi.lt(8)), 3).where(twi.gte(8).And(twi.lt(10)), 4)
        .where(twi.gte(10), 5).clip(aoi).rename("twi_r")
    )
    landcover_r = (
        ee.Image(0).where(landcover.eq(10), 1).where(landcover.eq(80), 1)
        .where(landcover.eq(20), 2).where(landcover.eq(90), 2)
        .where(landcover.eq(30), 3).where(landcover.eq(50), 3)
        .where(landcover.eq(40), 4).where(landcover.eq(60), 5)
        .clip(aoi).rename("landcover_r")
    )
    dist_r = (
        ee.Image(0).where(dist_roads.lt(100), 5).where(dist_roads.gte(100).And(dist_roads.lt(300)), 4)
        .where(dist_roads.gte(300).And(dist_roads.lt(600)), 3).where(dist_roads.gte(600).And(dist_roads.lt(1000)), 2)
        .where(dist_roads.gte(1000), 1).clip(aoi).rename("dist_r")
    )
    litho_r = lithology_img.remap([1,2,3,4,5,6,7,8,9,10], [3,4,5,2,1,3,4,2,5,1], 0).clip(aoi).rename("litho_r")
    soiltype_r = soiltype.remap([1,2,3,4,5,6,7,8,9,10,11,12], [4,4,3,3,2,3,4,5,5,2,2,1], 0).clip(aoi).rename("soiltype_r")

    lsi = (
        litho_r.multiply(WEIGHTS["lithology"]).add(soiltype_r.multiply(WEIGHTS["soiltype"]))
        .add(slope_r.multiply(WEIGHTS["slope"])).add(rainfall_r.multiply(WEIGHTS["rainfall"]))
        .add(landcover_r.multiply(WEIGHTS["landcover"])).add(twi_r.multiply(WEIGHTS["twi"]))
        .add(dist_r.multiply(WEIGHTS["dist_roads"])).rename("LSI")
    )

    lsi_class = (
        ee.Image(0).where(lsi.lt(1.8), 1).where(lsi.gte(1.8).And(lsi.lt(2.6)), 2)
        .where(lsi.gte(2.6).And(lsi.lt(3.4)), 3).where(lsi.gte(3.4).And(lsi.lt(4.2)), 4)
        .where(lsi.gte(4.2), 5).clip(aoi).rename("LSI_class")
    )

    lsi_map_id = lsi.getMapId(LSI_VIS)
    lsi_class_map_id = lsi_class.getMapId({**LSI_VIS, "min": 1, "max": 5})

    stats_raw = lsi.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.min(), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True).combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=aoi, scale=100, maxPixels=1e13, tileScale=4, bestEffort=True,
    ).getInfo()

    class_area_bands = ee.Image.cat(
        [lsi_class.eq(i + 1).multiply(ee.Image.pixelArea()).rename(f"c{i}") for i in range(5)]
    )
    class_area_dict = class_area_bands.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=100, maxPixels=1e13, tileScale=4, bestEffort=True,
    ).getInfo()
    class_areas = {
        lbl: round((class_area_dict.get(f"c{i}", 0) or 0) / 1e6, 2)
        for i, lbl in enumerate(LSI_CLASS_NAMES)
    }

    classify = quantile_classify(
        layers=[
            {"name": "LSI", "image": lsi, "title": "Landslide Susceptibility Index"},
            {"name": "slope_r", "image": slope_r, "title": "Slope"},
            {"name": "rainfall_r", "image": rainfall_r, "title": "Rainfall"},
            {"name": "litho_r", "image": litho_r, "title": "Lithology"},
            {"name": "soiltype_r", "image": soiltype_r, "title": "Soil Type"},
            {"name": "landcover_r", "image": landcover_r, "title": "Land Cover"},
            {"name": "twi_r", "image": twi_r, "title": "TWI"},
            {"name": "dist_r", "image": dist_r, "title": "Distance to Roads"},
        ],
        aoi=aoi, scale=100, n_classes=n_classes,
    )

    centroid = aoi.centroid(maxError=100).coordinates().getInfo()
    center = [centroid[1], centroid[0]]

    result = {
        "lsi_tile_url": lsi_map_id["tile_fetcher"].url_format,
        "lsi_class_tile_url": lsi_class_map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean LSI": round(stats_raw.get("LSI_mean") or 0, 3),
            "Min LSI": round(stats_raw.get("LSI_min") or 0, 3),
            "Max LSI": round(stats_raw.get("LSI_max") or 0, 3),
            "Std Dev": round(stats_raw.get("LSI_stdDev") or 0, 3),
        },
        "class_areas_km2": class_areas,
        "classify": classify,
        "center": center,
        "district": district_name,
        "start_year": start_year,
        "end_year": end_year,
    }
    with _lock:
        _cache[cache_key] = result
    return result
