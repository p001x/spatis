"""
GEE context layer for the Sample Digitization page.

The image a user imports here is an arbitrary external file (any GeoTIFF
reachable by URL) — turning that specific raster into a real `ee.Image`
would require ingesting it as an Earth Engine asset (staging through Cloud
Storage, then an asset-ingest job), which is a separate, heavier pipeline
this feature does not implement (see `utils/samples_storage.py` docstring).

What this module *does* provide, so the local raster and a genuine
GEE-backed image are visible on the same map: a recent, cloud-filtered
Sentinel-2 true-color composite clipped to the imported raster's own
bounding box, fetched live from Earth Engine via `getMapId` (the same
pattern every other module in this app uses for its tile layers).
"""

from __future__ import annotations

from datetime import datetime, timezone

import ee
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def sentinel2_context_layer(bbox: tuple[float, float, float, float], months_back: int = 6):
    """Returns a dict with a tile_url + scene count for a Sentinel-2 SR
    composite over `bbox` (minx, miny, maxx, maxy), or None if no cloud-free
    scenes were found in the lookback window. Raises on a genuine GEE error
    instead of returning a fake/empty layer."""
    minx, miny, maxx, maxy = bbox
    geom = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

    end = ee.Date(datetime.now(timezone.utc).isoformat())
    start = end.advance(-months_back, "month")

    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    count = col.size().getInfo()
    if count == 0:
        return None

    image = col.limit(20).median().clip(geom)
    vis_params = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
    map_id = image.getMapId(vis_params)

    return {
        "tile_url": map_id["tile_fetcher"].url_format,
        "scene_count": count,
        "months_back": months_back,
    }
