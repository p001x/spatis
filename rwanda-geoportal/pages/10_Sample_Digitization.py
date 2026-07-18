"""
Sample Digitization — import raster, vector, or points data from a link or a
local upload, and digitize labeled training samples on top of it.

Flow:
1. Import data one of two ways, both handling raster **and** vector/points:
   - Paste a link — a direct file URL, a Google Drive/Dropbox/OneDrive file
     link, an S3/GCS/Azure/GitHub URL, a shortened link, or a live GEE
     catalog ID. See utils/link_resolver.py for the full list of supported
     link formats.
   - Upload a local file. No practical size cap (see `.streamlit/config.toml`
     `maxUploadSize` and `utils/samples_storage.MAX_IMPORT_MB` — both raised
     to ~20 GB, bounded only by what actually fits, not an arbitrary limit).
   Supported formats: GeoTIFF/.tiff/.jp2/.img rasters, PNG/JPG images, a
   zipped Shapefile, GeoJSON, GeoPackage, KML vectors, and a lat/lon points
   CSV.
2. Geo-referenced data is shown as a map layer (raster overlay or vector/
   points GeoJSON layer); draw points/polygons on top and tag each with a
   class label to build a training-sample set.
3. Samples are saved to a shared catalog (Replit Object Storage) and can be
   downloaded as GeoJSON at any time.

What this page deliberately does NOT do (see utils/link_resolver.py for why):
- List images inside a Drive/Dropbox folder or Google Photos album (needs
  OAuth against that service's API).
- Resolve Gmail/Outlook attachment links, Box links, or Imgur/Flickr albums
  (same reason — needs OAuth/API access this project doesn't have).
- Fetch from WMS/WMTS/ArcGIS map *services* or SFTP (need rendering/creds
  beyond a single file download).

The "Upload → permanent GEE asset" tab pushes a local raster or vector file
into Earth Engine as a permanent asset (not just a page preview). It stages
the file in this app's own Object Storage bucket (no Google Cloud billing
needed on the Earth Engine project) and calls the real
`ee.data.startIngestion` / `ee.data.startTableIngestion` APIs — see
gee_scripts/gee_asset_upload.py and gee_scripts/gee_vector_upload.py.
"""

import base64
import uuid
from datetime import date, timedelta

import ee
import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from gee_scripts.auth import initialize_gee
from gee_scripts.context_layer import sentinel2_context_layer
from gee_scripts.gee_asset_upload import AssetUploadError, push_raster_to_gee
from gee_scripts.gee_image_import import GeeImportError, build_gee_composite, looks_like_gee_id, resolve_collection_id
from gee_scripts.gee_vector_upload import push_vector_to_gee
from gee_scripts.ndvi import RWANDA_DISTRICTS
from gee_scripts.sample_sync import add_feature, ensure_session_synced, feature_count, get_feature_collection
from utils.geodata_viz import raster_preview as _raster_preview
from utils.samples_export import ExportError, export_csv, export_kml, export_shapefile_zip, export_to_drive, export_to_gee_asset
from utils.samples_storage import (
    DEFAULT_SAMPLE_COLOR,
    LinkImportError,
    TrainingSample,
    add_sample,
    class_colors,
    default_color_for_class,
    delete_sample,
    detect_image_kind,
    load_samples,
    resolve_image_link,
    samples_to_geojson,
)
from utils.style import apply_style, material
from utils.vector_import import (
    VectorImportError,
    detect_data_kind,
    gdf_to_geojson_dict,
    geojson_bbox,
    geometry_type_summary,
    load_vector_gdf,
    load_vector_link,
)

initialize_gee()
apply_style()


@st.cache_data(show_spinner=False, max_entries=8)
def raster_preview(file_bytes: bytes):
    """Cached wrapper: Streamlit reruns this whole page on every map interaction
    (drawing a point/polygon), so without caching the same raster would be re-decoded
    from scratch on every click. Keyed on the file bytes themselves."""
    return _raster_preview(file_bytes)


