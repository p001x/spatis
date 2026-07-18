"""Rwanda GeoPortal — Flask backend."""
import io
import json
import logging
import os
import threading
from typing import Optional

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from pydantic import BaseModel, Field, ValidationError

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
from reports.report_builder import build_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ── GEE state ───────────────────────────────────────────────────────────────
_gee_ready = False
_gee_error = None

def _init_gee_background() -> None:
    global _gee_ready, _gee_error
    try:
        initialize_gee()
        _gee_ready = True
        logger.info("GEE Initialization successful.")
    except Exception as exc:
        _gee_error = str(exc)
        logger.critical("GEE initialization failed: %s", exc)

def _require_gee():
    if _gee_error:
        return jsonify({"detail": f"GEE initialization failed: {_gee_error}"}), 503
    if not _gee_ready:
        return jsonify({"detail": "GEE is still initializing — please retry in ~30 seconds."}), 503
    return None

# ── App ──────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# Fallback to load secret if not in env
key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "").strip()
if not key:
    try:
        with open("backend/gee_key.json", "r") as f:
            content = f.read()
            os.environ["GEE_SERVICE_ACCOUNT_KEY"] = content.strip()
    except Exception:
        pass

logger.info("Starting GEE initialization in background thread…")
threading.Thread(target=_init_gee_background, daemon=True).start()

# ── Meta ─────────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    if _gee_error:
        return jsonify({"detail": _gee_error}), 503
    if not _gee_ready:
        return jsonify({"status": "initializing", "message": "GEE is starting up, retry in ~30 s"})
    return jsonify({"status": "ok", "version": "2.0.0"})

@app.route("/api/districts", methods=["GET"])
def get_districts():
    return jsonify({"districts": RWANDA_DISTRICTS})

# ── Models ─────────────────────────────────────────────────────────
class NDVIRequest(BaseModel):
    district: str
    start_date: str
    end_date: str
    n_classes: int = 5

class LSTRequest(BaseModel):
    district: str
    start_date: str
    end_date: str
    n_classes: int = 5

class RUSLERequest(BaseModel):
    district: str
    year: int = 2023
    n_classes: int = 5
    reverse_r: bool = False
    reverse_k: bool = False
    reverse_ls: bool = False
    reverse_c: bool = False
    reverse_p: bool = False

class SlopeRequest(BaseModel):
    district: str
    n_classes: int = 5

class LandfillRequest(BaseModel):
    district: str
    n_classes: int = 5
    reverse_river: bool = False
    reverse_residential: bool = False
    reverse_slope: bool = False
    reverse_road: bool = False
    reverse_lulc: bool = False
    custom_weights: Optional[dict] = None

class AirPollutionRequest(BaseModel):
    district: str
    start_date: str
    end_date: str
    n_classes: int = 5

class LandslideRequest(BaseModel):
    district: str
    start_year: int = 2015
    end_year: int = 2024
    n_classes: int = 5

class UHIRequest(BaseModel):
    district: str
    start_date: str
    end_date: str
    grid_size: int = 6

class ReportRequest(BaseModel):
    module_name: str
    district: str
    date_range: str
    stats: dict
    class_areas: dict
    extra_notes: str = ""

# ── Analysis Endpoints ─────────────────────────────────────────────────────────

@app.route("/api/report", methods=["POST"])
def generate_report():
    try:
        req = ReportRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    
    try:
        pdf_bytes = build_report(
            module_name=req.module_name,
            district=req.district,
            date_range=req.date_range,
            stats=req.stats,
            class_areas=req.class_areas,
            extra_notes=req.extra_notes,
        )
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={req.module_name.replace(' ', '_')}_Report.pdf"}
        )
    except Exception as e:
        logger.exception("Report generation failed")
        return jsonify({"detail": str(e)}), 500

@app.route("/api/ndvi", methods=["POST"])
def ndvi_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = NDVIRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_ndvi(req.district, req.start_date, req.end_date, req.n_classes)
        return jsonify(res)
    except Exception as exc:
        logger.exception("NDVI failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/lst", methods=["POST"])
