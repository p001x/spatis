"""
Vector/points import for Sample Digitization — the vector-data counterpart to
`utils/samples_storage.py` (rasters) and `utils/link_resolver.py` (link
fetching, shared by both).

Supported local/linked formats:
- Shapefile, as a **.zip** bundle (.shp + .dbf + .shx [+ .prj]) — reuses
  `utils/geodata_viz.load_shapefile_gdf`, the same loader the RARE DATA page
  already relies on.
- GeoJSON (.geojson/.json).
- GeoPackage (.gpkg).
- KML (.kml) — read via the `pyogrio`/GDAL `LIBKML` driver.
- CSV of points (.csv) with a latitude/longitude column pair — reuses
  `utils/geodata_viz.csv_to_points_gdf`.

Everything is normalized to a WGS84 (EPSG:4326) GeoJSON `FeatureCollection`
dict so the calling page can render it with `folium.GeoJson` exactly like the
already-saved training samples, regardless of which format it came from.
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from typing import Any

from utils.geodata_viz import csv_to_points_gdf, load_shapefile_gdf

VECTOR_EXTENSIONS = {"zip", "geojson", "json", "gpkg", "kml"}
POINTS_EXTENSIONS = {"csv"}


class VectorImportError(ValueError):
    """Raised for vector/points data that genuinely can't be parsed —
    message names the concrete cause (bad zip, unreadable CRS, missing
    lat/lon columns, etc.)."""


def _ext(filename: str) -> str:
    return filename.lower().rsplit(".", 1)[-1] if "." in filename else ""


def detect_data_kind(filename: str) -> str | None:
    """Returns "vector", "points", or None (not a recognized vector/points format —
    caller should fall back to `utils.samples_storage.detect_image_kind` for rasters)."""
    ext = _ext(filename)
    if ext in POINTS_EXTENSIONS:
        return "points"
    if ext in VECTOR_EXTENSIONS:
        return "vector"
    return None


def _to_wgs84(gdf):
    if gdf.crs is not None and str(gdf.crs).upper() not in ("EPSG:4326", "OGC:CRS84"):
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def load_vector_gdf(file_bytes: bytes, filename: str):
    """Parse `file_bytes` into a WGS84 GeoDataFrame based on `filename`'s extension.
    Raises VectorImportError with a specific, honest message on failure."""
    import geopandas as gpd

    ext = _ext(filename)
    try:
        if ext == "zip":
            gdf = load_shapefile_gdf(file_bytes)
        elif ext == "csv":
            gdf = csv_to_points_gdf(file_bytes)
        elif ext in ("geojson", "json"):
            gdf = gpd.read_file(io.BytesIO(file_bytes))
        elif ext == "gpkg":
            with tempfile.NamedTemporaryFile(suffix=".gpkg") as tmp:
                tmp.write(file_bytes)
                tmp.flush()
                gdf = gpd.read_file(tmp.name)
        elif ext == "kml":
            with tempfile.NamedTemporaryFile(suffix=".kml") as tmp:
                tmp.write(file_bytes)
                tmp.flush()
                try:
                    gdf = gpd.read_file(tmp.name, driver="LIBKML")
                except Exception:
                    gdf = gpd.read_file(tmp.name, driver="KML")
        else:
            raise VectorImportError(
                f"`.{ext}` isn't a recognized vector/points format. Supported: a zipped "
                "Shapefile (.zip), GeoJSON (.geojson/.json), GeoPackage (.gpkg), KML (.kml), "
                "or a points CSV (.csv) with latitude/longitude columns."
            )
    except VectorImportError:
        raise
    except Exception as e:  # noqa: BLE001 - surfaced as a specific, honest message below
        raise VectorImportError(f"Could not read this as {ext.upper()} vector data: {e}") from e

    if gdf.empty:
        raise VectorImportError("This file has no features in it.")

    gdf = _to_wgs84(gdf)
    return gdf


def gdf_to_geojson_dict(gdf) -> dict[str, Any]:
    return json.loads(gdf.to_json())


def geojson_bbox(geojson: dict[str, Any]) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) across every feature's geometry — flattens all
    coordinate arrays regardless of geometry type (Point/LineString/Polygon/Multi*)."""
    xs: list[float] = []
    ys: list[float] = []

    def _walk(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            xs.append(coords[0])
            ys.append(coords[1])
        else:
            for c in coords:
                _walk(c)

    for feature in geojson.get("features", []):
        geom = feature.get("geometry") or {}
        _walk(geom.get("coordinates"))

    if not xs or not ys:
        raise VectorImportError("Could not determine a bounding box for this data.")
    return min(xs), min(ys), max(xs), max(ys)


def geometry_type_summary(geojson: dict[str, Any]) -> str:
    types: dict[str, int] = {}
    for feature in geojson.get("features", []):
        t = (feature.get("geometry") or {}).get("type", "Unknown")
        types[t] = types.get(t, 0) + 1
    return ", ".join(f"{n} {t}" for t, n in sorted(types.items()))


def load_vector_link(url: str, filename_hint: str = "") -> tuple[bytes, str]:
    """Fetch vector/points bytes for a link — thin wrapper kept for symmetry with
    `utils.samples_storage.resolve_image_link`. Actual fetching is the same
    multi-source resolver used for rasters (see `utils/link_resolver.py`)."""
    from utils.samples_storage import MAX_IMPORT_MB
    from utils.link_resolver import resolve_link

    file_bytes, filename, _resolved_url = resolve_link(url, max_mb=MAX_IMPORT_MB)
    return file_bytes, filename