st.title(":material/draw: Sample Digitization")
st.markdown(
    "Import **raster, vector, or points** data from a link or a local upload — GeoTIFF/"
    ".jp2/.img/.png/.jpg rasters, a zipped Shapefile, GeoJSON, GeoPackage, KML vectors, or a "
    "lat/lon points CSV — then digitize labeled training samples on top of it. No practical "
    "file-size limit (uploads and link downloads are capped at ~20 GB, not a small default)."
)
with st.expander("What's not supported here, and why"):
    st.markdown(
        "- **Drive/Dropbox folders, Google Photos albums** — listing files inside a folder/"
        "album needs that service's API with OAuth, which this project doesn't have "
        "configured. Paste one file's link at a time instead.\n"
        "- **Gmail/Outlook attachment links, Box links, Imgur/Flickr albums** — same reason: "
        "each needs OAuth or an API key this project doesn't have. For email, grab the Drive/"
        "Dropbox link inside the message body instead; for Box, download and re-host the file.\n"
        "- **WMS/WMTS/XYZ tiles/ArcGIS ImageServer** — these serve rendered tiles/layers on "
        "demand, not a single downloadable file.\n"
        "- **SFTP** — needs login credentials and an SFTP client; use FTP or HTTPS instead.\n"
        "- **A bare .shp with no sidecar files** — Shapefiles are multi-file formats (.shp/"
        ".dbf/.shx[/.prj]); zip them together first, then link/upload the .zip.\n"
        "- **Existing GEE catalog/asset IDs pasted into the link field above** are handled "
        "natively — paste one (e.g. `COPERNICUS/S2_SR_HARMONIZED`) to digitize on a live "
        "GEE composite instead of a downloaded file.\n"
        "- **Your own raster or vector becoming a permanent GEE asset** is a separate, "
        "heavier operation (Cloud Storage staging + Earth Engine ingestion) — use the "
        "**\"Upload → permanent GEE asset\"** tab in the sidebar for that, rather than the "
        "link field above."
    )

all_records = load_samples()
ensure_session_synced(all_records)
saved_class_colors = class_colors(all_records)