def lst_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = LSTRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_lst(req.district, req.start_date, req.end_date, req.n_classes)
        return jsonify(res)
    except Exception as exc:
        logger.exception("LST failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/rusle", methods=["POST"])
def rusle_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = RUSLERequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_rusle(
            req.district, req.year, req.n_classes,
            req.reverse_r, req.reverse_k, req.reverse_ls, req.reverse_c, req.reverse_p
        )
        return jsonify(res)
    except Exception as exc:
        logger.exception("RUSLE failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/slope", methods=["POST"])
def slope_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = SlopeRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_slope(req.district, req.n_classes)
        return jsonify(res)
    except Exception as exc:
        logger.exception("Slope failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/landfill", methods=["POST"])
def landfill_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = LandfillRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_landfill_suitability(
            req.district, req.reverse_river, req.reverse_residential,
            req.reverse_slope, req.reverse_road, req.reverse_lulc, req.n_classes,
            custom_weights=req.custom_weights
        )
        return jsonify(res)
    except Exception as exc:
        logger.exception("Landfill failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/air-pollution", methods=["POST"])
def air_pollution_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = AirPollutionRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_no2(req.district, req.start_date, req.end_date, req.n_classes)
        return jsonify(res)
    except Exception as exc:
        logger.exception("Air pollution failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/landslide", methods=["POST"])
def landslide_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = LandslideRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_landslide_susceptibility(req.district, req.start_year, req.end_year, req.n_classes)
        return jsonify(res)
    except Exception as exc:
        logger.exception("Landslide failed")
        return jsonify({"detail": str(exc)}), 500

@app.route("/api/uhi", methods=["POST"])
def uhi_endpoint():
    err = _require_gee()
    if err: return err
    try:
        req = UHIRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
    if req.district not in RWANDA_DISTRICTS:
        return jsonify({"detail": f"Unknown district '{req.district}'."}), 400
    try:
        res = compute_uhi(req.district, req.start_date, req.end_date, req.grid_size)
        return jsonify(res)
    except Exception as exc:
        logger.exception("UHI failed")
        return jsonify({"detail": str(exc)}), 500

# ── RARE DATA — Dataset Repository ─────────────────────────────────────────

@app.route("/api/datasets", methods=["GET"])
def list_datasets():
    source = request.args.get("source", "admin")
    if source not in ("admin", "community"):
        return jsonify({"detail": "Invalid source"}), 400
    return jsonify({"records": load_metadata(source=source)})

@app.route("/api/datasets/upload", methods=["POST"])
def upload_dataset():
    source = request.form.get("source", "admin")
    if source not in ("admin", "community"):
        return jsonify({"detail": "source must be 'admin' or 'community'"}), 400
    
    file = request.files.get("file")
    if not file:
        return jsonify({"detail": "file missing"}), 400
        
    name = request.form.get("name")
    if not name:
        return jsonify({"detail": "name missing"}), 400
        
    description = request.form.get("description", "")
    contributor = request.form.get("contributor")
    
    file_bytes = file.read()
    record = process_and_store_upload(
        filename=file.filename or "upload",
        file_bytes=file_bytes,
        name=name,
        description=description,
        source=source,
        contributor=contributor,
    )
    return jsonify(record.to_dict())

class DatasetLinkRequest(BaseModel):
    url: str
    name: str
    description: str = ""
    source: str = "admin"
    contributor: Optional[str] = None

@app.route("/api/datasets/link", methods=["POST"])
def add_dataset_link():
    try:
        req = DatasetLinkRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
        
    if req.source not in ("admin", "community"):
        return jsonify({"detail": "source must be 'admin' or 'community'"}), 400
        
    record = process_and_store_link(
        url=req.url, name=req.name, description=req.description,
        source=req.source, contributor=req.contributor,
    )
    return jsonify(record.to_dict())

