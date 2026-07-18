"""
Push a locally-uploaded GeoTIFF onto Google Earth Engine as a *permanent*
image asset — the reverse direction of `gee_image_import.py` (which pulls
existing catalog datasets in). Earth Engine has exactly one ingestion path
for external rasters: stage the file in a Google Cloud Storage bucket the
Earth Engine backend can read, then call `ee.data.startIngestion`.

Staging uses this app's own Replit Object Storage bucket (the same one
`utils/samples_storage.py` / `utils/dataset_storage.py` already write to) —
not a new bucket in the connected Earth Engine project. That bucket already
exists and is billed by Replit, so no Google Cloud billing needs to be
enabled on the Earth Engine project for this to work. Each staged object is
kept private; only the Earth Engine service account is granted read access
to it (via a per-object ACL grant), and the object is deleted again once
ingestion finishes.

Once ingested, the resulting asset ID (e.g. `projects/<project>/assets/foo`)
can be pasted straight into the "Image link or GEE dataset ID" field on this
page to load it back as a live composite for digitizing, or used directly
in any of the other GEE-backed analysis pages in this app.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass

import ee


class AssetUploadError(Exception):
    """Raised when the raster genuinely can't be pushed to Earth Engine —
    the message names the concrete cause (staging failure, permission
    problem, ingestion failure) instead of a generic failure."""


@dataclass
class IngestedAsset:
    asset_id: str
    task_id: str
    bucket: str
    object_path: str


def sanitize_asset_name(name: str) -> str:
    name = name.strip().strip("/")
    return re.sub(r"[^A-Za-z0-9_\-/]", "_", name)


def _service_account_info() -> dict:
    from gee_scripts.auth import _load_key_json

    return json.loads(_load_key_json())


def _poll_ingestion_task(task_id: str, timeout_s: int = 600) -> dict:
    """Blocks until `task_id` reaches a terminal state (or `timeout_s` elapses).
    Shared by both image and table ingestion — Earth Engine's task-status API
    is identical either way. Returns the final status dict, or an empty dict
    on timeout."""
    deadline = time.time() + timeout_s
    status: dict = {}
    while time.time() < deadline:
        statuses = ee.data.getTaskStatus([task_id])
        status = statuses[0] if statuses else {}
        if status.get("state") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(5)
    return status


def _staging_bucket():
    """Return a `google.cloud.storage.Bucket` handle for this app's own
    Replit Object Storage bucket, authenticated the same way
    `replit.object_storage.Client` does internally."""
    from google.auth import identity_pool
    from google.cloud import storage
    from replit.object_storage._config import REPLIT_ADC

    bucket_id = os.environ.get("DEFAULT_OBJECT_STORAGE_BUCKET_ID", "").strip()
    if not bucket_id:
        raise AssetUploadError(
            "DEFAULT_OBJECT_STORAGE_BUCKET_ID is not set — this app's object storage bucket "
            "isn't configured, so there's nowhere to stage the file for Earth Engine to read."
        )

    creds = identity_pool.Credentials(**REPLIT_ADC)
    client = storage.Client(credentials=creds, project="")
    return client.bucket(bucket_id)


def push_raster_to_gee(file_bytes: bytes, filename: str, asset_name: str, allow_overwrite: bool = True) -> IngestedAsset:
    """Stage `file_bytes` (a GeoTIFF) in this app's Object Storage bucket,
    grant the Earth Engine service account read access to just that object,
    then ingest it as a permanent Earth Engine image asset. Blocks until the
    ingestion task finishes and raises AssetUploadError with Earth Engine's
    own failure reason if it doesn't complete successfully — never reports
    success without the task itself confirming COMPLETED."""
    if not filename.lower().endswith((".tif", ".tiff")):
        raise AssetUploadError("Only GeoTIFF files (.tif/.tiff) can be ingested as an Earth Engine image asset.")

    asset_name = sanitize_asset_name(asset_name)
    if not asset_name:
        raise AssetUploadError("Give the asset a name first.")

    key_data = _service_account_info()
    project_id = key_data["project_id"]
    ee_sa_email = key_data["client_email"]

    bucket = _staging_bucket()
    bucket_name = bucket.name
    object_path = f"gee_uploads/{uuid.uuid4().hex}/{filename}"
    blob = bucket.blob(object_path)

    try:
        blob.upload_from_string(file_bytes, content_type="image/tiff")
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
    manifest = {"name": asset_id, "tilesets": [{"sources": [{"uris": [gcs_uri]}]}]}

    request_id = ee.data.newTaskId(1)[0]
    try:
        started = ee.data.startIngestion(request_id, manifest, allow_overwrite=allow_overwrite)
    except Exception as e:  # noqa: BLE001
        _best_effort_delete(blob)
        raise AssetUploadError(f"Earth Engine rejected the ingestion request: {e}") from e

    task_id = (started or {}).get("id") or request_id
    status = _poll_ingestion_task(task_id)

    _best_effort_delete(blob)

    if not status:
        raise AssetUploadError("Timed out waiting for Earth Engine to report the ingestion task's status.")
    if status.get("state") != "COMPLETED":
        raise AssetUploadError(
            f"Earth Engine ingestion did not complete (state: {status.get('state')}): "
            f"{status.get('error_message', 'no error message provided')}"
        )

    return IngestedAsset(asset_id=asset_id, task_id=task_id, bucket=bucket_name, object_path=object_path)


def _best_effort_delete(blob) -> None:
    # Staging cleanup is best-effort: Earth Engine has already read the file
    # by the time ingestion finishes (or definitively failed), so a leftover
    # staged object is just storage cost, never a correctness issue.
    try:
        if blob.exists():
            blob.delete()
    except Exception:
        pass
