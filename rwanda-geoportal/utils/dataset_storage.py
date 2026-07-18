"""
RARE DATA — Dataset Repository storage layer.

All geospatial dataset files and their metadata live in Replit Object Storage
(never on local disk, so they survive redeploys). This module owns:

- reading/writing the JSON metadata catalog ("datasets_metadata.json")
- uploading/downloading/deleting raw dataset bytes
- bbox extraction for GeoTIFF, shapefile (zipped), and CSV uploads
- shapely-based spatial intersection helpers
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from replit.object_storage import Client
from shapely.geometry import box, shape as shapely_shape

MAX_UPLOAD_MB = 200
MAX_LINK_MB = 200
LINK_KEY_PREFIX = "url::"  # marks a storage_key as "fetch live from this URL", not Object Storage

# Admin-curated datasets and user/community-contributed datasets are kept in
# completely separate metadata catalogs and storage prefixes so they never mix.
METADATA_KEYS = {
    "admin": "datasets_metadata.json",
    "community": "community_datasets_metadata.json",
}
DATA_PREFIXES = {
    "admin": "rare_data/files/",
    "community": "rare_data/community_files/",
}

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        bucket_id = os.environ.get("DEFAULT_OBJECT_STORAGE_BUCKET_ID")
        _client = Client(bucket_id=bucket_id) if bucket_id else Client()
    return _client


@dataclass
class DatasetRecord:
    id: str
    name: str
    description: str
    file_type: str  # "tiff" | "csv" | "shapefile" | "other"
    storage_key: str
    original_filename: str
    bbox: Optional[list[float]] = None  # [minx, miny, maxx, maxy] in EPSG:4326
    upload_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    file_size_mb: float = 0.0
    status: str = "ok"  # "ok" | "error" | "non-spatial"
    error_message: Optional[str] = None
    source: str = "admin"  # "admin" | "community" — keeps the two catalogs distinguishable
    contributor: Optional[str] = None  # display name for community uploads
    source_url: Optional[str] = None  # set when the file lives on GitHub, not in Object Storage

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Metadata catalog
# ---------------------------------------------------------------------------

def load_metadata(source: str = "admin") -> list[dict[str, Any]]:
    """Load the full dataset catalog for one source ("admin" or "community").

    Admin and community catalogs are stored under different keys and are never merged.
    Returns [] if absent/corrupt.
    """
    client = _get_client()
    key = METADATA_KEYS[source]
    try:
        if not client.exists(key):
            return []
        raw = client.download_as_text(key)
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []


def save_metadata(records: list[dict[str, Any]], source: str = "admin") -> None:
    client = _get_client()
    client.upload_from_text(METADATA_KEYS[source], json.dumps(records, indent=2))


def add_record(record: DatasetRecord, source: str = "admin") -> None:
    records = load_metadata(source=source)
    records.append(record.to_dict())
    save_metadata(records, source=source)


def delete_record(dataset_id: str, source: str = "admin") -> bool:
    """Delete a dataset's file from storage and remove its metadata entry."""
    records = load_metadata(source=source)
    target = next((r for r in records if r["id"] == dataset_id), None)
    if target is None:
        return False

    if not target["storage_key"].startswith(LINK_KEY_PREFIX):
        client = _get_client()
        try:
            if client.exists(target["storage_key"]):
                client.delete(target["storage_key"])
        except Exception:
            pass  # metadata cleanup should proceed even if the blob is already gone

    remaining = [r for r in records if r["id"] != dataset_id]
    try:
        save_metadata(remaining, source=source)
    except Exception:
        return False  # storage outage: report failure instead of crashing the caller
    return True


# ---------------------------------------------------------------------------
# Bbox extraction
# ---------------------------------------------------------------------------

def extract_tiff_bbox(file_bytes: bytes) -> list[float]:
    import rasterio
    from rasterio.warp import transform_bounds

    with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        with rasterio.open(tmp.name) as src:
            bounds = src.bounds
            if src.crs is None:
                return [bounds.left, bounds.bottom, bounds.right, bounds.top]
            minx, miny, maxx, maxy = transform_bounds(
                src.crs, "EPSG:4326", bounds.left, bounds.bottom, bounds.right, bounds.top
            )
            return [minx, miny, maxx, maxy]


