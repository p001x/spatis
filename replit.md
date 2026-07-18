# Rwanda Environmental GeoPortal

A satellite-powered environmental analysis platform for Rwanda. Built with a **FastAPI (Python) backend + React/Vite frontend** architecture, powered by Google Earth Engine.

---

## Architecture

```
backend/          FastAPI Python API — GEE analysis modules
  main.py         App entry, CORS, lifespan, all routes
  gee/auth.py     GEE service-account init (background thread)
  gee/ndvi.py     NDVI computation
  gee/lst.py      LST computation
  gee/rusle.py    RUSLE computation
  gee/slope.py    Slope computation
  gee/landfill.py Landfill suitability
  gee/air_pollution.py  NO₂ monitoring
  gee/landslide.py      Landslide susceptibility
  gee/uhi.py      Urban Heat Island
  storage/        Dataset & samples storage (Replit Object Storage)

artifacts/geoportal/   React + Vite frontend (port 5000)
  src/App.tsx           Layout + wouter router
  src/pages/            One page per analysis module (10 total)
  src/lib/api.ts        Typed fetch client (/api/* → FastAPI via Vite proxy)
  src/components/DistrictMap.tsx  Leaflet map with GEE tile overlay

rwanda-geoportal/  Original Streamlit app (preserved, NOT running)
```

---

## Workflows

| Workflow | Command | Port |
|---|---|---|
| `GeoPortal API (FastAPI)` | `cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8001` | 8001 |
| `artifacts/geoportal: web` | `cd artifacts/geoportal && PORT=5000 BASE_PATH=/ npx vite --config vite.config.ts --host 0.0.0.0 --port 5000` | 5000 (preview) |

The Vite dev server proxies `/api/*` → `http://localhost:8001` (FastAPI backend).

---

## Required Secrets

| Secret | Description |
|---|---|
| `GEE_SERVICE_ACCOUNT_KEY` | Full JSON of your GEE service account key |

GEE initializes in a background thread on startup — the port opens immediately. Endpoints return HTTP 503 while GEE warms up (~1–2 s). Without this secret the API starts but all analysis endpoints return 503.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness probe |
| `GET` | `/api/districts` | List of 30 Rwanda districts |
| `POST` | `/api/ndvi` | NDVI analysis |
| `POST` | `/api/lst` | Land Surface Temperature |
| `POST` | `/api/rusle` | Soil Erosion (RUSLE) |
| `POST` | `/api/slope` | Slope / Topography |
| `POST` | `/api/landfill` | Landfill site suitability |
| `POST` | `/api/air-pollution` | NO₂ Air Pollution |
| `POST` | `/api/landslide` | Landslide susceptibility |
| `POST` | `/api/uhi` | Urban Heat Island |

---

## Modules Status

| Module | Backend | Frontend |
|---|---|---|
| NDVI | ✅ | ✅ |
| LST | ✅ | ✅ |
| RUSLE | ✅ | ✅ |
| Slope | ✅ | ✅ |
| Landfill Siting | ✅ | ✅ |
| Air Pollution (NO₂) | ✅ | ✅ |
| Landslide Susceptibility | ✅ | ✅ |
| UHI | ✅ | ✅ |
| RARE DATA | ✅ | ✅ |
| Sample Digitization | ✅ | ✅ |

---

## Notes

- GEE service account: `geoportalservices@ee-petersonyang87.iam.gserviceaccount.com`
- Sentinel-5P NO₂ data is only available from ~2018 onwards.
- The original Streamlit app lives in `rwanda-geoportal/` (preserved, not running).