with st.sidebar:
    st.header("Analysis Controls")
    st.markdown("##### Import")
    tab_link, tab_upload = st.tabs(["Link / GEE ID", "Upload → permanent GEE asset"])

    with tab_link:
        link = st.text_input(
            "Data link or GEE dataset ID",
            placeholder="https://.../image.tif  —or—  .../data.geojson  —or—  COPERNICUS/S2_SR_HARMONIZED",
            help=(
                "Paste a downloadable raster (.tif/.jp2/.img/.png/.jpg), vector (.zip "
                "Shapefile/.geojson/.gpkg/.kml), or points (.csv) link — or a Google Earth "
                "Engine catalog ID (e.g. `COPERNICUS/S2_SR_HARMONIZED`, "
                "`LANDSAT/LC09/C02/T1_L2`) to digitize on top of a real, live GEE composite "
                "instead. No practical size limit on the download."
            ),
        )
        is_gee_mode = looks_like_gee_id(link)
        gee_district = "All Rwanda"
        gee_start_date = None
        gee_end_date = None
        if is_gee_mode:
            gee_district = st.selectbox("Area of interest", ["All Rwanda"] + RWANDA_DISTRICTS)
            col_start, col_end = st.columns(2)
            _today = date.today()
            with col_start:
                gee_start_date = st.date_input("From", value=_today - timedelta(days=180))
            with col_end:
                gee_end_date = st.date_input("To", value=_today)
        fetch = st.button(f"{material('cloud_download')} Fetch image", width='stretch', type="primary")

    with tab_upload:
        st.caption(
            "Upload your own raster **or** vector/points file to ingest it as a "
            "**permanent** Earth Engine asset, for further analysis in GEE — not just "
            "previewing here. No file-size cap beyond ~20 GB, and no Google Cloud billing "
            "needs to be enabled on your Earth Engine project for this."
        )
        upload_file = st.file_uploader(
            "Raster, vector, or points file",
            type=["tif", "tiff", "zip", "geojson", "json", "gpkg", "kml", "csv"],
            key="ts_asset_upload_file",
            help=(
                "Raster: .tif/.tiff (→ Earth Engine image asset). Vector/points: a zipped "
                "Shapefile, .geojson/.json, .gpkg, .kml, or a lat/lon .csv (→ Earth Engine "
                "table/FeatureCollection asset)."
            ),
        )
        asset_name_input = st.text_input(
            "Asset name",
            placeholder="e.g. my_2026_survey_raster",
            help="Becomes `projects/<your-gee-project>/assets/<this name>`.",
        )
        push_clicked = st.button(f"{material('cloud_upload')} Push to Earth Engine", width='stretch', type="primary")
        if push_clicked:
            if upload_file is None:
                st.error("Choose a file first.")
            elif not asset_name_input.strip():
                st.error("Give the asset a name first.")
            else:
                upload_kind = "tiff" if upload_file.name.lower().endswith((".tif", ".tiff")) else detect_data_kind(upload_file.name)
                if upload_kind is None:
                    st.error(f"`{upload_file.name}` isn't a recognized raster/vector/points format.")
                elif upload_kind == "tiff":
                    with st.spinner(
                        "Uploading and ingesting into Earth Engine — this can take a few minutes…"
                    ):
                        try:
                            ingested = push_raster_to_gee(
                                upload_file.getvalue(), upload_file.name, asset_name_input
                            )
                            st.success(
                                f"Ingested as `{ingested.asset_id}`. Paste that into the "
                                "\"Link / GEE ID\" tab above to load it, or reference it in "
                                "any other GEE-backed analysis page."
                            )
                        except AssetUploadError as e:
                            st.error(str(e))
                        except Exception as e:  # noqa: BLE001 - a bad upload must never crash the page
                            st.error(f"Could not push this raster to Earth Engine: {e}")
                else:
                    with st.spinner(
                        "Uploading and ingesting into Earth Engine — this can take a few minutes…"
                    ):
                        try:
                            ingested = push_vector_to_gee(
                                upload_file.getvalue(), upload_file.name, asset_name_input
                            )
                            st.success(
                                f"Ingested {ingested.feature_count} feature(s) as "
                                f"`{ingested.asset_id}`. Paste that into the \"Link / GEE ID\" "
                                "tab above to load it, or reference it in any other "
                                "GEE-backed analysis page."
                            )
                        except AssetUploadError as e:
                            st.error(str(e))
                        except Exception as e:  # noqa: BLE001 - a bad upload must never crash the page
                            st.error(f"Could not push this vector data to Earth Engine: {e}")

    st.markdown("##### New sample")
    class_label = st.text_input("Class label", placeholder="e.g. cropland, water, built-up")
    _label_key = class_label.strip()
    default_color = saved_class_colors.get(_label_key) or default_color_for_class(_label_key)
    sample_color = st.color_picker("Class color", value=default_color, key=f"color_{_label_key or 'none'}")
    creator = st.text_input("Your name (optional)", value="anonymous")

    st.markdown("##### GEE sync")
    st.caption(
        f"{feature_count()} sample(s) mirrored into a live `ee.FeatureCollection` "
        "for this session — used by the export options below."
    )

    _loaded_kind = st.session_state.get("ts_kind")
    _loaded_bytes = st.session_state.get("ts_raw_bytes")
    if _loaded_kind in ("tiff", "vector", "points") and _loaded_bytes:
        st.markdown("##### Push loaded data to GEE")
        _loaded_filename = st.session_state.get("ts_filename", "")
        st.caption(
            f"Push the **same data already loaded above** (`{_loaded_filename}`) into Earth "
            "Engine as a permanent asset — no need to fetch or upload it again."
        )
        push_loaded_asset_name = st.text_input(
            "Asset name",
            placeholder="e.g. my_2026_survey",
            help="Becomes `projects/<your-gee-project>/assets/<this name>`.",
            key="ts_push_loaded_asset_name",
        )
        push_loaded_clicked = st.button(
            f"{material('cloud_upload')} Push to Earth Engine",
            width='stretch',
            key="ts_push_loaded_button",
        )
        if push_loaded_clicked:
            if not push_loaded_asset_name.strip():
                st.error("Give the asset a name first.")
            else:
                with st.spinner(
                    "Uploading and ingesting into Earth Engine — this can take a few minutes…"
                ):
                    try:
                        if _loaded_kind == "tiff":
                            ingested = push_raster_to_gee(
                                _loaded_bytes, _loaded_filename, push_loaded_asset_name
                            )
                            st.success(f"Ingested as `{ingested.asset_id}`.")
                        else:
                            ingested = push_vector_to_gee(
                                _loaded_bytes, _loaded_filename, push_loaded_asset_name
                            )
                            st.success(
                                f"Ingested {ingested.feature_count} feature(s) as "
                                f"`{ingested.asset_id}`."
                            )
                    except AssetUploadError as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001 - a bad push must never crash the page
                        st.error(f"Could not push this data to Earth Engine: {e}")