def extract_shapefile_bbox(zip_bytes: bytes) -> tuple[list[float], bytes]:
    """Unzip, read with geopandas, reproject to EPSG:4326, compute bbox, re-zip.

    Returns (bbox, rezipped_bytes) — the rezipped bytes are what get stored.
    """
    import geopandas as gpd

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_zip = Path(tmpdir) / "upload.zip"
        tmp_zip.write_bytes(zip_bytes)

        with zipfile.ZipFile(tmp_zip) as zf:
            safe_extractall(zf, tmpdir)

        shp_files = list(Path(tmpdir).glob("**/*.shp"))
        if not shp_files:
            raise ValueError("No .shp file found inside the uploaded zip.")

        gdf = gpd.read_file(shp_files[0])
        if gdf.crs is not None and str(gdf.crs) != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        minx, miny, maxx, maxy = gdf.total_bounds.tolist()

        # Re-zip exactly what was extracted (keeps .shp/.shx/.dbf/.prj together)
        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out_zf:
            for f in Path(tmpdir).rglob("*"):
                if f.is_file() and f.name != "upload.zip":
                    out_zf.write(f, arcname=f.name)
        return [minx, miny, maxx, maxy], out_buf.getvalue()


MAX_ZIP_MEMBERS = 200
MAX_ZIP_UNCOMPRESSED_MB = 500
MAX_ZIP_COMPRESSION_RATIO = 100  # guards against zip bombs (tiny compressed, huge uncompressed)


def safe_extractall(zf: zipfile.ZipFile, dest_dir: str) -> None:
    """Extract a zip while rejecting Zip Slip path traversal and zip-bomb style archives."""
    dest_root = Path(dest_dir).resolve()
    infos = zf.infolist()

    if len(infos) > MAX_ZIP_MEMBERS:
        raise ValueError(f"Zip has {len(infos)} entries, exceeds the {MAX_ZIP_MEMBERS} entry cap.")

    total_uncompressed = 0
    for member in infos:
        member_path = (dest_root / member.filename).resolve()
        if not str(member_path).startswith(str(dest_root) + os.sep) and member_path != dest_root:
            raise ValueError(f"Unsafe path in zip archive: {member.filename!r}")

        total_uncompressed += member.file_size
        if member.compress_size > 0 and member.file_size / member.compress_size > MAX_ZIP_COMPRESSION_RATIO:
            raise ValueError(f"Suspicious compression ratio in zip entry {member.filename!r} (possible zip bomb).")

    if total_uncompressed > MAX_ZIP_UNCOMPRESSED_MB * 1024 * 1024:
        raise ValueError(
            f"Zip would expand to {total_uncompressed / (1024*1024):.1f} MB, "
            f"exceeds the {MAX_ZIP_UNCOMPRESSED_MB} MB cap."
        )

    zf.extractall(dest_dir)


_LAT_NAMES = {"lat", "latitude", "y"}
_LON_NAMES = {"lon", "lng", "longitude", "x"}


def extract_csv_bbox(file_bytes: bytes) -> Optional[list[float]]:
    """Returns bbox if lat/lon-like columns are found, else None (non-spatial)."""
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    cols_lower = {c.lower(): c for c in df.columns}

    lat_col = next((cols_lower[n] for n in _LAT_NAMES if n in cols_lower), None)
    lon_col = next((cols_lower[n] for n in _LON_NAMES if n in cols_lower), None)

    if lat_col is None or lon_col is None:
        return None

    coords = pd.DataFrame({
        "lat": pd.to_numeric(df[lat_col], errors="coerce"),
        "lon": pd.to_numeric(df[lon_col], errors="coerce"),
    }).dropna()  # drop rows where either coordinate is missing/invalid, keeping pairs intact
    if coords.empty:
        return None

    return [
        float(coords["lon"].min()),
        float(coords["lat"].min()),
        float(coords["lon"].max()),
        float(coords["lat"].max()),
    ]