@app.route("/api/datasets/<dataset_id>/download", methods=["GET"])
def download_dataset(dataset_id):
    source = request.args.get("source", "admin")
    records = load_metadata(source=source)
    record = next((r for r in records if r["id"] == dataset_id), None)
    if record is None:
        return jsonify({"detail": "Dataset not found"}), 404
    try:
        file_bytes = download_dataset_bytes(record["storage_key"])
    except Exception as exc:
        return jsonify({"detail": f"Could not fetch file: {exc}"}), 500
    
    return Response(
        file_bytes,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{record.get("original_filename", "download")}"'}
    )

@app.route("/api/datasets/<dataset_id>", methods=["DELETE"])
def delete_dataset(dataset_id):
    source = request.args.get("source", "admin")
    ok = delete_record(dataset_id, source=source)
    if not ok:
        return jsonify({"detail": "Dataset not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/datasets/download-all", methods=["GET"])
def download_all_datasets():
    source = request.args.get("source", "admin")
    records = load_metadata(source=source)
    zip_bytes = build_zip_of_datasets(records)
    return Response(
        zip_bytes,
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{source}_all_datasets.zip"'}
    )

# ── Admin auth ──────────────────────────────────────────────────────────────

class AdminVerifyRequest(BaseModel):
    password: str

@app.route("/api/admin/verify", methods=["POST"])
def admin_verify():
    try:
        req = AdminVerifyRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
        
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password or req.password != admin_password:
        return jsonify({"detail": "Incorrect password"}), 401
    return jsonify({"ok": True})

# ── Sample Digitization ─────────────────────────────────────────────────────

class SampleCreateRequest(BaseModel):
    geometry: dict
    class_label: str
    source_filename: str = "manual"
    source_url: str = ""
    creator: str = "anonymous"
    color: str = "#0F6E4F"

@app.route("/api/samples", methods=["GET"])
def list_samples():
    return jsonify({"samples": load_samples()})

@app.route("/api/samples", methods=["POST"])
def create_sample():
    try:
        req = SampleCreateRequest(**request.json)
    except ValidationError as e:
        return jsonify(e.errors()), 400
        
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
    res = add_sample(sample)
    return jsonify(res.dict() if hasattr(res, 'dict') else res)

@app.route("/api/samples/<sample_id>", methods=["DELETE"])
def delete_sample_endpoint(sample_id):
    ok = delete_sample(sample_id)
    if not ok:
        return jsonify({"detail": "Sample not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/samples/export/geojson", methods=["GET"])
def export_samples_geojson():
    records = load_samples()
    geojson = samples_to_geojson(records)
    return Response(
        json.dumps(geojson, indent=2),
        mimetype="application/geo+json",
        headers={"Content-Disposition": 'attachment; filename="training_samples.geojson"'}
    )

@app.route("/api/samples/push-to-gee", methods=["POST"])
def push_to_gee():
    err = _require_gee()
    if err: return err
    
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rwanda-geoportal'))
    
    file = request.files.get("file")
    if not file:
        return jsonify({"detail": "file missing"}), 400
        
    asset_name = request.form.get("asset_name")
    if not asset_name:
        return jsonify({"detail": "asset_name missing"}), 400
        
    filename = file.filename or "upload"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    is_raster = ext in {"tif", "tiff"}
    
    file_bytes = file.read()
    
    try:
        if is_raster:
            from gee_scripts.gee_asset_upload import push_raster_to_gee
            result = push_raster_to_gee(file_bytes, filename, asset_name)
            return jsonify({"asset_id": result.asset_id, "kind": "raster"})
        else:
            from gee_scripts.gee_vector_upload import push_vector_to_gee
            result = push_vector_to_gee(file_bytes, filename, asset_name)
            return jsonify({"asset_id": result.asset_id, "kind": "vector", "feature_count": result.feature_count})
    except Exception as exc:
        return jsonify({"detail": str(exc)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