if fetch:
    if not link.strip():
        st.sidebar.error("Paste a link first.")
    elif is_gee_mode:
        with st.spinner("Resolving Earth Engine asset…"):
            try:
                resolved_id = resolve_collection_id(link)
                if gee_district == "All Rwanda":
                    aoi = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
                        ee.Filter.eq("ADM0_NAME", "Rwanda")
                    ).geometry()
                else:
                    aoi = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
                        ee.Filter.And(
                            ee.Filter.eq("ADM0_NAME", "Rwanda"),
                            ee.Filter.eq("ADM2_NAME", gee_district),
                        )
                    ).geometry()
                composite = build_gee_composite(
                    resolved_id, aoi.getInfo(), str(gee_start_date), str(gee_end_date)
                )
                if composite is None:
                    st.sidebar.warning(
                        f"No scenes found for `{resolved_id}` over {gee_district} between "
                        f"{gee_start_date} and {gee_end_date}. Try a wider date range."
                    )
                else:
                    st.session_state["ts_kind"] = "gee"
                    st.session_state["ts_filename"] = resolved_id
                    st.session_state["ts_source_url"] = (
                        "https://developers.google.com/earth-engine/datasets/catalog/"
                        + resolved_id.replace("/", "_")
                    )
                    st.session_state["ts_gee_composite"] = composite
                    st.session_state.pop("ts_image_bytes", None)
                    st.session_state.pop("ts_vector_geojson", None)
                    st.session_state.pop("ts_raw_bytes", None)
                    st.session_state.pop("ts_last_drawing", None)
            except GeeImportError as e:
                st.sidebar.error(str(e))
            except Exception as e:  # noqa: BLE001 - a bad GEE id must never crash the app
                st.sidebar.error(f"Could not load this Earth Engine dataset: {e}")
    else:
        with st.spinner("Fetching…"):
            try:
                file_bytes, filename = resolve_image_link(link)
                vector_kind = detect_data_kind(filename)
                st.session_state.pop("ts_gee_composite", None)
                st.session_state.pop("ts_last_drawing", None)
                if vector_kind:
                    gdf = load_vector_gdf(file_bytes, filename)
                    st.session_state["ts_kind"] = vector_kind
                    st.session_state["ts_vector_geojson"] = gdf_to_geojson_dict(gdf)
                    st.session_state["ts_filename"] = filename
                    st.session_state["ts_source_url"] = link.strip()
                    st.session_state["ts_raw_bytes"] = file_bytes  # kept so "Push to Earth
                    # Engine" below can ingest the exact fetched file without re-fetching it.
                    st.session_state.pop("ts_image_bytes", None)
                else:
                    st.session_state["ts_kind"] = detect_image_kind(filename)
                    st.session_state["ts_image_bytes"] = file_bytes
                    st.session_state["ts_filename"] = filename
                    st.session_state["ts_source_url"] = link.strip()
                    st.session_state["ts_raw_bytes"] = file_bytes
                    st.session_state.pop("ts_vector_geojson", None)
            except (LinkImportError, VectorImportError) as e:
                st.sidebar.error(str(e))
            except Exception as e:  # noqa: BLE001 - a bad link must never crash the app
                st.sidebar.error(f"Could not import this link: {e}")

