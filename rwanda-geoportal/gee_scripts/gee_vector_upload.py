"""
Push locally-uploaded (or link-imported) vector/points data onto Google Earth
Engine as a *permanent* table asset — the vector counterpart of
`gee_scripts/gee_asset_upload.py` (rasters). Same staging approach: upload
into this app's own Replit Object Storage bucket (no GCP billing needed),
grant the Earth Engine service account per-object read access, then call
`ee.data.startTableIngestion`.

Supported inputs (all normalized to a GeoDataFrame first via
`utils/vector_import.py`, then re-serialized to a zipped Shapefile — the
*only* vector format `ee.data.startTableIngestion` actually accepts besides
CSV — so every input format (Shapefile zip, GeoJSON, GPKG, KML, CSV points)
goes through the exact same single-file ingestion path).
"""

from __future__ import annotations

from dataclasses import dataclass

import ee

from gee_scripts.gee_asset_upload import (
    AssetUploadError,
    _best_effort_delete,
    _poll_ingestion_task,
    _service_account_info,
    _staging_bucket,
    sanitize_asset_name,
)


@dataclass
class IngestedVectorAsset:
    asset_id: str
    task_id: str
    bucket: str
    object_path: str
    feature_count: int


def push_vector_to_gee(file_bytes: bytes, filename: str, asset_name: str, allow_overwrite: bool = True) -> IngestedVectorAsset:
    """Parse `file_bytes` (Shapefile zip / GeoJSON / GPKG / KML / points CSV) via
    `utils/vector_import.py`, stage it as GeoJSON in this app's Object Storage
    bucket, then ingest it as a permanent Earth Engine table (FeatureCollection)
    asset. Blocks until the ingestion task finishes and raises AssetUploadError
    with Earth Engine's own failure reason if it doesn't complete successfully."""
    import uuid

    from utils.geodata_viz import gdf_to_shapefile_zip
    from utils.vector_import import VectorImportError, load_vector_gdf

    try:
        gdf = load_vector_gdf(file_bytes, filename)
    except VectorImportError as e:
        raise AssetUploadError(str(e)) from e

    feature_count = len(gdf)
    # Earth Engine's table ingestion only accepts a zipped Shapefile (or CSV) as the
    # source URI — not GeoJSON/GPKG/KML directly — so every input format is
    # re-serialized to that one shape Earth Engine actually understands.
    try:
        shapefile_zip_bytes = gdf_to_shapefile_zip(gdf)
    except Exception as e:  # noqa: BLE001
        raise AssetUploadError(f"Could not convert this data to a Shapefile for Earth Engine: {e}") from e

    asset_name = sanitize_asset_name(asset_name)
    if not asset_name:
        raise AssetUploadError("Give the asset a name first.")

    key_data = _service_account_info()
    project_id = key_data["project_id"]
    ee_sa_email = key_data["client_email"]

    bucket = _staging_bucket()
    bucket_name = bucket.name
    object_path = f"gee_uploads/{uuid.uuid4().hex}/data.zip"
    blob = bucket.blob(object_path)

    try:
        blob.upload_from_string(shapefile_zip_bytes, content_type="application/zip")
    except Exception as e:  # noqa: BLE001
        raise AssetUploadError(f"Upload to this app's storage bucket failed: {e}") from e

    try:
        blob.acl.user(ee_sa_email).grant_read()
        blob.acl.save()
    except Exception as e:  # noqa: BLE001
        _best_effort_delete(blob)
        raise AssetUploadError(
            f"Uploaded the file, but couldn't grant Earth Engine's service account "
            f"(`{ee_sa_email}`) read access to it: {e}"
        ) from e

    asset_id = f"projects/{project_id}/assets/{asset_name}"
    gcs_uri = f"gs://{bucket_name}/{object_path}"
    manifest = {"name": asset_id, "sources": [{"uris": [gcs_uri]}]}

    request_id = ee.data.newTaskId(1)[0]
    try:
        started = ee.data.startTableIngestion(request_id, manifest, allow_overwrite=allow_overwrite)
    except Exception as e:  # noqa: BLE001
        _best_effort_delete(blob)
        raise AssetUploadError(f"Earth Engine rejected the table ingestion request: {e}") from e

    task_id = (started or {}).get("id") or request_id
    status = _poll_ingestion_task(task_id)

    _best_effort_delete(blob)

    if not status:
        raise AssetUploadError("Timed out waiting for Earth Engine to report the ingestion task's status.")
    if status.get("state") != "COMPLETED":
        raise AssetUploadError(
            f"Earth Engine table ingestion did not complete (state: {status.get('state')}): "
            f"{status.get('error_message', 'no error message provided')}"
        )

    return IngestedVectorAsset(
        asset_id=asset_id, task_id=task_id, bucket=bucket_name, object_path=object_path, feature_count=feature_count,
    )
