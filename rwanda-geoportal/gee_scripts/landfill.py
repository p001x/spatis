import math
import ee
import streamlit as st
from gee_scripts.classify_utils import quantile_classify

WEIGHTS = {
    "river": 0.30,
    "residential": 0.25,
    "slope": 0.20,
    "road": 0.15,
    "lulc": 0.10,
}

FACTOR_ORDER = ["river", "residential", "slope", "road", "lulc"]

FACTOR_META = {
    "river": {
        "label": "River Distance",
        "icon": "water",
        "weight_pct": 30,
        "normal_desc": "Farther from rivers = more suitable (protects water quality)",
        "reversed_desc": "Closer to rivers = more suitable (reversed)",
    },
    "residential": {
        "label": "Residential Distance",
        "icon": "home_work",
        "weight_pct": 25,
        "normal_desc": "Farther from settlements = more suitable (protects public health)",
        "reversed_desc": "Closer to settlements = more suitable (reversed)",
    },
    "slope": {
        "label": "Slope",
        "icon": "terrain",
        "weight_pct": 20,
        "normal_desc": "Gentler slope = more suitable (engineering stability & drainage)",
        "reversed_desc": "Steeper slope = more suitable (reversed)",
    },
    "road": {
        "label": "Road Accessibility",
        "icon": "route",
        "weight_pct": 15,
        "normal_desc": "Closer to roads = more suitable (transport efficiency)",
        "reversed_desc": "Farther from roads = more suitable (reversed)",
    },
    "lulc": {
        "label": "Land Cover",
        "icon": "park",
        "weight_pct": 10,
        "normal_desc": "Bare land / grassland = more suitable; forest, water & built-up = unsuitable",
        "reversed_desc": "Forest, water & built-up = more suitable (reversed)",
    },
}

_SCORE_VIS = {
    "min": 1, "max": 5,
    "palette": ["#d73027", "#f46d43", "#fee08b", "#d9ef8b", "#1a9850"],
}


def _distance_km(mask, aoi, scale=100):
    """
    Raster-based Euclidean distance (km) from every pixel to the nearest
    True pixel in `mask`, computed with fastDistanceTransform.
    This avoids passing vector FeatureCollection geometries into distance()
    calls, which is what caused 'Invalid GeoJSON geometry' errors before.
    """
    filled = mask.unmask(0).selfMask().unmask(0).toByte()
    distance_m = (
        filled.fastDistanceTransform(256, "pixels", "squared_euclidean")
        .sqrt()
        .multiply(ee.Image.pixelArea().sqrt())
        .clip(aoi)
    )
    return distance_m.divide(1000).reproject(crs="EPSG:4326", scale=scale)


def _reclass_far_is_good(distance_km):
    """>5 km = 5 (best) ... <1 km = 1 (worst). Used for rivers & residential."""
    return (
        ee.Image(1)
        .where(distance_km.gte(1).And(distance_km.lt(2)), 2)
        .where(distance_km.gte(2).And(distance_km.lt(3)), 3)
        .where(distance_km.gte(3).And(distance_km.lt(5)), 4)
        .where(distance_km.gte(5), 5)
    )


def _reclass_near_is_good(distance_km):
    """<1 km = 5 (best) ... >5 km = 1 (worst). Used for road accessibility."""
    return (
        ee.Image(1)
        .where(distance_km.lt(5), 2)
        .where(distance_km.lt(3), 3)
        .where(distance_km.lt(2), 4)
        .where(distance_km.lt(1), 5)
    )


def _apply_reverse(score_img, reversed_flag):
    if reversed_flag:
        return ee.Image(6).subtract(score_img)
    return score_img


def _factor_urls(image: "ee.Image", key: str, aoi) -> dict:
    """Return tile URL, thumb URL (PNG 512px), and GeoTIFF download URL for one factor score."""
    tile_url = image.getMapId(_SCORE_VIS)["tile_fetcher"].url_format
    thumb_url = image.getThumbURL({
        **_SCORE_VIS,
        "region": aoi,
        "dimensions": 512,
        "format": "png",
    })
    download_url = image.getDownloadURL({
        "name": f"Landfill_{key}_score",
        "scale": 100,
        "region": aoi,
        "format": "GEO_TIFF",
        "filePerBand": False,
    })
    return {"tile_url": tile_url, "thumb_url": thumb_url, "download_url": download_url}


