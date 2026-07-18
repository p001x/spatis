"""RUSLE soil erosion analysis — no Streamlit dependency."""
import math
import ee
from cachetools import TTLCache
from threading import Lock

_cache: TTLCache = TTLCache(maxsize=64, ttl=3600)
_lock = Lock()

FACTOR_VIS = {
    "R": {"label": "R — Rainfall Erosivity", "unit": "MJ·mm·ha⁻¹·h⁻¹·yr⁻¹",
          "description": "Roose (1977): R = 38.5 + 0.35×P (CHIRPS annual rainfall)",
          "min": 700, "max": 1300,
          "palette": ["#ffffcc", "#a1dab4", "#41b6c4", "#2c7fb8", "#253494"],
          "normal_desc": "Higher rainfall erosivity = higher erosion risk",
          "reversed_desc": "Higher rainfall erosivity treated as lower risk (reversed)"},
    "K": {"label": "K — Soil Erodibility", "unit": "t·ha·h·MJ⁻¹·ha⁻¹·mm⁻¹",
          "description": "Williams (1995) EPIC formula — OpenLandMap clay & sand (0–10 cm)",
          "min": 0.020, "max": 0.060,
          "palette": ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
          "normal_desc": "More erodible soil = higher erosion risk",
          "reversed_desc": "More erodible soil treated as lower risk (reversed)"},
    "LS": {"label": "LS — Topographic Factor", "unit": "dimensionless",
           "description": "L: Desmet & Govers (1996) via HydroSHEDS; S: McCool et al. (1987)",
           "min": 0, "max": 100,
           "palette": ["#f7fcfd", "#e0ecf4", "#bfd3e6", "#9ebcda", "#8c96c6", "#88419d", "#6e016b"],
           "normal_desc": "Longer/steeper slopes = higher erosion risk",
           "reversed_desc": "Longer/steeper slopes treated as lower risk (reversed)"},
    "C": {"label": "C — Cover Management", "unit": "0 – 1",
          "description": "Van der Knijff (2000): C = exp(−2×NDVI/(1−NDVI)) — Sentinel-2 SR",
          "min": 0.0, "max": 1.0,
          "palette": ["#1a9641", "#a6d96a", "#ffffbf", "#fdae61", "#d7191c"],
          "normal_desc": "Less vegetation cover = higher erosion risk",
          "reversed_desc": "Less vegetation cover treated as lower risk (reversed)"},
    "P": {"label": "P — Support Practice", "unit": "0 – 1",
          "description": "Slope-based Rwanda terracing: <5°→0.10 … >30°→1.00",
          "min": 0.0, "max": 1.0,
          "palette": ["#1a9641", "#a6d96a", "#ffffbf", "#fdae61", "#d7191c"],
          "normal_desc": "Less conservation support = higher erosion risk",
          "reversed_desc": "Less conservation support treated as lower risk (reversed)"},
    "A": {"label": "A — Annual Soil Loss", "unit": "t·ha⁻¹·yr⁻¹",
          "description": "RUSLE result: A = R × K × LS × C × P",
          "min": 0, "max": 200,
          "palette": ["#1a9641", "#a6d96a", "#ffffbf", "#fdae61", "#d7191c"]},
}

RECLASS_FACTOR_ORDER = ["R", "K", "LS", "C", "P"]
RECLASS_WEIGHT_PCT = 20


def _class_palette(n: int) -> list:
    full = ["#1a9850", "#66bd63", "#a6d96a", "#d9ef8b", "#ffffbf",
            "#fee08b", "#fdae61", "#f46d43", "#d73027", "#a50026"]
    if n == 1:
        return ["#ffffbf"]
    if n >= len(full):
        return full[:n]
    step = (len(full) - 1) / (n - 1)
    return [full[round(i * step)] for i in range(n)]


def _class_tile_url(cls_img, n_classes: int) -> str:
    vis = {"min": 1, "max": n_classes, "palette": _class_palette(n_classes)}
    return cls_img.getMapId(vis)["tile_fetcher"].url_format


def _class_thumb_url(cls_img, n_classes: int, aoi) -> str:
    vis = {"min": 1, "max": n_classes, "palette": _class_palette(n_classes)}
    return cls_img.getThumbURL({**vis, "region": aoi, "dimensions": 512, "format": "png"})


