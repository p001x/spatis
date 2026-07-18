"""GEE authentication — no Streamlit dependency."""
import os
import json
import logging
import ee

logger = logging.getLogger(__name__)
_initialized = False


def initialize_gee() -> None:
    """Initialize the Earth Engine API using the service account key from env.

    Safe to call multiple times — subsequent calls are no-ops.
    Raises RuntimeError on any configuration problem so the caller can decide
    how to surface the error (e.g. FastAPI startup failure).
    """
    global _initialized
    if _initialized:
        return

    key_json = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "").strip()

    if not key_json:
        raise RuntimeError(
            "GEE_SERVICE_ACCOUNT_KEY environment variable is not set. "
            "Add the full JSON of your service account key as a Replit Secret."
        )

    if not key_json.startswith("{"):
        raise RuntimeError(
            f"GEE_SERVICE_ACCOUNT_KEY does not look like JSON "
            f"(starts with: {key_json[:40]!r}). "
            "Paste the entire contents of the downloaded .json key file."
        )

    try:
        key_data = json.loads(key_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GEE_SERVICE_ACCOUNT_KEY is not valid JSON: {exc}") from exc

    credentials = ee.ServiceAccountCredentials(
        email=key_data["client_email"],
        key_data=key_json,
    )
    ee.Initialize(credentials)
    _initialized = True
    logger.info("GEE initialized with service account: %s", key_data.get("client_email"))
