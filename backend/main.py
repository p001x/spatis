"""Rwanda GeoPortal — FastAPI backend (all modules).

GEE is initialised in a background thread so uvicorn can bind the port
immediately. Endpoints return HTTP 503 while GEE is still starting up.
"""
import io
import json
import logging
import os
import threading
import zipfile
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from gee.auth import initialize_gee
from gee.ndvi import RWANDA_DISTRICTS, compute_ndvi
from gee.lst import compute_lst
from gee.rusle import compute_rusle
from gee.slope import compute_slope
from gee.landfill import compute_landfill_suitability
from gee.air_pollution import compute_no2
from gee.landslide import compute_landslide_susceptibility
from gee.uhi import compute_uhi

from storage.dataset_storage import (
    load_metadata, delete_record, download_dataset_bytes,
    process_and_store_upload, process_and_store_link,
    build_zip_of_datasets, datasets_intersecting,
)
from storage.samples_storage import (
    load_samples, add_sample, delete_sample, samples_to_geojson, TrainingSample,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── GEE state ───────────────────────────────────────────────────────────────

_gee_ready = False
_gee_error: str | None = None


def _init_gee_background() -> None:
    global _gee_ready, _gee_error
    try:
        initialize_gee()
        _gee_ready = True
    except Exception as exc:
        _gee_error = str(exc)
        logger.critical("GEE initialization failed: %s", exc)


def _require_gee() -> None:
    if _gee_error:
        raise HTTPException(status_code=503, detail=f"GEE initialization failed: {_gee_error}")
    if not _gee_ready:
        raise HTTPException(status_code=503, detail="GEE is still initializing — please retry in ~30 seconds.")


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "").strip()
    if not key:
        global _gee_error
        _gee_error = "GEE_SERVICE_ACCOUNT_KEY is not set — add it as a Replit Secret."
        logger.critical(_gee_error)
    else:
        logger.info("Starting GEE initialization in background thread…")
        t = threading.Thread(target=_init_gee_background, daemon=True)
        t.start()
    yield
    logger.info("GeoPortal API shutting down.")


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Rwanda Environmental GeoPortal API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ── Meta ─────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["meta"])
def health():
    if _gee_error:
        raise HTTPException(status_code=503, detail=_gee_error)
    if not _gee_ready:
        return {"status": "initializing", "message": "GEE is starting up, retry in ~30 s"}
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/districts", tags=["meta"])
def get_districts():
    return {"districts": RWANDA_DISTRICTS}


# ── Analysis models ──────────────────────────────────────────────────────────

class NDVIRequest(BaseModel):
    district: str = Field(..., examples=["Gasabo"])
    start_date: str = Field(..., examples=["2024-01-01"])
    end_date: str = Field(..., examples=["2024-06-30"])
    n_classes: int = Field(5, ge=2, le=10)


class LSTRequest(BaseModel):
    district: str = Field(..., examples=["Gasabo"])
    start_date: str = Field(..., examples=["2024-01-01"])
    end_date: str = Field(..., examples=["2024-06-30"])
    n_classes: int = Field(5, ge=2, le=10)


class RUSLERequest(BaseModel):
    district: str = Field(..., examples=["Huye"])
    year: int = Field(2023, ge=2018, le=2024)
    n_classes: int = Field(5, ge=2, le=10)
    reverse_r: bool = False
    reverse_k: bool = False
    reverse_ls: bool = False
    reverse_c: bool = False
    reverse_p: bool = False


class SlopeRequest(BaseModel):
    district: str = Field(..., examples=["Musanze"])
    n_classes: int = Field(5, ge=2, le=10)


class LandfillRequest(BaseModel):
    district: str = Field(..., examples=["Nyagatare"])
    n_classes: int = Field(5, ge=2, le=10)
    reverse_river: bool = False
    reverse_residential: bool = False
    reverse_slope: bool = False
    reverse_road: bool = False
    reverse_lulc: bool = False
    custom_weights: Optional[dict] = Field(
        None,
        description="Optional weight overrides e.g. {'river':0.4,'residential':0.2,'slope':0.2,'road':0.1,'lulc':0.1}. Values are normalized to sum to 1.",
    )