def _factor_urls(image, key: str, aoi) -> dict:
    vis = FACTOR_VIS[key]
    vp = {"min": vis["min"], "max": vis["max"], "palette": vis["palette"]}
    return {
        "tile_url": image.getMapId(vp)["tile_fetcher"].url_format,
        "thumb_url": image.getThumbURL({**vp, "region": aoi, "dimensions": 512, "format": "png"}),
        "download_url": image.getDownloadURL({"name": f"RUSLE_{key}", "scale": 100, "region": aoi, "format": "GEO_TIFF", "filePerBand": False}),
    }


def _classify_from_breakpoints(img, breakpoints: list, reverse: bool = False):
    cls = ee.Image(1)
    for i, bp in enumerate(breakpoints):
        cls = cls.where(img.gt(bp), i + 2)
    if reverse:
        n = len(breakpoints) + 1
        cls = ee.Image(n + 1).subtract(cls)
    return cls


def compute_rusle(
    district_name: str, year: int, n_classes: int = 5,
    reverse_r: bool = False, reverse_k: bool = False, reverse_ls: bool = False,
    reverse_c: bool = False, reverse_p: bool = False,
) -> dict:
    cache_key = (district_name, year, n_classes, reverse_r, reverse_k, reverse_ls, reverse_c, reverse_p)
    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(ee.Filter.eq("ADM0_NAME", "Rwanda"), ee.Filter.eq("ADM2_NAME", district_name))
    )
    aoi = rwanda.geometry()
    start = f"{year}-01-01"
    end = f"{year}-12-31"

    chirps_annual = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate(start, end).filterBounds(aoi).sum().clip(aoi)
    R = chirps_annual.multiply(0.35).add(38.5).rename("R")

    clay = ee.Image("OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02").select("b0").clip(aoi)
    sand = ee.Image("OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02").select("b0").clip(aoi)
    silt = clay.add(sand).multiply(-1).add(100).max(1)
    f_csand = sand.multiply(clay.add(sand).divide(100)).multiply(-0.0256).exp().multiply(0.3).add(0.2)
    f_cl_si = silt.divide(clay.add(silt).max(1)).pow(0.3)
    K = f_csand.multiply(f_cl_si).multiply(0.763).multiply(0.1317).max(0.020).min(0.060).rename("K")

    dem = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(aoi)
    slope_deg = ee.Terrain.slope(dem)
    slope_rad = slope_deg.multiply(math.pi / 180)
    sin_theta = slope_rad.sin()
    flow_acc = ee.Image("WWF/HydroSHEDS/15ACC").select("b1").clip(aoi).max(0)
    cell_area_m2 = 450.0 * 450.0
    As = flow_acc.add(0.5).multiply(cell_area_m2)
    L = As.divide(22.13).pow(0.4)
    S_gentle = sin_theta.multiply(10.8).add(0.03)
    S_steep = sin_theta.multiply(16.8).subtract(0.50)
    S = S_gentle.where(slope_deg.gte(5.14), S_steep).max(0.03)
    LS = L.multiply(S).min(300).rename("LS")

    ndvi = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start, end).filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .map(lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI"))
        .median().clip(aoi)
    )
    ndvi_safe = ndvi.max(0.001).min(0.990)
    C = ndvi_safe.multiply(-2).divide(ndvi_safe.multiply(-1).add(1)).exp().max(0.001).min(1.0).rename("C")

    P = (ee.Image(1.0).where(slope_deg.lt(5), 0.10).where(slope_deg.gte(5).And(slope_deg.lt(10)), 0.12)
         .where(slope_deg.gte(10).And(slope_deg.lt(15)), 0.14).where(slope_deg.gte(15).And(slope_deg.lt(20)), 0.19)
         .where(slope_deg.gte(20).And(slope_deg.lt(25)), 0.25).where(slope_deg.gte(25).And(slope_deg.lt(30)), 0.50)
         .where(slope_deg.gte(30), 1.00).clip(aoi).rename("P"))

    A = R.multiply(K).multiply(LS).multiply(C).multiply(P).rename("A")
    A = A.where(A.lt(0), 0).clip(aoi)

    stats_raw = A.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.min(), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True).combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=aoi, scale=250, maxPixels=1e9, tileScale=4,
    ).getInfo()

    factor_img = R.rename("R").addBands(K.rename("K")).addBands(LS.rename("LS")).addBands(C.rename("C")).addBands(P.rename("P"))
    factor_raw = factor_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=250, maxPixels=1e9, tileScale=4).getInfo()

    fixed_class_thresholds = [
        ("Very Low (<10 t/ha/yr)", A.lt(10)),
        ("Low (10–30)", A.gte(10).And(A.lt(30))),
        ("Moderate (30–50)", A.gte(30).And(A.lt(50))),
        ("High (50–100)", A.gte(50).And(A.lt(100))),
        ("Very High (100–200)", A.gte(100).And(A.lt(200))),
        ("Extreme (>200)", A.gte(200)),
    ]
    fixed_labels = [lbl for lbl, _ in fixed_class_thresholds]
    fixed_area_img = ee.Image.cat([mask.multiply(ee.Image.pixelArea()).rename(f"c{i}") for i, (_, mask) in enumerate(fixed_class_thresholds)])
    fixed_area_dict = fixed_area_img.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=250, maxPixels=1e9, tileScale=4).getInfo()
    class_areas = {lbl: round((fixed_area_dict.get(f"c{i}", 0) or 0) / 1e6, 2) for i, lbl in enumerate(fixed_labels)}

    factor_images = {"R": R, "K": K, "LS": LS, "C": C, "P": P, "A": A}
    factor_maps = {}
    for key, img in factor_images.items():
        vis_meta = FACTOR_VIS[key]
        urls = _factor_urls(img, key, aoi)
        factor_maps[key] = {**vis_meta, **urls}

    n_classes = max(2, min(n_classes, 10))
    percentile_steps = [round(100 * j / n_classes) for j in range(1, n_classes)]
    all_factors_img = ee.Image.cat([R.rename("R"), K.rename("K"), LS.rename("LS"), C.rename("C"), P.rename("P"), A.rename("A")])
    pct_dict = all_factors_img.reduceRegion(
        reducer=ee.Reducer.percentile(percentile_steps), geometry=aoi, scale=250,
        maxPixels=1e9, tileScale=4, bestEffort=True,
    ).getInfo()

    def _thresholds(band_name):
        return [pct_dict.get(f"{band_name}_p{p}", 0) or 0 for p in percentile_steps]

    reverse_map = {"R": reverse_r, "K": reverse_k, "LS": reverse_ls, "C": reverse_c, "P": reverse_p}
    class_images = {}
    for key in RECLASS_FACTOR_ORDER:
        bps = [ee.Number(v) for v in _thresholds(key)]
        cls_img = _classify_from_breakpoints(factor_images[key], bps, reverse_map[key]).clip(aoi)
        class_images[key] = cls_img
        factor_maps[key]["reversed"] = reverse_map[key]
        vis_meta = FACTOR_VIS[key]
        factor_maps[key]["direction_desc"] = vis_meta["reversed_desc"] if reverse_map[key] else vis_meta["normal_desc"]
        factor_maps[key]["class_tile_url"] = _class_tile_url(cls_img, n_classes)
        factor_maps[key]["class_thumb_url"] = _class_thumb_url(cls_img, n_classes, aoi)
        factor_maps[key]["class_breakpoints"] = _thresholds(key)

    a_bps = [ee.Number(v) for v in _thresholds("A")]
    A_class = _classify_from_breakpoints(A, a_bps).clip(aoi)

    risk_index = (
        class_images["R"].add(class_images["K"]).add(class_images["LS"])
        .add(class_images["C"]).add(class_images["P"]).divide(5.0).clip(aoi).rename("RiskIndex")
    )
    risk_tile_url = _class_tile_url(risk_index, n_classes)
    risk_thumb_url = _class_thumb_url(risk_index, n_classes, aoi)

    risk_bps_vals = [1 + (n_classes - 1) * j / n_classes for j in range(1, n_classes)]
    risk_class_masks = []
    for j in range(n_classes):
        lo = risk_bps_vals[j - 1] if j > 0 else None
        hi = risk_bps_vals[j] if j < n_classes - 1 else None
        if lo is None:
            mask = risk_index.lt(hi)
        elif hi is None:
            mask = risk_index.gte(lo)
        else:
            mask = risk_index.gte(lo).And(risk_index.lt(hi))
        risk_class_masks.append(mask)

    risk_area_img = ee.Image.cat([m.multiply(ee.Image.pixelArea()).rename(f"r{i}") for i, m in enumerate(risk_class_masks)])
    risk_area_dict = risk_area_img.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=250, maxPixels=1e9, tileScale=4).getInfo()
    risk_class_labels = [f"Risk Class {j + 1}" for j in range(n_classes)]
    risk_class_areas = {lbl: round((risk_area_dict.get(f"r{i}", 0) or 0) / 1e6, 2) for i, lbl in enumerate(risk_class_labels)}
    risk_stats_raw = risk_index.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=aoi, scale=250, maxPixels=1e9, tileScale=4,
    ).getInfo()

    a_class_masks = []
    for j in range(n_classes):
        lo = _thresholds("A")[j - 1] if j > 0 else None
        hi = _thresholds("A")[j] if j < n_classes - 1 else None
        if lo is None:
            mask = A.lt(hi)
        elif hi is None:
            mask = A.gte(lo)
        else:
            mask = A.gte(lo).And(A.lt(hi))
        a_class_masks.append(mask)

    a_class_area_img = ee.Image.cat([m.multiply(ee.Image.pixelArea()).rename(f"a{i}") for i, m in enumerate(a_class_masks)])
    a_class_area_dict = a_class_area_img.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=250, maxPixels=1e9, tileScale=4).getInfo()
    a_thresholds = _thresholds("A")
    a_class_labels = []
    for j in range(n_classes):
        lo = round(a_thresholds[j - 1], 1) if j > 0 else None
        hi = round(a_thresholds[j], 1) if j < n_classes - 1 else None
        a_class_labels.append(f"Class 1 (<{hi})" if lo is None else (f"Class {j+1} (≥{lo})" if hi is None else f"Class {j+1} ({lo}–{hi})"))
    a_class_areas = {lbl: round((a_class_area_dict.get(f"a{i}", 0) or 0) / 1e6, 2) for i, lbl in enumerate(a_class_labels)}

    bounds = aoi.bounds().getInfo()["coordinates"][0]
    center = [(bounds[0][1] + bounds[2][1]) / 2, (bounds[0][0] + bounds[2][0]) / 2]

    result = {
        "tile_url": factor_maps["A"]["tile_url"],
        "risk_index": {
            "tile_url": risk_tile_url, "thumb_url": risk_thumb_url,
            "mean": round(risk_stats_raw.get("RiskIndex_mean") or 0, 2),
            "std_dev": round(risk_stats_raw.get("RiskIndex_stdDev") or 0, 2),
            "class_areas_km2": risk_class_areas, "weight_pct_each": RECLASS_WEIGHT_PCT,
        },
        "stats": {
            "Mean (t/ha/yr)": round(stats_raw.get("A_mean") or 0, 2),
            "Min (t/ha/yr)": round(stats_raw.get("A_min") or 0, 2),
            "Max (t/ha/yr)": round(stats_raw.get("A_max") or 0, 2),
            "Std Dev (t/ha/yr)": round(stats_raw.get("A_stdDev") or 0, 2),
        },
        "factor_means": {
            "R — Rainfall Erosivity": round(factor_raw.get("R") or 0, 1),
            "K — Soil Erodibility": round(factor_raw.get("K") or 0, 4),
            "LS — Topographic Factor": round(factor_raw.get("LS") or 0, 2),
            "C — Cover Management": round(factor_raw.get("C") or 0, 3),
            "P — Support Practice": round(factor_raw.get("P") or 0, 3),
        },
        "class_areas_km2": class_areas,
        "n_class_soil_loss_km2": a_class_areas,
        "n_class_soil_loss_tile": _class_tile_url(A_class, n_classes),
        "factor_maps": factor_maps,
        "reverse_flags": reverse_map,
        "n_classes": n_classes,
        "center": center,
        "district": district_name,
        "year": year,
    }
    with _lock:
        _cache[cache_key] = result
    return result
