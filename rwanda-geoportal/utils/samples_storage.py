"""
Training Samples — link-based image import + digitization storage layer.

Scope (kept intentionally small):
- Resolve a link from any of the source categories `utils/link_resolver.py`
  supports (direct URLs, Google Drive, Dropbox, OneDrive, S3/GCS/Azure,
  GitHub, FTP, link shorteners, ...) and fetch its bytes.
- Persist digitized training samples (point/polygon + class label) as a
  GeoJSON-ish catalog in Replit Object Storage, alongside the existing
  RARE DATA catalogs.

Explicit non-goals (would require credentials/integrations this project
doesn't have — no fake/mocked behavior is implemented for these; see
`utils/link_resolver.py` for the full list): Drive/Dropbox folders, Google
Photos albums, Gmail/Outlook attachments, Box links, Imgur/Flickr albums,
WMS/WMTS/ArcGIS map services, SFTP, and GEE asset IDs.

Also explicitly out of scope:
- Pushing the image into the Google Earth Engine **Code Editor**: that
  requires ingesting an Earth Engine asset (Cloud Storage staging + asset
  ingest), a heavier pipeline than this feature covers. Instead, the image
  is shown next to the app's own GEE-backed layers so both are visible
  side by side in one place.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from replit.object_storage import Client

from utils.link_resolver import LinkResolutionError, resolve_link

MAX_IMPORT_MB = 20_000  # ~20 GB ceiling — effectively unbounded for any real raster/vector
# scene; a hard cap still exists only so a broken/infinite link can't hang the server forever.
SAMPLES_METADATA_KEY = "training_samples/samples.json"

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        bucket_id = os.environ.get("DEFAULT_OBJECT_STORAGE_BUCKET_ID")
        _client = Client(bucket_id=bucket_id) if bucket_id else Client()
    return _client


# Kept as the name this page's `except` clause already imports — same class,
# just re-exported under its established name for backward compatibility.
LinkImportError = LinkResolutionError


def resolve_image_link(url: str) -> tuple[bytes, str]:
    """Fetch bytes for a single-image link. Returns (bytes, filename).

    Delegates to the shared multi-source resolver in `utils/link_resolver.py`.
    Raises LinkImportError with a user-facing message for anything that link
    format can't actually support (Drive folders, unreachable links, etc.)
    """
    file_bytes, filename, _resolved_url = resolve_link(url, max_mb=MAX_IMPORT_MB)
    return file_bytes, filename


def detect_image_kind(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in {"tif", "tiff", "jp2", "img"}:
        return "tiff"
    if ext in {"png", "jpg", "jpeg"}:
        return "image"
    return "other"


DEFAULT_SAMPLE_COLOR = "#0F6E4F"


@dataclass
class TrainingSample:
    id: str
    geometry: dict[str, Any]
    class_label: str
    source_filename: str
    source_url: str
    creator: str
    color: str = DEFAULT_SAMPLE_COLOR
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_samples() -> list[dict[str, Any]]:
    client = _get_client()
    try:
        if not client.exists(SAMPLES_METADATA_KEY):
            return []
        raw = client.download_as_text(SAMPLES_METADATA_KEY)
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_samples(records: list[dict[str, Any]]) -> None:
    client = _get_client()
    client.upload_from_text(SAMPLES_METADATA_KEY, json.dumps(records, indent=2))


def add_sample(sample: TrainingSample) -> None:
    records = load_samples()
    records.append(sample.to_dict())
    save_samples(records)


def delete_sample(sample_id: str) -> bool:
    records = load_samples()
    remaining = [r for r in records if r["id"] != sample_id]
    if len(remaining) == len(records):
        return False
    save_samples(remaining)
    return True


_PALETTE = [
    "#0F6E4F", "#D62839", "#2E86AB", "#F4A259", "#7768AE",
    "#3A6B35", "#E07A5F", "#4A4E69", "#B5838D", "#1B998B",
]


def default_color_for_class(class_label: str) -> str:
    """Deterministic fallback color for a class that has no saved samples
    yet, so the color picker always starts somewhere sensible instead of
    always defaulting to the same green."""
    if not class_label:
        return DEFAULT_SAMPLE_COLOR
    return _PALETTE[hash(class_label) % len(_PALETTE)]


def class_colors(records: list[dict[str, Any]]) -> dict[str, str]:
    """Most-recently-used color per class label, so the map/legend/export
    all render each class consistently even though color lives per-sample."""
    colors: dict[str, str] = {}
    for r in records:
        colors[r["class_label"]] = r.get("color", DEFAULT_SAMPLE_COLOR)
    return colors


def samples_to_geojson(records: list[dict[str, Any]]) -> bytes:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": r["geometry"],
                "properties": {
                    "id": r["id"],
                    "class_label": r["class_label"],
                    "color": r.get("color", DEFAULT_SAMPLE_COLOR),
                    "source_filename": r["source_filename"],
                    "source_url": r["source_url"],
                    "creator": r["creator"],
                    "created_at": r["created_at"],
                },
            }
            for r in records
        ],
    }
    return json.dumps(fc, indent=2).encode("utf-8")
