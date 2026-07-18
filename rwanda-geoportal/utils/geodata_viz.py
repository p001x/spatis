"""
RARE DATA — visualization + format conversion helpers.

- Renders any stored dataset (raster or vector) as a map layer + attribute table.
- Converts between formats:
    raster  -> vector polygons (rasterio.features.shapes)
    raster  -> points (regular sample grid)
    points  -> raster, via IDW or Ordinary Kriging interpolation
    lines   -> raster, via Euclidean distance from the nearest line
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from utils.dataset_storage import safe_extractall

_LAT_NAMES = {"lat", "latitude", "y"}
_LON_NAMES = {"lon", "lng", "longitude", "x"}


# ---------------------------------------------------------------------------
# Loading vector data into GeoDataFrames
# ---------------------------------------------------------------------------

def load_shapefile_gdf(zip_bytes: bytes):
    import geopandas as gpd

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_zip = Path(tmpdir) / "in.zip"
        tmp_zip.write_bytes(zip_bytes)
        with zipfile.ZipFile(tmp_zip) as zf:
            safe_extractall(zf, tmpdir)
        shp_files = list(Path(tmpdir).glob("**/*.shp"))
        if not shp_files:
            raise ValueError("No .shp file found inside this zip.")
        gdf = gpd.read_file(shp_files[0])
        if gdf.crs is not None and str(gdf.crs) != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf


def csv_to_points_gdf(file_bytes: bytes):
    import geopandas as gpd

    df = pd.read_csv(io.BytesIO(file_bytes))
    cols_lower = {c.lower(): c for c in df.columns}
    lat_col = next((cols_lower[n] for n in _LAT_NAMES if n in cols_lower), None)
    lon_col = next((cols_lower[n] for n in _LON_NAMES if n in cols_lower), None)
    if lat_col is None or lon_col is None:
        raise ValueError("No latitude/longitude columns found in this CSV.")

    df = df.copy()
    df["_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["_lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=["_lat", "_lon"])
    if df.empty:
        raise ValueError("No valid coordinate rows in this CSV.")

    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["_lon"], df["_lat"]), crs="EPSG:4326")
    return gdf.drop(columns=["_lat", "_lon"])


def numeric_columns(df) -> list[str]:
    return [c for c in df.columns if c != "geometry" and pd.api.types.is_numeric_dtype(df[c])]


# ---------------------------------------------------------------------------
# Raster preview + stats
# ---------------------------------------------------------------------------

MAX_PREVIEW_DIM = 1024  # downsample preview rendering so huge rasters can't stall the app
MAX_EXACT_STATS_PIXELS = 25_000_000  # above this, band stats are computed from a decimated
# sample (see below) instead of reading every pixel, so multi-hundred-MB scenes still preview.
# No fixed pixel cap: the decimated read keeps memory bounded by the *output* window
# (MAX_EXACT_STATS_PIXELS / MAX_PREVIEW_DIM), regardless of source raster size — only GDAL's
# own limits (~2^31 pixels per dimension), disk/RAM, and wall-clock time bound how large a
# scene can load; a MemoryError during the read is caught and reported below.


def _stride_downsample(arr: np.ma.MaskedArray, target_h: int, target_w: int) -> np.ma.MaskedArray:
    """Cheap in-memory downsample by index-striding (no resampling math) — used to derive a
    smaller array from one already read from disk, instead of issuing a second GDAL read."""
    h, w = arr.shape
    if h <= target_h and w <= target_w:
        return arr
    row_idx = np.linspace(0, h - 1, target_h).astype(np.intp)
    col_idx = np.linspace(0, w - 1, target_w).astype(np.intp)
    return arr[np.ix_(row_idx, col_idx)]


def raster_preview(file_bytes: bytes) -> tuple[bytes, list[float], pd.DataFrame]:
    """Returns (png_overlay_bytes, bbox_wgs84, band_stats_df).

    Both the band stats and the visual preview are read via a decimated (resampled) window
    rather than the full raster, so this scales to large scenes without loading every pixel
    into memory. For rasters at/under MAX_EXACT_STATS_PIXELS, stats are exact (every pixel);
    above that, stats are computed from a representative decimated sample and the dataframe
    says so via a `sampled` column — an honest approximation, not a silent one.

    Speed: decimated reads use nearest-neighbor resampling (GDAL can skip straight to the
    needed source pixels/blocks instead of decompressing and averaging every one — an order
    of magnitude faster on huge rasters), and band 1 is only read from disk once — the smaller
    preview-resolution array is derived from the stats-resolution array already in memory via
    cheap index-striding rather than a second GDAL scan.
    """
    import matplotlib.cm as cm
    import rasterio
    from PIL import Image
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds

    with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        with rasterio.open(tmp.name) as src:
            pixels = src.width * src.height
            sampled = pixels > MAX_EXACT_STATS_PIXELS
            if sampled:
                stats_scale = (MAX_EXACT_STATS_PIXELS / pixels) ** 0.5
                stats_h = max(1, int(src.height * stats_scale))
                stats_w = max(1, int(src.width * stats_scale))
            else:
                stats_h, stats_w = src.height, src.width

            preview_scale = min(1.0, MAX_PREVIEW_DIM / max(src.width, src.height))
            preview_h = max(1, int(src.height * preview_scale))
            preview_w = max(1, int(src.width * preview_scale))

            try:
                stats_rows = []
                band1_raw = None
                for i in range(1, src.count + 1):
                    if sampled:
                        band = src.read(
                            i, masked=True, out_shape=(stats_h, stats_w), resampling=Resampling.nearest
                        )
                    else:
                        band = src.read(i, masked=True)
                    if i == 1:
                        band1_raw = band
                    valid = band.compressed()
                    stats_rows.append({
                        "band": i,
                        "min": float(valid.min()) if valid.size else None,
                        "max": float(valid.max()) if valid.size else None,
                        "mean": float(valid.mean()) if valid.size else None,
                        "std": float(valid.std()) if valid.size else None,
                        "valid_pixels": int(valid.size),
                        "sampled": sampled,
                    })
                stats_df = pd.DataFrame(stats_rows)

                band1 = _stride_downsample(band1_raw, preview_h, preview_w).astype("float64")
            except MemoryError as e:
                raise ValueError(
                    f"This raster is {src.width}x{src.height} ({pixels:,} pixels) — reading it "
                    "ran out of memory even at a decimated resolution. This scene is likely too "
                    "large for this app's available memory; try a downsampled raster."
                ) from e
            valid = band1.compressed()
            vmin, vmax = (float(valid.min()), float(valid.max())) if valid.size else (0.0, 1.0)
            span = (vmax - vmin) or 1.0
            norm = np.clip((band1.filled(vmin) - vmin) / span, 0, 1)
            rgba = (cm.viridis(norm) * 255).astype("uint8")
            alpha_mask = (~band1.mask).astype("uint8") * 255 if np.ma.is_masked(band1) else np.full(band1.shape, 255, "uint8")
            rgba[..., 3] = alpha_mask

            img = Image.fromarray(rgba, mode="RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")

            bounds = src.bounds
            if src.crs is not None and str(src.crs) != "EPSG:4326":
                minx, miny, maxx, maxy = transform_bounds(src.crs, "EPSG:4326", *bounds)
            else:
                minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top

            return buf.getvalue(), [minx, miny, maxx, maxy], stats_df


# ---------------------------------------------------------------------------
# Raster -> Vector / Points
# ---------------------------------------------------------------------------

MAX_POLYGONIZE_FEATURES = 20000
MAX_RASTER_PIXELS = 25_000_000  # ~5000x5000 — this is a real limit for raster_to_vector only:
# polygonizing preserves per-pixel identity, so it must read (and can produce polygons from)
# every pixel at full resolution. Preview and raster_to_points no longer need this — they
# read a decimated window instead — so this cap is intentionally narrower in scope now.


def _check_raster_size(src) -> None:
    pixels = src.width * src.height
    if pixels > MAX_RASTER_PIXELS:
        raise ValueError(
            f"This raster is {src.width}x{src.height} ({pixels:,} pixels), exceeding the "
            f"{MAX_RASTER_PIXELS:,} pixel cap for vector conversion (polygonizing needs every "
            "pixel at full resolution). Use a downsampled raster, or use 'Convert to Points' "
            "instead, which supports large rasters."
        )


def raster_to_vector(file_bytes: bytes):
    """Polygonize a single-band raster into a GeoDataFrame of polygons with a `value` column."""
    import geopandas as gpd
    import rasterio
    from rasterio.features import shapes

    with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        with rasterio.open(tmp.name) as src:
            _check_raster_size(src)
            band = src.read(1)
            mask = band != src.nodata if src.nodata is not None else None
            features = []
            for geom, v in shapes(band, mask=mask, transform=src.transform):
                features.append({"properties": {"value": float(v)}, "geometry": geom})
                if len(features) > MAX_POLYGONIZE_FEATURES:
                    raise ValueError(
                        f"This raster would produce more than {MAX_POLYGONIZE_FEATURES} polygons. "
                        "Use a coarser raster."
                    )
            if not features:
                raise ValueError("No polygon features could be extracted from this raster.")
            gdf = gpd.GeoDataFrame.from_features(features, crs=src.crs)
            if src.crs is not None and str(src.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
    return gdf


def raster_to_points(file_bytes: bytes, max_points: int = 3000):
    """Sample a single-band raster on a regular grid, capped at `max_points`.

    Reads a decimated (resampled) window sized to roughly `max_points` cells rather than
    reading the full raster and then striding over it, so this scales to large scenes
    without loading every pixel into memory.
    """
    import geopandas as gpd
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from shapely.geometry import Point

    with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        with rasterio.open(tmp.name) as src:
            pixels = src.width * src.height
            side = max(1, int(round(max_points ** 0.5)))
            out_h, out_w = min(src.height, side), min(src.width, side)
            try:
                band = src.read(1, masked=True, out_shape=(out_h, out_w), resampling=Resampling.nearest)
            except MemoryError as e:
                raise ValueError(
                    f"This raster is {src.width}x{src.height} ({pixels:,} pixels) — reading it "
                    "ran out of memory even at a decimated resolution. This scene is likely too "
                    "large for this app's available memory; try a downsampled raster."
                ) from e
            out_transform = from_bounds(*src.bounds, out_w, out_h)

            records = []
            rows, cols = band.shape
            for r in range(rows):
                for c in range(cols):
                    val = band[r, c]
                    if np.ma.is_masked(val):
                        continue
                    x, y = rasterio.transform.xy(out_transform, r, c)
                    records.append({"value": float(val), "geometry": Point(x, y)})
            if not records:
                raise ValueError("No valid (non-nodata) pixels found to sample.")
            gdf = gpd.GeoDataFrame(records, crs=src.crs)
            if src.crs is not None and str(src.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
    return gdf


# ---------------------------------------------------------------------------
# Points -> Raster (IDW / Kriging), Lines -> Raster (Euclidean distance)
# ---------------------------------------------------------------------------

def _padded_bounds(gdf, pad_frac: float = 0.05):
    minx, miny, maxx, maxy = gdf.total_bounds
    pad_x = (maxx - minx) * pad_frac or 0.01
    pad_y = (maxy - miny) * pad_frac or 0.01
    return minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y


def _grid_transform(minx, miny, maxx, maxy, resolution):
    from affine import Affine

    transform = Affine.translation(minx, maxy) * Affine.scale(
        (maxx - minx) / resolution, -(maxy - miny) / resolution
    )
    return transform


MAX_INTERPOLATION_POINTS = 5000
IDW_K_NEIGHBORS = 12  # cap neighbors considered per grid cell to bound memory/CPU


def idw_interpolate(gdf, value_col: str, resolution: int = 100, power: float = 2.0):
    """Inverse Distance Weighting interpolation of point values onto a regular grid.

    Uses a k-nearest-neighbors search (not a full dense distance matrix) so memory/CPU
    stay bounded regardless of point count or grid resolution.
    """
    from scipy.spatial import cKDTree

    coords = np.column_stack([gdf.geometry.x.values, gdf.geometry.y.values])
    values = pd.to_numeric(gdf[value_col], errors="coerce").values
    valid = ~np.isnan(values)
    coords, values = coords[valid], values[valid]
    if len(values) < 2:
        raise ValueError("Need at least 2 points with valid values to interpolate.")
    if len(values) > MAX_INTERPOLATION_POINTS:
        raise ValueError(
            f"{len(values)} points exceeds the {MAX_INTERPOLATION_POINTS} point cap for interpolation."
        )

    minx, miny, maxx, maxy = _padded_bounds(gdf)
    transform = _grid_transform(minx, miny, maxx, maxy, resolution)

    xs = np.linspace(minx + (maxx - minx) / (2 * resolution), maxx - (maxx - minx) / (2 * resolution), resolution)
    ys = np.linspace(maxy - (maxy - miny) / (2 * resolution), miny + (maxy - miny) / (2 * resolution), resolution)
    xx, yy = np.meshgrid(xs, ys)
    grid_points = np.column_stack([xx.ravel(), yy.ravel()])

    k = min(IDW_K_NEIGHBORS, len(values))
    tree = cKDTree(coords)
    dists, idxs = tree.query(grid_points, k=k)
    if k == 1:  # cKDTree squeezes the last axis when k=1
        dists = dists[:, None]
        idxs = idxs[:, None]
    dists = np.where(dists == 0, 1e-10, dists)
    weights = 1.0 / (dists ** power)
    neighbor_vals = values[idxs]
    z = (weights * neighbor_vals).sum(axis=1) / weights.sum(axis=1)

    array = z.reshape(resolution, resolution).astype("float32")
    return array, transform


def kriging_interpolate(gdf, value_col: str, resolution: int = 100, variogram_model: str = "linear"):
    """Ordinary Kriging interpolation via pykrige. Falls back to IDW if kriging fails."""
    from pykrige.ok import OrdinaryKriging

    x = gdf.geometry.x.values
    y = gdf.geometry.y.values
    z = pd.to_numeric(gdf[value_col], errors="coerce").values
    valid = ~np.isnan(z)
    x, y, z = x[valid], y[valid], z[valid]
    if len(z) < 3:
        raise ValueError("Need at least 3 points with valid values for kriging.")
    if len(z) > MAX_INTERPOLATION_POINTS:
        raise ValueError(
            f"{len(z)} points exceeds the {MAX_INTERPOLATION_POINTS} point cap for kriging. Try IDW instead."
        )

    minx, miny, maxx, maxy = _padded_bounds(gdf)
    gridx = np.linspace(minx, maxx, resolution)
    gridy = np.linspace(miny, maxy, resolution)

    try:
        ok = OrdinaryKriging(x, y, z, variogram_model=variogram_model, verbose=False, enable_plotting=False)
        zgrid, _ = ok.execute("grid", gridx, gridy)
        array = np.asarray(zgrid)[::-1, :].astype("float32")  # flip to north-up row order
    except Exception as e:  # noqa: BLE001 - surface a clear message, let caller decide to fall back
        raise RuntimeError(f"Kriging failed ({e}). Try IDW instead or use more points.") from e

    transform = _grid_transform(minx, miny, maxx, maxy, resolution)
    return array, transform


def euclidean_distance_raster(gdf_lines, resolution: int = 100):
    """Rasterize lines and compute per-cell Euclidean distance to the nearest line."""
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt

    minx, miny, maxx, maxy = _padded_bounds(gdf_lines)
    transform = _grid_transform(minx, miny, maxx, maxy, resolution)

    shapes_iter = [(geom, 1) for geom in gdf_lines.geometry if geom is not None]
    if not shapes_iter:
        raise ValueError("No valid line geometries to rasterize.")

    mask = rasterize(
        shapes_iter, out_shape=(resolution, resolution), transform=transform, fill=0, all_touched=True
    )
    pixel_dist = distance_transform_edt(mask == 0)

    px_w = (maxx - minx) / resolution
    px_h = (maxy - miny) / resolution
    array = (pixel_dist * ((px_w + px_h) / 2)).astype("float32")
    return array, transform


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def array_to_geotiff_bytes(array: np.ndarray, transform, crs: str = "EPSG:4326") -> bytes:
    import rasterio

    fd, path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    try:
        with rasterio.open(
            path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
            count=1, dtype="float32", crs=crs, transform=transform, nodata=np.nan,
        ) as dst:
            dst.write(array.astype("float32"), 1)
        return Path(path).read_bytes()
    finally:
        os.remove(path)


def gdf_to_shapefile_zip(gdf) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = Path(tmpdir) / "output.shp"
        gdf.to_file(shp_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in Path(tmpdir).glob("output.*"):
                zf.write(f, arcname=f.name)
        return buf.getvalue()


def raster_array_to_png(array: np.ndarray) -> bytes:
    """Quick grayscale/viridis PNG preview of a float array (for interpolation/distance previews)."""
    import matplotlib.cm as cm
    from PIL import Image

    valid = array[~np.isnan(array)]
    vmin, vmax = (float(valid.min()), float(valid.max())) if valid.size else (0.0, 1.0)
    span = (vmax - vmin) or 1.0
    norm = np.clip((np.nan_to_num(array, nan=vmin) - vmin) / span, 0, 1)
    rgba = (cm.viridis(norm) * 255).astype("uint8")
    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
