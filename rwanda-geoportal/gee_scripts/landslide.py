"""
Landslide Susceptibility Index (LSI) — Weighted Overlay (AHP)

Factors & weights:
  Slope          0.30   SRTM DEM via ee.Terrain
  Rainfall       0.20   CHIRPS daily → mean annual (mm/yr)
  Lithology      0.15   GEE asset (litodoloy) — remapped 1-5
  Soil type      0.14   ISDA Africa texture class — remapped 1-5
  Land cover     0.09   ESA WorldCover 2021 — remapped 1-5
  TWI            0.07   HydroSHEDS flow-acc + DEM
  Dist to roads  0.05   GRIP4 Africa fastDistanceTransform

AOI is the selected district boundary (FAO GAUL 2015 level 2).
Lithology is used as a data layer clipped to that district.
The service account must have read access to the lithology GEE asset.
"""
import math

import ee
import streamlit as st

from gee_scripts.classify_utils import quantile_classify

# ── GEE asset ──────────────────────────────────────────────────────────────
LITHOLOGY_ASSET = "projects/ee-petersonyang87/assets/litodoloy"

# ── AHP weights (must sum to 1.0) ──────────────────────────────────────────
WEIGHTS = {
    "slope":      0.30,
    "rainfall":   0.20,
    "lithology":  0.15,
    "soiltype":   0.14,
    "landcover":  0.09,
    "twi":        0.07,
    "dist_roads": 0.05,
}

FACTOR_META = {
    "slope":      {"label": "Slope",             "icon": "terrain",  "weight_pct": 30},
    "rainfall":   {"label": "Rainfall",          "icon": "rainy",  "weight_pct": 20},
    "lithology":  {"label": "Lithology",         "icon": "landscape",  "weight_pct": 15},
    "soiltype":   {"label": "Soil Type",         "icon": "public",  "weight_pct": 14},
    "landcover":  {"label": "Land Cover",        "icon": "park",  "weight_pct":  9},
    "twi":        {"label": "TWI",               "icon": "water_drop",  "weight_pct":  7},
    "dist_roads": {"label": "Distance to Roads", "icon": "route",  "weight_pct":  5},
}

LSI_VIS = {
    "min": 1, "max": 5,
    "palette": ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"],
}

LSI_CLASS_NAMES = ["Very Low", "Low", "Moderate", "High", "Very High"]


