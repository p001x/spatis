"""
Shared helpers for quantile-based image classification used across all modules.

Pattern (one-shot, two GEE round-trips for any number of layers/classes):
  1. One batched reduceRegion(percentile) to compute all breakpoints.
  2. One batched reduceRegion(sum) to compute all class areas.
  Then build tile + thumb URLs per classified layer (no extra GEE calls).
"""
import ee

PANEL_LETTERS = "ABCDEFGHIJ"


def class_palette(n: int) -> list:
    """Return n hex colours spanning green → yellow → red."""
    full = [
        "#1a9850", "#66bd63", "#a6d96a", "#d9ef8b", "#ffffbf",
        "#fee08b", "#fdae61", "#f46d43", "#d73027", "#a50026",
    ]
    n = max(1, min(n, len(full)))
    if n == 1:
        return [full[4]]
    step = (len(full) - 1) / (n - 1)
    return [full[round(i * step)] for i in range(n)]


def class_labels(n: int) -> list:
    """Descriptive labels (low → high) for n classes."""
    presets = {
        2: ["Low", "High"],
        3: ["Low", "Moderate", "High"],
        4: ["Low", "Moderate", "High", "Very High"],
        5: ["Very Low", "Low", "Moderate", "High", "Very High"],
        6: ["Very Low", "Low", "Moderate", "High", "Very High", "Extreme"],
    }
    return presets.get(n, [f"Class {i + 1}" for i in range(n)])


def quantile_classify(layers: list, aoi, scale: int, n_classes: int) -> dict:
    """
    Classify each layer into n_classes using quantile breakpoints computed within
    `aoi`. All breakpoints and all class areas are fetched in exactly two GEE
    round-trips regardless of how many layers or classes are requested.

    Parameters
    ----------
    layers     : list of {"name": str, "image": ee.Image, "title": str}
                 Each image must carry a single band named `name`.
    aoi        : ee.Geometry — the study-area boundary (already clipped).
    scale      : int — pixel size for reduceRegion (metres).
    n_classes  : int — number of output classes (clamped to 2–10).

    Returns
    -------
    dict:
      "panels"          : list of panel dicts (see below)
      "n_classes"       : int
      "percentile_steps": list[int]

    Each panel dict contains:
      "letter"      : "A", "B", …
      "name"        : band name (str)
      "title"       : human-readable title (str)
      "tile_url"    : GEE tile URL for Folium
      "thumb_url"   : 512 px PNG thumbnail URL
      "breakpoints" : list[float]  — N-1 data-driven thresholds
      "areas"       : {label_with_range: km²}
    """
    n = max(2, min(n_classes, 10))
    pct_steps = [round(100 * j / n) for j in range(1, n)]
    pal  = class_palette(n)
    lbls = class_labels(n)
    vis  = {"min": 1, "max": n, "palette": pal}

    names  = [lay["name"]  for lay in layers]
    images = [lay["image"] for lay in layers]
    titles = [lay["title"] for lay in layers]

    # ── Round-trip 1: percentile breakpoints (all bands, one call) ────────────
    all_bands = ee.Image.cat([img.rename(nm) for nm, img in zip(names, images)])
    pct_raw = all_bands.reduceRegion(
        reducer=ee.Reducer.percentile(pct_steps),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9,
        tileScale=4,
        bestEffort=True,
    ).getInfo()

    # ── Build classified images ────────────────────────────────────────────────
    classified = []
    area_bands = []
    for j, (nm, img) in enumerate(zip(names, images)):
        bps = [pct_raw.get(f"{nm}_p{p}", 0) or 0 for p in pct_steps]
        cls = ee.Image(1)
        for i, bp in enumerate(bps):
            cls = cls.where(img.gt(bp), i + 2)
        cls = cls.clip(aoi)
        classified.append({"bps": bps, "cls": cls})
        # Area bands: one band per (layer × class)
        for ci in range(n):
            area_bands.append(
                cls.eq(ci + 1).multiply(ee.Image.pixelArea()).rename(f"b{j}c{ci}")
            )

    # ── Round-trip 2: class areas (all layers × all classes, one call) ────────
    area_img  = ee.Image.cat(area_bands)
    area_raw  = area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=1e9, tileScale=4
    ).getInfo()

    # ── Build panels (tile + thumb URLs — no extra round-trips) ───────────────
    panels = []
    for j, (nm, title) in enumerate(zip(names, titles)):
        bps = classified[j]["bps"]
        cls = classified[j]["cls"]

        tile_url  = cls.getMapId(vis)["tile_fetcher"].url_format
        thumb_url = cls.getThumbURL({
            **vis, "region": aoi, "dimensions": 512, "format": "png",
        })

        areas = {}
        for ci, lbl in enumerate(lbls):
            if ci == 0:
                suffix = f" (<{bps[0]:.3g})" if bps else ""
            elif ci == n - 1:
                suffix = f" (≥{bps[-1]:.3g})" if bps else ""
            else:
                suffix = f" ({bps[ci-1]:.3g}–{bps[ci]:.3g})"
            km2 = round((area_raw.get(f"b{j}c{ci}", 0) or 0) / 1e6, 2)
            areas[lbl + suffix] = km2

        panels.append({
            "letter":      PANEL_LETTERS[j],
            "name":        nm,
            "title":       title,
            "tile_url":    tile_url,
            "thumb_url":   thumb_url,
            "areas":       areas,
            "breakpoints": bps,
        })

    return {"panels": panels, "n_classes": n, "percentile_steps": pct_steps}
