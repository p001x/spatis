"""
Multi-format export for digitized training samples.

Local formats (Shapefile / GeoJSON / KML / CSV) are built with GeoPandas +
Fiona and returned as bytes for a Streamlit download button. GEE-side
formats (Asset / Google Drive / TFRecord) submit an `ee.batch.Export.table`
task against the live `ee.FeatureCollection` mirrored by `gee_scripts.
sample_sync` and return the task so the caller can show its id/status —
nothing here silently pretends a task succeeded.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import ee


class ExportError(Exception):
    """Raised when a requested export format genuinely can't be produced
    (e.g. no samples, or the local GDAL build lacks a driver) — surfaced to
    the user instead of failing silently."""


def _records_to_geodataframe(records: list[dict[str, Any]]):
    import geopandas as gpd
    from shapely.geometry import shape

    if not records:
        raise ExportError("No samples to export yet.")

    geometries = [shape(r["geometry"]) for r in records]
    df_records = [
        {
            "id": r["id"],
            "class_label": r["class_label"],
            "color": r.get("color", ""),
            "creator": r.get("creator", ""),
            "created_at": r.get("created_at", ""),
            "source_filename": r.get("source_filename", ""),
            "source_url": r.get("source_url", ""),
        }
        for r in records
    ]
    return gpd.GeoDataFrame(df_records, geometry=geometries, crs="EPSG:4326")


def export_shapefile_zip(records: list[dict[str, Any]]) -> bytes:
    """Shapefiles are always a *set* of sidecar files (.shp/.shx/.dbf/.prj),
    and a single .shp can only hold one geometry type — so points and
    polygons/rectangles are split into separate shapefiles, then all of it
    is zipped together into one downloadable archive."""
    gdf = _records_to_geodataframe(records)

    # Normalize to the two shapefile-compatible buckets: Point vs Polygon
    # (rectangles drawn by the Leaflet Draw tool are stored as Polygon).
    is_point = gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
    groups = {"points": gdf[is_point], "polygons": gdf[~is_point]}

    with tempfile.TemporaryDirectory() as tmpdir:
        wrote_any = False
        for name, sub_gdf in groups.items():
            if sub_gdf.empty:
                continue
            shp_path = Path(tmpdir) / f"training_samples_{name}.shp"
            try:
                sub_gdf.to_file(shp_path, driver="ESRI Shapefile")
                wrote_any = True
            except Exception as e:  # noqa: BLE001 - surface the real GDAL error
                raise ExportError(f"Could not write Shapefile ({name}): {e}") from e

        if not wrote_any:
            raise ExportError("No samples to export yet.")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in Path(tmpdir).glob("training_samples_*.*"):
                zf.write(f, arcname=f.name)
        return buf.getvalue()


def export_kml(records: list[dict[str, Any]]) -> bytes:
    gdf = _records_to_geodataframe(records)
    with tempfile.TemporaryDirectory() as tmpdir:
        kml_path = Path(tmpdir) / "training_samples.kml"
        try:
            gdf.to_file(kml_path, driver="KML")
        except Exception as e:  # noqa: BLE001
            raise ExportError(
                "Could not write KML — this environment's GDAL/Fiona build "
                f"doesn't support the KML driver ({e})."
            ) from e
        return kml_path.read_bytes()


def export_csv(records: list[dict[str, Any]]) -> bytes:
    """Flattens geometry to a representative lat/lon (the point itself for
    Point samples, the centroid for Polygon/Rectangle samples) alongside all
    properties — CSV can't hold arbitrary geometry."""
    gdf = _records_to_geodataframe(records)
    reps = gdf.geometry.representative_point()
    out = gdf.drop(columns="geometry").copy()
    out["geometry_type"] = gdf.geometry.geom_type
    out["lon"] = reps.x
    out["lat"] = reps.y
    return out.to_csv(index=False).encode("utf-8")


def export_to_gee_asset(fc: ee.FeatureCollection, asset_id: str, description: str = "training_samples_export"):
    if not asset_id.strip():
        raise ExportError("Provide a destination asset ID (e.g. users/you/training_samples).")
    task = ee.batch.Export.table.toAsset(collection=fc, description=description, assetId=asset_id.strip())
    task.start()
    return task


def export_to_drive(
    fc: ee.FeatureCollection,
    file_format: str,
    description: str = "training_samples_export",
    folder: str = "",
):
    kwargs: dict[str, Any] = {
        "collection": fc,
        "description": description,
        "fileFormat": file_format,
    }
    if folder.strip():
        kwargs["folder"] = folder.strip()
    task = ee.batch.Export.table.toDrive(**kwargs)
    task.start()
    return task