@st.cache_data(ttl=3600, show_spinner=False)
def compute_landslide_susceptibility(
    district_name: str,
    start_year:    int = 2019,
    end_year:      int = 2024,
    n_classes:     int = 5,
):
    """
    Compute Landslide Susceptibility Index for a Rwanda district.

    Parameters
    ----------
    district_name : Rwanda district name (FAO GAUL ADM2_NAME)
    start_year    : first year of CHIRPS rainfall window (inclusive)
    end_year      : last  year of CHIRPS rainfall window (inclusive)
    n_classes     : number of quantile classes for the Classify tab
    """
    # ── AOI: selected district (FAO GAUL level 2) ─────────────────────────
    aoi = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(
            ee.Filter.And(
                ee.Filter.eq("ADM0_NAME", "Rwanda"),
                ee.Filter.eq("ADM2_NAME", district_name),
            )
        )
        .geometry()
    )

    # ── Lithology (GEE asset — clipped to district) ───────────────────────
    lithology_img = ee.Image(LITHOLOGY_ASSET).clip(aoi)

    # ── DEM & terrain ──────────────────────────────────────────────────────
    dem   = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(aoi)
    slope = ee.Terrain.slope(dem)                                    # degrees

    # ── TWI = ln(flowAcc + 1) − ln(tan(slope_rad) + 0.001) ───────────────
    flow_acc  = ee.Image("WWF/HydroSHEDS/15ACC").clip(aoi)
    slope_rad = slope.multiply(math.pi / 180)
    twi = (
        flow_acc.add(1).log()
        .subtract(slope_rad.tan().add(0.001).log())
        .rename("TWI")
    )

    # ── CHIRPS mean annual rainfall (mm/yr) ───────────────────────────────
    n_years  = max(1, end_year - start_year + 1)
    rainfall = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
        .filterBounds(aoi)
        .select("precipitation")
        .sum()
        .divide(n_years)
        .clip(aoi)
        .rename("rainfall")
    )

    # ── Land cover (ESA WorldCover 2021) ───────────────────────────────────
    landcover = ee.Image("ESA/WorldCover/v200/2021").select("Map").clip(aoi)

    # ── Soil type (ISDA Africa) ────────────────────────────────────────────
    soiltype = (
        ee.Image("ISDASOIL/Africa/v1/texture_class")
        .select("texture_0_20")
        .clip(aoi)
    )

    # ── Distance to roads (GRIP4 Africa) ──────────────────────────────────
    roads     = ee.FeatureCollection("projects/sat-io/open-datasets/GRIP4/Africa").filterBounds(aoi)
    roads_img = ee.Image().byte().paint(roads, 1).clip(aoi)
    dist_roads = (
        roads_img.fastDistanceTransform(128)
        .sqrt()
        .multiply(ee.Image.pixelArea().sqrt())
        .rename("dist_roads")
    )

    # ── Reclassify each factor → 1-5 susceptibility scale ─────────────────
    slope_r = (
        ee.Image(0)
        .where(slope.lt(5), 1)
        .where(slope.gte(5).And(slope.lt(15)), 2)
        .where(slope.gte(15).And(slope.lt(25)), 3)
        .where(slope.gte(25).And(slope.lt(35)), 4)
        .where(slope.gte(35), 5)
        .clip(aoi).rename("slope_r")
    )

    rainfall_r = (
        ee.Image(0)
        .where(rainfall.lt(900), 1)
        .where(rainfall.gte(900).And(rainfall.lt(1100)), 2)
        .where(rainfall.gte(1100).And(rainfall.lt(1300)), 3)
        .where(rainfall.gte(1300).And(rainfall.lt(1500)), 4)
        .where(rainfall.gte(1500), 5)
        .clip(aoi).rename("rainfall_r")
    )

    twi_r = (
        ee.Image(0)
        .where(twi.lt(4), 1)
        .where(twi.gte(4).And(twi.lt(6)), 2)
        .where(twi.gte(6).And(twi.lt(8)), 3)
        .where(twi.gte(8).And(twi.lt(10)), 4)
        .where(twi.gte(10), 5)
        .clip(aoi).rename("twi_r")
    )

    # ESA codes: 10 Tree, 20 Shrub, 30 Grass, 40 Crop, 50 Built, 60 Bare, 80 Water, 90 Wetland
    landcover_r = (
        ee.Image(0)
        .where(landcover.eq(10), 1)
        .where(landcover.eq(80), 1)
        .where(landcover.eq(20), 2)
        .where(landcover.eq(90), 2)
        .where(landcover.eq(30), 3)
        .where(landcover.eq(50), 3)
        .where(landcover.eq(40), 4)
        .where(landcover.eq(60), 5)
        .clip(aoi).rename("landcover_r")
    )

    dist_r = (
        ee.Image(0)
        .where(dist_roads.lt(100), 5)
        .where(dist_roads.gte(100).And(dist_roads.lt(300)), 4)
        .where(dist_roads.gte(300).And(dist_roads.lt(600)), 3)
        .where(dist_roads.gte(600).And(dist_roads.lt(1000)), 2)
        .where(dist_roads.gte(1000), 1)
        .clip(aoi).rename("dist_r")
    )

    # Lithology remap — class codes 1-10 mapped to susceptibility 1-5
    litho_r = (
        lithology_img
        .remap([1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
               [3, 4, 5, 2, 1, 3, 4, 2, 5, 1], 0)
        .clip(aoi).rename("litho_r")
    )

    # ISDA soil texture classes 1-12 mapped to susceptibility 1-5
    soiltype_r = (
        soiltype
        .remap([1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12],
               [4,  4,  3,  3,  2,  3,  4,  5,  5,  2,  2,  1], 0)
        .clip(aoi).rename("soiltype_r")
    )

    # ── Weighted Overlay → LSI ─────────────────────────────────────────────
    lsi = (
        litho_r    .multiply(WEIGHTS["lithology"])
        .add(soiltype_r .multiply(WEIGHTS["soiltype"]))
        .add(slope_r    .multiply(WEIGHTS["slope"]))
        .add(rainfall_r .multiply(WEIGHTS["rainfall"]))
        .add(landcover_r.multiply(WEIGHTS["landcover"]))
        .add(twi_r      .multiply(WEIGHTS["twi"]))
        .add(dist_r     .multiply(WEIGHTS["dist_roads"]))
        .rename("LSI")
    )

    # ── Fixed 5-class classification ──────────────────────────────────────
    lsi_class = (
        ee.Image(0)
        .where(lsi.lt(1.8), 1)
        .where(lsi.gte(1.8).And(lsi.lt(2.6)), 2)
        .where(lsi.gte(2.6).And(lsi.lt(3.4)), 3)
        .where(lsi.gte(3.4).And(lsi.lt(4.2)), 4)
        .where(lsi.gte(4.2), 5)
        .clip(aoi)
        .rename("LSI_class")
    )

    # ── Tile URLs ──────────────────────────────────────────────────────────
    lsi_map_id       = lsi.getMapId(LSI_VIS)
    lsi_class_map_id = lsi_class.getMapId({**LSI_VIS, "min": 1, "max": 5})

    # ── Stats: one batched call (mean/min/max/std) ─────────────────────────
    stats_raw = lsi.reduceRegion(
        reducer=(
            ee.Reducer.mean()
            .combine(ee.Reducer.min(),    sharedInputs=True)
            .combine(ee.Reducer.max(),    sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
        ),
        geometry=aoi, scale=100, maxPixels=1e13, tileScale=4, bestEffort=True,
    ).getInfo()

    # ── Class areas: one batched reduceRegion ─────────────────────────────
    class_area_bands = ee.Image.cat(
        [lsi_class.eq(i + 1).multiply(ee.Image.pixelArea()).rename(f"c{i}") for i in range(5)]
    )
    class_area_dict = class_area_bands.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi, scale=100, maxPixels=1e13, tileScale=4, bestEffort=True,
    ).getInfo()
    class_areas = {
        lbl: round((class_area_dict.get(f"c{i}", 0) or 0) / 1e6, 2)
        for i, lbl in enumerate(LSI_CLASS_NAMES)
    }

    # ── Quantile classification: LSI + all 7 reclassified factors ──────────
    classify = quantile_classify(
        layers=[
            {"name": "LSI",         "image": lsi,         "title": "Landslide Susceptibility Index"},
            {"name": "slope_r",     "image": slope_r,     "title": "Slope"},
            {"name": "rainfall_r",  "image": rainfall_r,  "title": "Rainfall"},
            {"name": "litho_r",     "image": litho_r,     "title": "Lithology"},
            {"name": "soiltype_r",  "image": soiltype_r,  "title": "Soil Type"},
            {"name": "landcover_r", "image": landcover_r, "title": "Land Cover"},
            {"name": "twi_r",       "image": twi_r,       "title": "TWI"},
            {"name": "dist_r",      "image": dist_r,      "title": "Distance to Roads"},
        ],
        aoi=aoi,
        scale=100,
        n_classes=n_classes,
    )

    # ── Map centre from district centroid ─────────────────────────────────
    centroid  = aoi.centroid(maxError=100).coordinates().getInfo()
    center    = [centroid[1], centroid[0]]

    return {
        "lsi_tile_url":       lsi_map_id["tile_fetcher"].url_format,
        "lsi_class_tile_url": lsi_class_map_id["tile_fetcher"].url_format,
        "stats": {
            "Mean LSI":  round(stats_raw.get("LSI_mean")   or 0, 3),
            "Min LSI":   round(stats_raw.get("LSI_min")    or 0, 3),
            "Max LSI":   round(stats_raw.get("LSI_max")    or 0, 3),
            "Std Dev":   round(stats_raw.get("LSI_stdDev") or 0, 3),
        },
        "class_areas_km2": class_areas,
        "classify":         classify,
        "center":           center,
        "district":         district_name,
        "start_year":       start_year,
        "end_year":         end_year,
    }
