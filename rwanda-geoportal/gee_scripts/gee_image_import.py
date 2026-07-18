"""
Import a Google Earth Engine dataset (by its catalog ID, e.g.
`COPERNICUS/S2_SR_HARMONIZED`) as the base layer for Sample Digitization,
as an alternative to pasting a downloadable file link.

This is a *real* Earth Engine composite — an `ee.Image`, filtered/clipped
server-side and rendered as live map tiles via `getMapId` — not a static
downloaded raster. It's the direct answer to wanting an actual `ee.Image`
under the digitizing tool, without the heavier asset-ingestion pipeline
that pushing an arbitrary *external* file into Earth Engine would need
(see `utils/samples_storage.py` for why that part stays out of scope).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import ee
import streamlit as st

# Common Earth Engine catalog prefixes. Used to repair the common typo of
# swapping the catalog's "/" for "_" (e.g. pasting "COPERNICUS_S2_SR_HARMONIZED"
# instead of "COPERNICUS/S2_SR_HARMONIZED").
_KNOWN_PREFIXES = [
    "COPERNICUS", "LANDSAT", "USGS", "MODIS", "NASA", "NOAA", "ESA", "JAXA",
    "FAO", "CSP", "GOOGLE", "WORLDPOP", "JRC", "IDAHO_EPSCOR", "UMD", "OREGONSTATE",
]

# True-color visualization presets for common optical collections. Anything
# not listed falls back to a generic first-3-band stretch (see
# `_fallback_vis`) — still a real composite, just without a hand-tuned preset.
_KNOWN_VIS: dict[str, dict[str, Any]] = {
    "COPERNICUS/S2_SR_HARMONIZED": {
        "bands": ["B4", "B3", "B2"], "min": 0, "max": 3000,
        "cloud_property": "CLOUDY_PIXEL_PERCENTAGE", "cloud_max": 20,
    },
    "COPERNICUS/S2_HARMONIZED": {
        "bands": ["B4", "B3", "B2"], "min": 0, "max": 3000,
        "cloud_property": "CLOUDY_PIXEL_PERCENTAGE", "cloud_max": 20,
    },
    "LANDSAT/LC09/C02/T1_L2": {
        "bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0, "max": 0.3,
        "cloud_property": "CLOUD_COVER", "cloud_max": 20,
        "scale_factor": 0.0000275, "scale_offset": -0.2,
    },
    "LANDSAT/LC08/C02/T1_L2": {
        "bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0, "max": 0.3,
        "cloud_property": "CLOUD_COVER", "cloud_max": 20,
        "scale_factor": 0.0000275, "scale_offset": -0.2,
    },
}


class GeeImportError(Exception):
    """Raised when the given string isn't a resolvable GEE asset/collection."""


@dataclass
class GeeComposite:
    collection_id: str
    tile_url: str
    bbox: tuple[float, float, float, float]
    scene_count: int
    vis_label: str
    start_date: str
    end_date: str


def looks_like_gee_id(raw: str) -> bool:
    """True for bare catalog-style identifiers (no scheme), false for URLs."""
    raw = raw.strip()
    if not raw or "://" in raw:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_/.\-]+", raw))


@st.cache_data(ttl=3600, show_spinner=False)
def resolve_collection_id(raw_id: str) -> str:
    """Find a real Earth Engine asset ID matching the user's input, trying a
    couple of common typo-repairs before giving up. Raises GeeImportError
    with a message naming every candidate tried, so a genuine typo is
    diagnosable rather than silently falling back to something else."""
    raw_id = raw_id.strip().strip("/")
    candidates = [raw_id]

    for prefix in _KNOWN_PREFIXES:
        if raw_id.startswith(prefix + "_"):
            rest = raw_id[len(prefix) + 1:]
            candidates.append(f"{prefix}/{rest.replace('_', '/')}")
            candidates.append(f"{prefix}/{rest}")
            break
    if "_" in raw_id and "/" not in raw_id:
        candidates.append(raw_id.replace("_", "/"))

    tried = []
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        tried.append(candidate)
        try:
            ee.data.getAsset(candidate)
            return candidate
        except Exception:
            continue

    raise GeeImportError(
        f"Couldn't find a Google Earth Engine asset matching `{raw_id}`. Tried: "
        + ", ".join(f"`{c}`" for c in tried)
        + ". Double-check the exact catalog ID (e.g. `COPERNICUS/S2_SR_HARMONIZED`), "
        "or paste a downloadable image link instead."
    )