# ---------------------------------------------------------------------------
# Upload orchestration
# ---------------------------------------------------------------------------

def normalize_github_url(url: str) -> str:
    """Turn a GitHub "blob" page URL into the raw file URL it points to.

    Accepts already-raw URLs (raw.githubusercontent.com, gist raw, etc.) unchanged.
    Example:
      https://github.com/user/repo/blob/main/data/file.csv
      -> https://raw.githubusercontent.com/user/repo/main/data/file.csv
    """
    url = url.strip()
    if "github.com" in url and "/blob/" in url and "raw.githubusercontent.com" not in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


def fetch_url_bytes(url: str, max_mb: float = MAX_LINK_MB) -> bytes:
    """Download a remote file (e.g. from GitHub) into memory, enforcing a size cap.

    Raises ValueError/requests exceptions on failure — callers must handle them.
    """
    resp = requests.get(url, timeout=30, stream=True)
    resp.raise_for_status()

    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > max_mb * 1024 * 1024:
        raise ValueError(f"File is {int(content_length) / (1024*1024):.1f} MB, exceeds the {max_mb:.0f} MB cap.")

    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        total += len(chunk)
        if total > max_mb * 1024 * 1024:
            raise ValueError(f"File exceeds the {max_mb:.0f} MB cap.")
        chunks.append(chunk)
    return b"".join(chunks)