if "ts_kind" not in st.session_state:
    st.info("Fetch an image from the sidebar to begin.")
    st.stop()

kind = st.session_state["ts_kind"]
filename = st.session_state["ts_filename"]
source_url = st.session_state["ts_source_url"]
file_bytes = st.session_state.get("ts_image_bytes")

tab_map, tab_samples = st.tabs([":material/map: Map & Digitize", ":material/list_alt: Saved Samples"])

with tab_map:
    st.markdown(f"**Loaded:** `{filename}` — [source link]({source_url})")

    if kind in ("tiff", "gee", "vector", "points"):
        stats_df = None
        vector_geojson = None
        if kind == "tiff":
            try:
                png_bytes, bbox, stats_df = raster_preview(file_bytes)
            except Exception as e:
                st.error(f"Could not read this GeoTIFF: {e}")
                st.stop()
        elif kind == "gee":
            composite = st.session_state["ts_gee_composite"]
            bbox = composite.bbox
            st.caption(
                f"Live GEE composite — **{composite.collection_id}**, {composite.vis_label}, "
                f"{composite.scene_count} scene(s) from {composite.start_date} to {composite.end_date}."
            )
        else:
            vector_geojson = st.session_state["ts_vector_geojson"]
            try:
                bbox = geojson_bbox(vector_geojson)
            except VectorImportError as e:
                st.error(str(e))
                st.stop()
            n_features = len(vector_geojson.get("features", []))
            st.caption(
                f"**{n_features}** feature(s) — {geometry_type_summary(vector_geojson)}."
            )

        minx, miny, maxx, maxy = bbox

        show_context = st.checkbox(
            f"{material('satellite_alt')} Overlay a live Sentinel-2 (GEE) context layer",
            help=(
                "A real, recent Sentinel-2 composite for this same area, fetched live from GEE, "
                "shown alongside the loaded base layer for extra context."
            ),
        )

        m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=12, tiles="CartoDB positron")
        if kind == "tiff":
            png_data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            folium.raster_layers.ImageOverlay(
                image=png_data_uri, bounds=[[miny, minx], [maxy, maxx]], opacity=0.85, name="Imported raster"
            ).add_to(m)
        elif kind == "gee":
            folium.TileLayer(
                tiles=composite.tile_url,
                attr="Google Earth Engine",
                name=f"{composite.collection_id} composite",
                overlay=False,
            ).add_to(m)
        else:
            folium.GeoJson(
                vector_geojson,
                name="Imported vector/points data",
                marker=folium.CircleMarker(radius=5, color="#0F6E4F", fill=True, fill_opacity=0.8),
                style_function=lambda _f: {"color": "#0F6E4F", "fillColor": "#0F6E4F", "fillOpacity": 0.35, "weight": 2},
                tooltip=folium.GeoJsonTooltip(
                    fields=[k for k in (vector_geojson["features"][0]["properties"] or {}).keys()][:5]
                ) if vector_geojson.get("features") and vector_geojson["features"][0].get("properties") else None,
            ).add_to(m)

        if show_context:
            try:
                context = sentinel2_context_layer(bbox)
            except Exception as e:  # noqa: BLE001 - a GEE call failing must not crash the page
                context = None
                st.warning(f"Could not fetch the GEE context layer: {e}")
            if context is None:
                st.info("No cloud-free Sentinel-2 scenes found near this area in the last 6 months.")
            else:
                folium.TileLayer(
                    tiles=context["tile_url"],
                    attr="Google Earth Engine",
                    name=f"Sentinel-2 GEE composite ({context['scene_count']} scenes)",
                    overlay=True,
                ).add_to(m)

        # Render already-saved samples for this image, colored per class, so
        # the map reflects each sample's assigned color as it's built up.
        for r in all_records:
            if r["source_filename"] != filename:
                continue
            color = r.get("color", DEFAULT_SAMPLE_COLOR)
            folium.GeoJson(
                r["geometry"],
                style_function=lambda _f, c=color: {"color": c, "fillColor": c, "fillOpacity": 0.5, "weight": 2},
                tooltip=r["class_label"],
            ).add_to(m)

        Draw(
            export=False,
            draw_options={
                "polygon": {"repeatMode": True},
                "rectangle": {"repeatMode": True},
                "circle": False,
                "circlemarker": False,
                "marker": {"repeatMode": True},
                "polyline": False,
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(m)
        folium.LayerControl().add_to(m)

        st.markdown(
            "**Draw a point or polygon on the map, label it in the sidebar, then save it below.** "
            "The draw tool now stays active after each shape — click its icon again or press "
            "**Escape** to turn it off."
        )
        map_state = st_folium(m, height=500, width=None, key="ts_map")

        drawn_geometry = None
        if map_state and map_state.get("all_drawings"):
            drawings = map_state["all_drawings"]
            if drawings:
                drawn_geometry = drawings[-1]["geometry"]

        col_a, col_b = st.columns([3, 1])
        with col_a:
            if drawn_geometry:
                st.success(f"Ready to save a **{drawn_geometry['type']}** sample in {sample_color}.")
            else:
                st.caption("No shape drawn yet.")
        with col_b:
            save_clicked = st.button(f"{material('save')} Save sample", width='stretch', type="primary")

        if save_clicked:
            if not drawn_geometry:
                st.warning("Draw a point or polygon on the map first.")
            elif not class_label.strip():
                st.warning("Enter a class label in the sidebar first.")
            else:
                sample = TrainingSample(
                    id=uuid.uuid4().hex,
                    geometry=drawn_geometry,
                    class_label=class_label.strip(),
                    source_filename=filename,
                    source_url=source_url,
                    creator=creator.strip() or "anonymous",
                    color=sample_color,
                )
                add_sample(sample)
                add_feature(sample.to_dict())
                st.success(f"Saved sample labeled **{sample.class_label}** and mirrored it into the GEE FeatureCollection.")
                st.rerun()

        if stats_df is not None:
            with st.expander("Raster band statistics"):
                st.dataframe(stats_df, width='stretch')

    elif kind == "image":
        st.warning(
            "This is a plain image without embedded georeferencing (not a GeoTIFF), so it can't "
            "be placed on a map or digitized here. Showing a preview only."
        )
        st.image(file_bytes, width='stretch')

    else:
        st.error(
            f"`{filename}` isn't a recognized image type (expected .tif/.tiff/.png/.jpg). "
            "Nothing was loaded."
        )

with tab_samples:
    records = load_samples()
    if not records:
        st.caption("No samples saved yet.")
    else:
        import pandas as pd

        st.markdown("##### Legend")
        legend_colors = class_colors(records)
        st.markdown(
            "&nbsp;&nbsp;".join(
                f"<span style='color:{c}'>■</span> {label}" for label, c in legend_colors.items()
            ),
            unsafe_allow_html=True,
        )

        df = pd.DataFrame([
            {
                "Class": r["class_label"],
                "Color": r.get("color", DEFAULT_SAMPLE_COLOR),
                "Geometry": r["geometry"]["type"],
                "Source": r["source_filename"],
                "Creator": r["creator"],
                "Saved": r["created_at"],
            }
            for r in records
        ])
        st.dataframe(df, width='stretch', hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                f"{material('download')} Download all samples (GeoJSON)",
                data=samples_to_geojson(records),
                file_name="training_samples.geojson",
                mime="application/geo+json",
                width='stretch',
            )
        with col2:
            to_delete = st.selectbox(
                "Delete a sample",
                options=[""] + [f"{r['id']} — {r['class_label']} ({r['source_filename']})" for r in records],
            )
            if to_delete and st.button(f"{material('delete')} Delete selected", width='stretch'):
                sample_id = to_delete.split(" — ", 1)[0]
                if delete_sample(sample_id):
                    st.success("Deleted.")
                    st.rerun()

        st.divider()
        st.markdown("##### Export")
        st.caption(
            f"{feature_count()} sample(s) are mirrored into this session's `ee.FeatureCollection` — "
            "the GEE Asset / Google Drive / TFRecord options below export that collection."
        )

        formats = st.multiselect(
            "Export format(s)",
            options=["Shapefile", "GeoJSON", "KML", "CSV", "GEE Asset", "Google Drive", "TFRecord (via Drive)"],
            default=["GeoJSON"],
        )

        gee_asset_id, drive_folder = "", ""
        if "GEE Asset" in formats:
            gee_asset_id = st.text_input("Destination GEE asset ID", placeholder="users/you/training_samples")
        if "Google Drive" in formats or "TFRecord (via Drive)" in formats:
            drive_folder = st.text_input("Google Drive folder (optional)", placeholder="gee-exports")

        if st.button(f"{material('upload')} Run export", width='stretch', type="primary"):
            fc = get_feature_collection()

            for fmt in formats:
                try:
                    if fmt == "Shapefile":
                        st.download_button(
                            f"{material('download')} Download Shapefile (.zip)",
                            data=export_shapefile_zip(records),
                            file_name="training_samples_shp.zip",
                            mime="application/zip",
                            width='stretch',
                            key="dl_shp",
                        )
                    elif fmt == "GeoJSON":
                        st.download_button(
                            f"{material('download')} Download GeoJSON",
                            data=samples_to_geojson(records),
                            file_name="training_samples.geojson",
                            mime="application/geo+json",
                            width='stretch',
                            key="dl_geojson_export",
                        )
                    elif fmt == "KML":
                        st.download_button(
                            f"{material('download')} Download KML",
                            data=export_kml(records),
                            file_name="training_samples.kml",
                            mime="application/vnd.google-earth.kml+xml",
                            width='stretch',
                            key="dl_kml",
                        )
                    elif fmt == "CSV":
                        st.download_button(
                            f"{material('download')} Download CSV",
                            data=export_csv(records),
                            file_name="training_samples.csv",
                            mime="text/csv",
                            width='stretch',
                            key="dl_csv",
                        )
                    elif fmt == "GEE Asset":
                        if fc is None:
                            st.warning("No samples mirrored into this session's FeatureCollection yet.")
                        else:
                            task = export_to_gee_asset(fc, gee_asset_id, description="training_samples_export")
                            st.success(
                                f"GEE Asset export task **{task.status()['description']}** submitted "
                                f"(task id `{task.id}`). Check progress in the "
                                "[Earth Engine Tasks tab](https://code.earthengine.google.com/tasks)."
                            )
                    elif fmt == "Google Drive":
                        if fc is None:
                            st.warning("No samples mirrored into this session's FeatureCollection yet.")
                        else:
                            task = export_to_drive(fc, file_format="GeoJSON", description="training_samples_export", folder=drive_folder)
                            st.success(
                                f"Google Drive export task submitted (task id `{task.id}`). Check progress in the "
                                "[Earth Engine Tasks tab](https://code.earthengine.google.com/tasks)."
                            )
                    elif fmt == "TFRecord (via Drive)":
                        if fc is None:
                            st.warning("No samples mirrored into this session's FeatureCollection yet.")
                        else:
                            task = export_to_drive(fc, file_format="TFRecord", description="training_samples_tfrecord", folder=drive_folder)
                            st.success(
                                f"TFRecord export task submitted (task id `{task.id}`). Check progress in the "
                                "[Earth Engine Tasks tab](https://code.earthengine.google.com/tasks)."
                            )
                except ExportError as e:
                    st.error(f"{fmt}: {e}")
                except Exception as e:  # noqa: BLE001 - a bad export request must not crash the page
                    st.error(f"{fmt}: {e}")