@st.cache_data(ttl=86400, show_spinner=False)
def compute_landfill_suitability(
    district_name: str,
    reverse_river: bool = False,
    reverse_residential: bool = False,
    reverse_slope: bool = False,
    reverse_road: bool = False,
    reverse_lulc: bool = False,
    n_classes: int = 5,
):
    """
    GIS-based Spatial Multi-Criteria Evaluation (SMCE) with AHP-derived weights
    for landfill site suitability, following:
      SI = 0.30(RIVER) + 0.25(RESIDENTIAL) + 0.20(SLOPE) + 0.15(ROADS) + 0.10(LULC)

    Every criterion's classification direction can be reversed via the
    reverse_* flags (score := 6 - score) so users can explore alternative
    siting priorities and immediately see the effect on the composite index.

    All distance criteria are computed with raster distance transforms
    (fastDistanceTransform) rather than vector FeatureCollection.distance(),
    which is more robust and avoids invalid-geometry failures on admin
    boundaries with complex/self-intersecting polygons.
    """
    reverse_flags = {
        "river": reverse_river,
        "residential": reverse_residential,
        "slope": reverse_slope,
        "road": reverse_road,
        "lulc": reverse_lulc,
    }

    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        )
    )
    aoi = rwanda.geometry()

    # ── Slope (%) from SRTM ──────────────────────────────────────────────────
    dem = ee.Image("USGS/SRTMGL1_003").select("elevation")
    slope_deg = ee.Terrain.slope(dem)
    slope_pct = slope_deg.multiply(math.pi / 180).tan().multiply(100)
    slope_score = (
        ee.Image(1)
        .where(slope_pct.gte(0).And(slope_pct.lt(2)), 5)
        .where(slope_pct.gte(2).And(slope_pct.lt(5)), 4)
        .where(slope_pct.gte(5).And(slope_pct.lt(10)), 3)
        .where(slope_pct.gte(10).And(slope_pct.lt(15)), 2)
        .where(slope_pct.gte(15), 1)
        .clip(aoi)
    )
    slope_score = _apply_reverse(slope_score, reverse_flags["slope"]).rename("slope_score")

    # ── Land cover (ESA WorldCover 2021, 10 m) ───────────────────────────────
    lc = ee.Image("ESA/WorldCover/v200/2021").select("Map").clip(aoi)

    # Permanent water (JRC Global Surface Water) — used for river-distance criterion
    gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    water_mask = gsw.gte(50).unmask(0).Or(lc.eq(80)).Or(lc.eq(90))
    river_dist_km = _distance_km(water_mask, aoi)
    river_score = _reclass_far_is_good(river_dist_km)
    river_score = _apply_reverse(river_score, reverse_flags["river"]).rename("river_score")

    # Built-up / settlement mask — residential exclusion buffer
    residential_mask = lc.eq(50)
    residential_dist_km = _distance_km(residential_mask, aoi)
    residential_score = _reclass_far_is_good(residential_dist_km)
    residential_score = _apply_reverse(residential_score, reverse_flags["residential"]).rename("residential_score")

    # Road accessibility proxy — no public Rwanda road vector in the GEE catalog,
    # so proximity to built-up areas (where road density is highest) approximates
    # transport accessibility. Replace with actual OSM/RTDA road vectors when available.
    road_score = _reclass_near_is_good(residential_dist_km)
    road_score = _apply_reverse(road_score, reverse_flags["road"]).rename("road_score")

    # LULC suitability reclass
    lulc_score = (
        ee.Image(1)
        .where(lc.eq(60).Or(lc.eq(30)), 5)   # bare land / grassland
        .where(lc.eq(40), 3)                  # cropland
        .where(lc.eq(20), 2)                  # shrubland
        .where(lc.eq(10).Or(lc.eq(80)).Or(lc.eq(90)).Or(lc.eq(95)).Or(lc.eq(50)), 1)  # forest/water/built-up
        .clip(aoi)
    )
    lulc_score = _apply_reverse(lulc_score, reverse_flags["lulc"]).rename("lulc_score")

    score_images = {
        "river": river_score,
        "residential": residential_score,
        "slope": slope_score,
        "road": road_score,
        "lulc": lulc_score,
    }

    suitability = (
        river_score.multiply(WEIGHTS["river"])
        .add(residential_score.multiply(WEIGHTS["residential"]))
        .add(slope_score.multiply(WEIGHTS["slope"]))
        .add(road_score.multiply(WEIGHTS["road"]))
        .add(lulc_score.multiply(WEIGHTS["lulc"]))
    ).rename("suitability")

    map_id = suitability.getMapId(_SCORE_VIS)

    classes = {
        "Unsuitable (<2)": suitability.lt(2),
        "Marginally Suitable (2–3)": suitability.gte(2).And(suitability.lt(3)),
        "Moderately Suitable (3–4)": suitability.gte(3).And(suitability.lt(4)),
        "Highly Suitable (4–5)": suitability.gte(4).And(suitability.lte(5)),
    }
    # Batched single reduceRegion for all classes instead of one call per class.
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

    # ── Per-factor map URLs (tile / thumb PNG / GeoTIFF download) ─────────────
    factor_maps = {}
    for key in FACTOR_ORDER:
        meta = FACTOR_META[key]
        urls = _factor_urls(score_images[key], key, aoi)
        factor_maps[key] = {
            "label": meta["label"],
            "icon": meta["icon"],
            "weight_pct": meta["weight_pct"],
            "reversed": reverse_flags[key],
            "description": meta["reversed_desc"] if reverse_flags[key] else meta["normal_desc"],
            **urls,
        }

    # ── Quantile classification: suitability + all 5 factor scores ────────────
    classify_layers = [
        {"name": "suitability",  "image": suitability,                    "title": "Suitability Index"},
        {"name": "river_score",  "image": score_images["river"],          "title": "River Distance"},
        {"name": "resid_score",  "image": score_images["residential"],    "title": "Residential Distance"},
        {"name": "slope_score",  "image": score_images["slope"],          "title": "Slope"},
        {"name": "road_score",   "image": score_images["road"],           "title": "Road Accessibility"},
        {"name": "lulc_score",   "image": score_images["lulc"],           "title": "Land Cover"},
    ]
    classify = quantile_classify(
        layers=classify_layers,
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
            "Total Area (km²)":     round(sum(class_areas.values()), 2),
            "Highly Suitable (km²)": class_areas.get("Highly Suitable (4–5)", 0),
            "Unsuitable (km²)":      class_areas.get("Unsuitable (<2)", 0),
        },
        "class_areas_km2": class_areas,
        "classify":        classify,
        "factor_maps":     factor_maps,
        "reverse_flags":   reverse_flags,
        "center":          [center_lat, center_lon],
        "district": district_name,
    }