def _fallback_vis(image: ee.Image) -> tuple[ee.Image, dict[str, Any], str]:
    """No hand-tuned preset for this collection: stretch the first 3 bands
    against their own 2nd/98th percentile so *something* sensible renders,
    rather than guessing fixed min/max that would wash the image out."""
    band_names = image.bandNames().getInfo()
    bands = band_names[:3] if len(band_names) >= 3 else band_names[:1]
    sub = image.select(bands)
    stats = sub.reduceRegion(
        reducer=ee.Reducer.percentile([2, 98]), geometry=image.geometry(), scale=100,
        maxPixels=1e9, bestEffort=True, tileScale=4,
    ).getInfo()
    mins = [stats.get(f"{b}_p2", 0) or 0 for b in bands]
    maxs = [stats.get(f"{b}_p98", 1) or 1 for b in bands]
    vis = {"bands": bands, "min": mins, "max": maxs}
    return sub, vis, f"bands {', '.join(bands)} (auto-stretched)"


@st.cache_data(ttl=1800, show_spinner=False)
def build_gee_composite(
    collection_id: str,
    aoi_geojson: dict[str, Any],
    start_date: str,
    end_date: str,
) -> Optional[GeeComposite]:
    """Build a cloud-filtered median composite (or the image itself, for a
    single ee.Image asset) clipped to `aoi_geojson`, and return live GEE
    tile info for it. Returns None if no scenes are found for an
    ImageCollection in that date range/area; raises GeeImportError for a
    genuine resolution/type failure."""
    aoi = ee.Geometry(aoi_geojson)
    vis_preset = _KNOWN_VIS.get(collection_id)

    try:
        asset_info = ee.data.getAsset(collection_id)
    except Exception as e:
        raise GeeImportError(f"Could not read asset `{collection_id}` from Earth Engine: {e}") from e

    asset_type = asset_info.get("type", "")

    if asset_type == "IMAGE":
        image = ee.Image(collection_id).clip(aoi)
        scene_count = 1
    else:
        collection = ee.ImageCollection(collection_id).filterDate(start_date, end_date).filterBounds(aoi)
        if vis_preset and vis_preset.get("cloud_property"):
            collection = collection.filter(
                ee.Filter.lt(vis_preset["cloud_property"], vis_preset["cloud_max"])
            )
        scene_count = collection.size().getInfo()
        if scene_count == 0:
            return None
        image = collection.median().clip(aoi)

    if vis_preset:
        bands = vis_preset["bands"]
        img_for_vis = image.select(bands)
        if "scale_factor" in vis_preset:
            img_for_vis = img_for_vis.multiply(vis_preset["scale_factor"]).add(vis_preset["scale_offset"])
        vis = {"bands": bands, "min": vis_preset["min"], "max": vis_preset["max"]}
        vis_label = f"true color ({', '.join(bands)})"
    else:
        img_for_vis, vis, vis_label = _fallback_vis(image)

    map_id = img_for_vis.getMapId(vis)
    bounds = aoi.bounds().getInfo()["coordinates"][0]
    bbox = (bounds[0][0], bounds[0][1], bounds[2][0], bounds[2][1])

    return GeeComposite(
        collection_id=collection_id,
        tile_url=map_id["tile_fetcher"].url_format,
        bbox=bbox,
        scene_count=scene_count,
        vis_label=vis_label,
        start_date=start_date,
        end_date=end_date,
    )
