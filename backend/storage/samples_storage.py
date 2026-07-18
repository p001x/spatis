"""Training Samples — storage layer (FastAPI backend version). Streamlit-free."""
from __future__ import annotations
import json, os, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from replit.object_storage import Client

SAMPLES_KEY = "training_samples/samples.json"

_client: Optional[Client] = None

def _get_client() -> Client:
    global _client
    if _client is None:
        bucket_id = os.environ.get("DEFAULT_OBJECT_STORAGE_BUCKET_ID")
        _client = Client(bucket_id=bucket_id) if bucket_id else Client()
    return _client


@dataclass
class TrainingSample:
    id: str
    geometry: dict[str, Any]
    class_label: str
    source_filename: str
    source_url: str
    creator: str
    color: str = "#0F6E4F"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_samples() -> list[dict[str, Any]]:
    client = _get_client()
    try:
        if not client.exists(SAMPLES_KEY):
            return []
        raw = client.download_as_text(SAMPLES_KEY)
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_samples(records: list[dict[str, Any]]) -> None:
    _get_client().upload_from_text(SAMPLES_KEY, json.dumps(records, indent=2))


def add_sample(sample: TrainingSample) -> dict[str, Any]:
    records = load_samples()
    d = sample.to_dict()
    records.append(d)
    _save_samples(records)
    return d


def delete_sample(sample_id: str) -> bool:
    records = load_samples()
    new = [r for r in records if r["id"] != sample_id]
    if len(new) == len(records):
        return False
    _save_samples(new)
    return True


def samples_to_geojson(records: list[dict[str, Any]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": r["geometry"],
             "properties": {k: v for k, v in r.items() if k != "geometry"}}
            for r in records
        ],
    }