class AirPollutionRequest(BaseModel):
    district: str = Field(..., examples=["Nyarugenge"])
    start_date: str = Field(..., examples=["2023-01-01"])
    end_date: str = Field(..., examples=["2023-12-31"])
    n_classes: int = Field(5, ge=2, le=10)


class LandslideRequest(BaseModel):
    district: str = Field(..., examples=["Musanze"])
    start_year: int = Field(2015, ge=1981, le=2024)
    end_year: int = Field(2024, ge=1981, le=2024)
    n_classes: int = Field(5, ge=2, le=10)


class UHIRequest(BaseModel):
    district: str = Field(..., examples=["Kicukiro"])
    start_date: str = Field(..., examples=["2024-01-01"])
    end_date: str = Field(..., examples=["2024-06-30"])
    grid_size: int = Field(6, ge=3, le=12)


# ── Analysis endpoints ───────────────────────────────────────────────────────

@app.post("/api/ndvi", tags=["analysis"])
def ndvi_endpoint(req: NDVIRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_ndvi(req.district, req.start_date, req.end_date, req.n_classes)
    except Exception as exc:
        logger.exception("NDVI failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/lst", tags=["analysis"])
def lst_endpoint(req: LSTRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_lst(req.district, req.start_date, req.end_date, req.n_classes)
    except Exception as exc:
        logger.exception("LST failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/rusle", tags=["analysis"])
def rusle_endpoint(req: RUSLERequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_rusle(
            req.district, req.year, req.n_classes,
            req.reverse_r, req.reverse_k, req.reverse_ls, req.reverse_c, req.reverse_p,
        )
    except Exception as exc:
        logger.exception("RUSLE failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/slope", tags=["analysis"])
def slope_endpoint(req: SlopeRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_slope(req.district, req.n_classes)
    except Exception as exc:
        logger.exception("Slope failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/landfill", tags=["analysis"])
def landfill_endpoint(req: LandfillRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_landfill_suitability(
            req.district, req.reverse_river, req.reverse_residential,
            req.reverse_slope, req.reverse_road, req.reverse_lulc, req.n_classes,
            custom_weights=req.custom_weights,
        )
    except Exception as exc:
        logger.exception("Landfill failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/air-pollution", tags=["analysis"])
def air_pollution_endpoint(req: AirPollutionRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_no2(req.district, req.start_date, req.end_date, req.n_classes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Air pollution failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/landslide", tags=["analysis"])
def landslide_endpoint(req: LandslideRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_landslide_susceptibility(
            req.district, req.start_year, req.end_year, req.n_classes
        )
    except Exception as exc:
        logger.exception("Landslide failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/uhi", tags=["analysis"])
def uhi_endpoint(req: UHIRequest):
    _require_gee()
    if req.district not in RWANDA_DISTRICTS:
        raise HTTPException(400, f"Unknown district '{req.district}'.")
    try:
        return compute_uhi(req.district, req.start_date, req.end_date, req.grid_size)
    except Exception as exc:
        logger.exception("UHI failed for %s", req.district)
        raise HTTPException(500, str(exc)) from exc


# ── RARE DATA — Dataset Repository ─────────────────────────────────────────

@app.get("/api/datasets", tags=["rare-data"])
def list_datasets(source: str = Query("admin", pattern="^(admin|community)$")):
    return {"records": load_metadata(source=source)}


@app.post("/api/datasets/upload", tags=["rare-data"])
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    source: str = Form("admin"),
    contributor: Optional[str] = Form(None),
):
    if source not in ("admin", "community"):
        raise HTTPException(400, "source must be 'admin' or 'community'")
    file_bytes = await file.read()
    record = process_and_store_upload(
        filename=file.filename or "upload",
        file_bytes=file_bytes,
        name=name,
        description=description,
        source=source,
        contributor=contributor,
    )
    return record.to_dict()


class DatasetLinkRequest(BaseModel):
    url: str
    name: str
    description: str = ""
    source: str = "admin"
    contributor: Optional[str] = None


@app.post("/api/datasets/link", tags=["rare-data"])
def add_dataset_link(req: DatasetLinkRequest):
    if req.source not in ("admin", "community"):
        raise HTTPException(400, "source must be 'admin' or 'community'")
    record = process_and_store_link(
        url=req.url, name=req.name, description=req.description,
        source=req.source, contributor=req.contributor,
    )
    return record.to_dict()


@app.get("/api/datasets/{dataset_id}/download", tags=["rare-data"])
def download_dataset(dataset_id: str, source: str = Query("admin", pattern="^(admin|community)$")):
    records = load_metadata(source=source)
    record = next((r for r in records if r["id"] == dataset_id), None)
    if record is None:
        raise HTTPException(404, "Dataset not found")
    try:
        file_bytes = download_dataset_bytes(record["storage_key"])
    except Exception as exc:
        raise HTTPException(500, f"Could not fetch file: {exc}") from exc
    return Response(
        content=file_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{record["original_filename"]}"'},
    )


@app.delete("/api/datasets/{dataset_id}", tags=["rare-data"])
def delete_dataset(dataset_id: str, source: str = Query("admin", pattern="^(admin|community)$")):
    ok = delete_record(dataset_id, source=source)
    if not ok:
        raise HTTPException(404, "Dataset not found")
    return {"ok": True}


@app.get("/api/datasets/download-all", tags=["rare-data"])
def download_all_datasets(source: str = Query("admin", pattern="^(admin|community)$")):
    records = load_metadata(source=source)
    zip_bytes = build_zip_of_datasets(records)
    return Response(
        content=zip_bytes, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{source}_all_datasets.zip"'},
    )


# ── Admin auth ──────────────────────────────────────────────────────────────

class AdminVerifyRequest(BaseModel):
    password: str


@app.post("/api/admin/verify", tags=["admin"])
def admin_verify(req: AdminVerifyRequest):
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password or req.password != admin_password:
        raise HTTPException(401, "Incorrect password")
    return {"ok": True}


# ── Sample Digitization ─────────────────────────────────────────────────────

class SampleCreateRequest(BaseModel):
    geometry: dict
    class_label: str
    source_filename: str = "manual"
    source_url: str = ""
    creator: str = "anonymous"
    color: str = "#0F6E4F"


@app.get("/api/samples", tags=["samples"])
def list_samples():
    return {"samples": load_samples()}


@app.post("/api/samples", tags=["samples"])
def create_sample(req: SampleCreateRequest):
    import uuid as _uuid
    sample = TrainingSample(
        id=_uuid.uuid4().hex,
        geometry=req.geometry,
        class_label=req.class_label,
        source_filename=req.source_filename,
        source_url=req.source_url,
        creator=req.creator,
        color=req.color,
    )
    return add_sample(sample)


@app.delete("/api/samples/{sample_id}", tags=["samples"])
def delete_sample_endpoint(sample_id: str):
    ok = delete_sample(sample_id)
    if not ok:
        raise HTTPException(404, "Sample not found")
    return {"ok": True}


@app.get("/api/samples/export/geojson", tags=["samples"])
def export_samples_geojson():
    records = load_samples()
    geojson = samples_to_geojson(records)
    return Response(
        content=json.dumps(geojson, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": 'attachment; filename="training_samples.geojson"'},
    )


@app.post("/api/samples/push-to-gee", tags=["samples"])
async def push_to_gee(
    file: UploadFile = File(...),
    asset_name: str = Form(...),
):
    """Push a raster or vector file to GEE as a permanent asset."""
    _require_gee()
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', 'rwanda-geoportal'))

    file_bytes = await file.read()
    filename = file.filename or "upload"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    is_raster = ext in {"tif", "tiff"}

    try:
        if is_raster:
            from gee_scripts.gee_asset_upload import push_raster_to_gee, AssetUploadError
            result = push_raster_to_gee(file_bytes, filename, asset_name)
            return {"asset_id": result.asset_id, "kind": "raster"}
        else:
            from gee_scripts.gee_vector_upload import push_vector_to_gee, AssetUploadError
            result = push_vector_to_gee(file_bytes, filename, asset_name)
            return {"asset_id": result.asset_id, "kind": "vector", "feature_count": result.feature_count}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
