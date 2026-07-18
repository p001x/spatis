"""
Mirror locally digitized training samples into a live `ee.FeatureCollection`
for the current Streamlit session.

Design notes:
- Each saved `TrainingSample` becomes one `ee.Feature` with the same geometry
  and properties (class_label, color, creator, created_at, id) as the local
  record — so the two stay in lockstep.
- The running collection is kept as a plain Python list of `ee.Feature`
  objects in `st.session_state`, appended to one at a time. `ee.Feature(...)`
  and `ee.FeatureCollection([...])` are cheap client-side constructors (no
  server round-trip happens until the collection is actually evaluated, e.g.
  via `.getInfo()` or an export task) — so append-only + "wrap on demand"
  avoids rebuilding anything from scratch on every click.
"""

from __future__ import annotations

from typing import Any

import ee
import streamlit as st

_SESSION_KEY = "ts_ee_features"


def _feature_from_record(record: dict[str, Any]) -> ee.Feature:
    geometry = ee.Geometry(record["geometry"])
    props = {
        "id": record["id"],
        "class_label": record["class_label"],
        "color": record.get("color") or "#0F6E4F",
        "creator": record.get("creator", ""),
        "created_at": record.get("created_at", ""),
        "source_filename": record.get("source_filename", ""),
    }
    return ee.Feature(geometry, props)


def ensure_session_synced(records: list[dict[str, Any]]) -> None:
    """Rebuild the session's ee.Feature list from persisted records exactly
    once per session (or whenever the persisted count changes underneath us,
    e.g. a sample was deleted) — after that, `add_feature` appends only."""
    features = st.session_state.get(_SESSION_KEY)
    tracked_ids = st.session_state.get(f"{_SESSION_KEY}_ids")
    current_ids = [r["id"] for r in records]

    if features is None or tracked_ids != current_ids:
        st.session_state[_SESSION_KEY] = [_feature_from_record(r) for r in records]
        st.session_state[f"{_SESSION_KEY}_ids"] = current_ids


def add_feature(record: dict[str, Any]) -> None:
    """Append one new sample to the running ee.FeatureCollection without
    touching or re-wrapping the rest."""
    features: list[ee.Feature] = st.session_state.setdefault(_SESSION_KEY, [])
    features.append(_feature_from_record(record))
    ids: list[str] = st.session_state.setdefault(f"{_SESSION_KEY}_ids", [])
    ids.append(record["id"])


def get_feature_collection() -> ee.FeatureCollection | None:
    """Wrap the current session's feature list as an ee.FeatureCollection.
    Returns None if nothing has been synced yet."""
    features = st.session_state.get(_SESSION_KEY)
    if not features:
        return None
    return ee.FeatureCollection(features)


def feature_count() -> int:
    return len(st.session_state.get(_SESSION_KEY, []))