def filename_from_url(url: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path
    return path.rsplit("/", 1)[-1] or "dataset"


def detect_file_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in {"tif", "tiff"}:
        return "tiff"
    if ext == "csv":
        return "csv"
    if ext == "zip":
        return "shapefile"
    return "other"


def process_and_store_upload(
    filename: str,
    file_bytes: bytes,
    name: str,
    description: str,
    source: str = "admin",
    contributor: Optional[str] = None,
) -> DatasetRecord:
    """Detect type, extract bbox, upload bytes to Object Storage, return the metadata record.

    `source` ("admin" or "community") determines which catalog/storage prefix this
    dataset is filed under — admin and community data are never mixed.

    Never raises for parse errors — bad uploads are recorded with status="error"
    (caller should still show st.error with the message).
    """
    size_mb = len(file_bytes) / (1024 * 1024)
    file_type = detect_file_type(filename)
    dataset_id = str(uuid.uuid4())
    data_prefix = DATA_PREFIXES[source]
    storage_key = f"{data_prefix}{dataset_id}_{filename}"

    bbox: Optional[list[float]] = None
    status = "ok"
    error_message = None
    bytes_to_store = file_bytes

    try:
        if size_mb > MAX_UPLOAD_MB:
            raise ValueError(f"File is {size_mb:.1f} MB, exceeds the {MAX_UPLOAD_MB} MB upload cap.")

        if file_type == "tiff":
            bbox = extract_tiff_bbox(file_bytes)
        elif file_type == "shapefile":
            storage_key = f"{data_prefix}{dataset_id}.zip"
            bbox, bytes_to_store = extract_shapefile_bbox(file_bytes)
        elif file_type == "csv":
            bbox = extract_csv_bbox(file_bytes)
            if bbox is None:
                status = "non-spatial"
        else:
            status = "non-spatial"
    except Exception as e:  # noqa: BLE001 - deliberately broad, upload must never crash the app
        status = "error"
        error_message = str(e)

    if status != "error":
        try:
            client = _get_client()
            client.upload_from_bytes(storage_key, bytes_to_store)
        except Exception as e:  # noqa: BLE001 - storage outages must not crash the app
            status = "error"
            error_message = f"Failed to save file to storage: {e}"

    record = DatasetRecord(
        id=dataset_id,
        name=name,
        description=description,
        file_type=file_type,
        storage_key=storage_key,
        original_filename=filename,
        bbox=bbox,
        file_size_mb=round(size_mb, 3),
        status=status,
        error_message=error_message,
        source=source,
        contributor=contributor,
    )
    try:
        add_record(record, source=source)
    except Exception as e:  # noqa: BLE001 - metadata catalog write failures must not crash the app
        record.status = "error"
        record.error_message = f"File processed but metadata could not be saved: {e}"
    return record


def process_and_store_link(
    url: str,
    name: str,
    description: str,
    source: str = "admin",
    contributor: Optional[str] = None,
) -> DatasetRecord:
    """Register a dataset that stays hosted on GitHub — only the URL + metadata are saved.

    The file itself is fetched live from GitHub on every view/download; nothing is
    duplicated into Object Storage. `source` ("admin" or "community") determines which
    catalog this dataset is filed under, matching `process_and_store_upload`.

    Never raises for fetch/parse errors — bad links are recorded with status="error".
    """
    raw_url = normalize_github_url(url)
    filename = filename_from_url(raw_url)
    file_type = detect_file_type(filename)
    dataset_id = str(uuid.uuid4())
    storage_key = f"{LINK_KEY_PREFIX}{raw_url}"

    bbox: Optional[list[float]] = None
    status = "ok"
    error_message = None
    size_mb = 0.0

    try:
        file_bytes = fetch_url_bytes(raw_url)
        size_mb = len(file_bytes) / (1024 * 1024)

        if file_type == "tiff":
            bbox = extract_tiff_bbox(file_bytes)
        elif file_type == "shapefile":
            bbox, _ = extract_shapefile_bbox(file_bytes)
        elif file_type == "csv":
            bbox = extract_csv_bbox(file_bytes)
            if bbox is None:
                status = "non-spatial"
        else:
            status = "non-spatial"
    except Exception as e:  # noqa: BLE001 - a bad link must never crash the app
        status = "error"
        error_message = f"Could not fetch/parse this link: {e}"

    record = DatasetRecord(
        id=dataset_id,
        name=name,
        description=description,
        file_type=file_type,
        storage_key=storage_key,
        original_filename=filename,
        bbox=bbox,
        file_size_mb=round(size_mb, 3),
        status=status,
        error_message=error_message,
        source=source,
        contributor=contributor,
        source_url=raw_url,
    )
    try:
        add_record(record, source=source)
    except Exception as e:  # noqa: BLE001 - metadata catalog write failures must not crash the app
        record.status = "error"
        record.error_message = f"Link registered but metadata could not be saved: {e}"
    return record


def download_dataset_bytes(storage_key: str) -> bytes:
    """Fetch a dataset's bytes — live from GitHub for linked datasets, else from Object Storage."""
    if storage_key.startswith(LINK_KEY_PREFIX):
        url = storage_key[len(LINK_KEY_PREFIX):]
        return fetch_url_bytes(url)
    client = _get_client()
    return client.download_as_bytes(storage_key)


# ---------------------------------------------------------------------------
# Spatial intersection helpers
# ---------------------------------------------------------------------------

def bbox_to_box(bbox: list[float]):
    minx, miny, maxx, maxy = bbox
    return box(minx, miny, maxx, maxy)


def datasets_intersecting(records: list[dict[str, Any]], area_geojson: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter spatial records whose bbox intersects the given GeoJSON geometry.

    If area_geojson is None, returns every spatial (bbox-having) record.
    """
    spatial = [r for r in records if r.get("bbox")]
    if area_geojson is None:
        return spatial

    try:
        area_geom = shapely_shape(area_geojson)
    except Exception:
        return spatial

    return [r for r in spatial if bbox_to_box(r["bbox"]).intersects(area_geom)]


def build_zip_of_datasets(records: list[dict[str, Any]]) -> bytes:
    """Download every record's file (Object Storage, or live from GitHub for linked ones) and zip it."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in records:
            try:
                data = download_dataset_bytes(r["storage_key"])
                zf.writestr(r["original_filename"], data)
            except Exception:
                continue  # skip files that fail to download rather than aborting the whole bundle
    return buf.getvalue()
