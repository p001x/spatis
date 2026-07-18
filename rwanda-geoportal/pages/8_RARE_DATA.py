"""
RARE DATA — Dataset Repository.

Three separate areas, kept fully isolated from each other in both storage and UI:
- Official Datasets   — curated by the admin (own catalog + storage prefix).
- Community Uploads   — anyone can contribute their own data (own catalog + storage prefix).
- Admin Upload        — password-gated management of the Official catalog only.

Every dataset can be visually previewed (map layer + attribute table / band stats) and,
depending on its geometry, converted to another format:
  raster   -> vector polygons, or sampled points
  points   -> raster, via IDW or Ordinary Kriging interpolation
  lines    -> raster, via Euclidean distance from the nearest line

All files persist in Replit Object Storage — nothing is kept on local disk,
so uploads survive redeploys.
"""

import base64
import os

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import Point
from streamlit_folium import st_folium

from utils.dataset_storage import (
    bbox_to_box,
    build_zip_of_datasets,
    datasets_intersecting,
    delete_record,
    download_dataset_bytes,
    load_metadata,
    process_and_store_link,
    process_and_store_upload,
)
from utils.geodata_viz import (
    array_to_geotiff_bytes,
    csv_to_points_gdf,
    euclidean_distance_raster,
    gdf_to_shapefile_zip,
    idw_interpolate,
    kriging_interpolate,
    load_shapefile_gdf,
    numeric_columns,
    raster_array_to_png,
    raster_preview as _raster_preview,
    raster_to_points as _raster_to_points,
    raster_to_vector as _raster_to_vector,
)
from utils.style import apply_style, material

apply_style()


@st.cache_data(show_spinner=False, max_entries=8)
def raster_preview(file_bytes: bytes):
    """Cached: this page reruns on every widget interaction, so without caching the
    same raster would be re-decoded from scratch every time. Keyed on file bytes."""
    return _raster_preview(file_bytes)


@st.cache_data(show_spinner=False, max_entries=8)
def raster_to_points(file_bytes: bytes, max_points: int):
    return _raster_to_points(file_bytes, max_points=max_points)


@st.cache_data(show_spinner=False, max_entries=8)
def raster_to_vector(file_bytes: bytes):
    return _raster_to_vector(file_bytes)

st.title(":material/database: RARE DATA — Dataset Repository")
st.markdown(
    "Browse, preview, convert, and download geospatial datasets covering Rwanda. "
    "**Official Datasets** are curated by the admin; **Community Uploads** are contributed by anyone "
    "and are kept in a completely separate catalog."
)

TYPE_COLORS = {"tiff": "#e74c3c", "shapefile": "#2980b9", "csv": "#27ae60", "other": "#8e44ad"}


# ---------------------------------------------------------------------------
# Shared: dataset detail view (visualize + convert)
# ---------------------------------------------------------------------------

def render_dataset_detail(record: dict, key_prefix: str) -> None:
    try:
        file_bytes = download_dataset_bytes(record["storage_key"])
    except Exception as e:
        st.error(f"Could not load this file from storage: {e}")
        return

    file_type = record["file_type"]

    if file_type == "tiff":
        try:
            png_bytes, bbox, stats_df = raster_preview(file_bytes)
        except Exception as e:
            st.error(f"Could not render this raster: {e}")
            return

        st.markdown("**Preview**")
        minx, miny, maxx, maxy = bbox
        rmap = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=9, tiles="CartoDB positron")
        png_data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
        folium.raster_layers.ImageOverlay(
            image=png_data_uri, bounds=[[miny, minx], [maxy, maxx]], opacity=0.8
        ).add_to(rmap)
        st_folium(rmap, height=380, width=None, key=f"{key_prefix}_raster_map")

        st.markdown("**Band statistics** (raster's equivalent of an attribute table)")
        st.dataframe(stats_df, width='stretch')

        st.markdown("**Convert**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(":material/arrow_forward: Convert to Vector (polygonize)", key=f"{key_prefix}_to_vec"):
                with st.spinner("Polygonizing raster..."):
                    try:
                        gdf = raster_to_vector(file_bytes)
                        zip_bytes = gdf_to_shapefile_zip(gdf)
                        st.success(f"Created {len(gdf)} polygons.")
                        st.download_button(
                            "Download shapefile.zip", data=zip_bytes, file_name="converted_vector.zip",
                            mime="application/zip", key=f"{key_prefix}_dl_vec",
                        )
                    except Exception as e:
                        st.error(f"Conversion failed: {e}")
        with c2:
            max_pts = st.number_input(
                "Max sample points", min_value=100, max_value=20000, value=3000, step=100, key=f"{key_prefix}_maxpts"
            )
            if st.button(":material/arrow_forward: Convert to Points", key=f"{key_prefix}_to_pts"):
                with st.spinner("Sampling raster to points..."):
                    try:
                        gdf = raster_to_points(file_bytes, max_points=int(max_pts))
                        zip_bytes = gdf_to_shapefile_zip(gdf)
                        st.success(f"Created {len(gdf)} points.")
                        st.download_button(
                            "Download points.zip", data=zip_bytes, file_name="converted_points.zip",
                            mime="application/zip", key=f"{key_prefix}_dl_pts",
                        )
                    except Exception as e:
                        st.error(f"Conversion failed: {e}")
        return

    # Vector-ish types: shapefile (any geometry) or CSV with lat/lon points
    try:
        if file_type == "shapefile":
            gdf = load_shapefile_gdf(file_bytes)
        elif file_type == "csv":
            gdf = csv_to_points_gdf(file_bytes)
        else:
            st.info("This dataset type has no visual preview.")
            return
    except Exception as e:
        st.error(f"Could not load this dataset for preview: {e}")
        return

    st.markdown("**Attribute table**")
    st.dataframe(gdf.drop(columns="geometry"), width='stretch')

    geom_types = set(gdf.geometry.geom_type.unique())
    is_points = geom_types <= {"Point", "MultiPoint"}
    is_lines = geom_types <= {"LineString", "MultiLineString"}

    st.markdown("**Preview**")
    try:
        minx, miny, maxx, maxy = gdf.total_bounds
        vmap = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=9, tiles="CartoDB positron")
        folium.GeoJson(gdf.to_json(), name="dataset").add_to(vmap)
        st_folium(vmap, height=380, width=None, key=f"{key_prefix}_vec_map")
    except Exception as e:
        st.warning(f"Map preview unavailable: {e}")

    num_cols = numeric_columns(gdf)

    if is_points:
        st.markdown("**Convert to Raster** (interpolation)")
        if not num_cols:
            st.info("No numeric attribute column found to interpolate — add one to enable conversion.")
        else:
            c1, c2, c3 = st.columns([2, 1, 1])
            value_col = c1.selectbox("Value column", num_cols, key=f"{key_prefix}_valcol")
            resolution = c2.slider("Grid resolution", 20, 200, 80, key=f"{key_prefix}_res")
            method = c3.selectbox("Method", ["IDW", "Kriging"], key=f"{key_prefix}_method")
            if st.button(":material/arrow_forward: Interpolate to Raster", key=f"{key_prefix}_interp"):
                with st.spinner(f"Running {method}..."):
                    try:
                        if method == "IDW":
                            array, transform = idw_interpolate(gdf, value_col, resolution=resolution)
                        else:
                            array, transform = kriging_interpolate(gdf, value_col, resolution=resolution)
                        st.image(raster_array_to_png(array), caption=f"{method} interpolation of '{value_col}'")
                        tiff_bytes = array_to_geotiff_bytes(array, transform)
                        st.download_button(
                            "Download raster.tif", data=tiff_bytes, file_name=f"{method.lower()}_result.tif",
                            mime="image/tiff", key=f"{key_prefix}_dl_raster",
                        )
                    except Exception as e:
                        st.error(f"Interpolation failed: {e}")

    elif is_lines:
        st.markdown("**Convert to Raster** (Euclidean distance)")
        resolution = st.slider("Grid resolution", 20, 300, 100, key=f"{key_prefix}_lineres")
        if st.button(":material/arrow_forward: Compute Distance Raster", key=f"{key_prefix}_dist"):
            with st.spinner("Computing Euclidean distance..."):
                try:
                    array, transform = euclidean_distance_raster(gdf, resolution=resolution)
                    st.image(raster_array_to_png(array), caption="Distance to nearest line (degrees)")
                    tiff_bytes = array_to_geotiff_bytes(array, transform)
                    st.download_button(
                        "Download distance.tif", data=tiff_bytes, file_name="euclidean_distance.tif",
                        mime="image/tiff", key=f"{key_prefix}_dl_dist",
                    )
                except Exception as e:
                    st.error(f"Distance computation failed: {e}")
    else:
        st.caption("Polygon datasets currently support preview and attribute table only (no conversion requested).")


# ---------------------------------------------------------------------------
# Shared: browse + download section for one source ("admin" or "community")
# ---------------------------------------------------------------------------

def render_browse_section(source: str, map_key: str) -> None:
    records = load_metadata(source=source)
    spatial_records = [r for r in records if r.get("bbox")]
    non_spatial_records = [r for r in records if not r.get("bbox")]

    total_size = sum(r.get("file_size_mb", 0) for r in records)
    type_counts = pd.Series([r["file_type"] for r in records]).value_counts().to_dict() if records else {}

    summary_cols = st.columns(4)
    summary_cols[0].metric("Datasets", len(records))
    summary_cols[1].metric("Total size", f"{total_size:.1f} MB")
    summary_cols[2].metric("Spatial footprints", len(spatial_records))
    summary_cols[3].metric(
        "File types", ", ".join(f"{k} ({v})" for k, v in type_counts.items()) if type_counts else "—"
    )

    if not records:
        st.info("No datasets here yet.")
        return

    map_col, list_col = st.columns([3, 2])

    with map_col:
        st.subheader("Coverage map")
        st.caption(
            "Colored rectangles show each dataset's footprint. Click one to select it, "
            "or draw your own study area with the tool at the top-left of the map."
        )
        center = [-1.94, 29.87]  # Rwanda centroid
        fmap = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")
        for r in spatial_records:
            minx, miny, maxx, maxy = r["bbox"]
            color = TYPE_COLORS.get(r["file_type"], "#7f8c8d")
            folium.Rectangle(
                bounds=[[miny, minx], [maxy, maxx]], color=color, weight=2, fill=True, fill_opacity=0.15,
                tooltip=r["name"],
                popup=folium.Popup(
                    f"<b>{r['name']}</b><br>Type: {r['file_type']}<br>"
                    f"Size: {r['file_size_mb']:.2f} MB<br>id: {r['id']}", max_width=250,
                ),
            ).add_to(fmap)
        Draw(
            export=False,
            draw_options={"polygon": True, "rectangle": True, "circle": False, "circlemarker": False, "marker": False, "polyline": False},
            edit_options={"edit": True, "remove": True},
        ).add_to(fmap)
        map_state = st_folium(fmap, height=500, width=None, key=map_key)

    selected_area_geojson = None
    click_note = None
    if map_state and map_state.get("all_drawings"):
        drawings = map_state["all_drawings"]
        if drawings:
            selected_area_geojson = drawings[-1]["geometry"]
            click_note = "Using your drawn study area."
    if selected_area_geojson is None and map_state and map_state.get("last_clicked"):
        lat = map_state["last_clicked"]["lat"]
        lng = map_state["last_clicked"]["lng"]
        click_point = Point(lng, lat)
        matched = [r for r in spatial_records if bbox_to_box(r["bbox"]).intersects(click_point.buffer(0.01))]
        if matched:
            selected_area_geojson = click_point.buffer(0.05).__geo_interface__
            click_note = f"Using footprint(s) near your click: {', '.join(m['name'] for m in matched)}."

    with list_col:
        st.subheader("Datasets")
        if click_note:
            st.success(click_note)

        filtered = datasets_intersecting(records, selected_area_geojson)
        display_records = filtered if selected_area_geojson else spatial_records

        for r in display_records:
            with st.container(border=True):
                st.markdown(f"**{r['name']}** &nbsp;·&nbsp; `{r['file_type']}` &nbsp;·&nbsp; {r['file_size_mb']:.2f} MB")
                if r.get("description"):
                    st.caption(r["description"])
                if r.get("contributor"):
                    st.caption(f"Contributed by: {r['contributor']}")
                if r.get("source_url"):
                    st.caption(f"{material('link')} Hosted on GitHub — [view source]({r['source_url']})")
                b1, b2 = st.columns(2)
                try:
                    data = download_dataset_bytes(r["storage_key"])
                    b1.download_button(":material/download: Download", data=data, file_name=r["original_filename"], key=f"{source}_dl_{r['id']}")
                except Exception as e:
                    b1.error(f"Load failed: {e}")
                with b2.popover(":material/search: View & Convert"):
                    render_dataset_detail(r, key_prefix=f"{source}_{r['id']}")

        if non_spatial_records:
            st.markdown("**Non-spatial datasets** (not shown on map)")
            for r in non_spatial_records:
                with st.container(border=True):
                    st.markdown(f"**{r['name']}** &nbsp;·&nbsp; `{r['file_type']}` &nbsp;·&nbsp; {r['file_size_mb']:.2f} MB")
                    try:
                        data = download_dataset_bytes(r["storage_key"])
                        st.download_button(":material/download: Download", data=data, file_name=r["original_filename"], key=f"{source}_dl_ns_{r['id']}")
                    except Exception as e:
                        st.error(f"Load failed: {e}")

        st.markdown("---")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            if st.button(":material/download: Download All", width='stretch', key=f"{source}_dl_all"):
                with st.spinner("Bundling all datasets..."):
                    zip_bytes = build_zip_of_datasets(records)
                st.download_button(
                    "Save all_datasets.zip", data=zip_bytes, file_name=f"{source}_all_datasets.zip",
                    mime="application/zip", width='stretch', key=f"{source}_dl_all_save",
                )
        with dl_col2:
            area_records = datasets_intersecting(records, selected_area_geojson) if selected_area_geojson else []
            disabled = not area_records
            if st.button(
                ":material/download: Download Selected Area Datasets", width='stretch', disabled=disabled,
                help="Draw or click a study area on the map first." if disabled else None, key=f"{source}_dl_area",
            ):
                with st.spinner("Bundling datasets for the selected area..."):
                    zip_bytes = build_zip_of_datasets(area_records)
                st.download_button(
                    "Save selected_area_datasets.zip", data=zip_bytes, file_name=f"{source}_selected_area.zip",
                    mime="application/zip", width='stretch', key=f"{source}_dl_area_save",
                )


official_tab, community_tab, admin_tab = st.tabs([
    ":material/public: Official Datasets",
    ":material/group: Community Uploads",
    ":material/admin_panel_settings: Admin Upload",
])

# ---------------------------------------------------------------------------
# Official Datasets (admin-curated, read-only for regular users)
# ---------------------------------------------------------------------------
with official_tab:
    render_browse_section(source="admin", map_key="official_map")

# ---------------------------------------------------------------------------
# Community Uploads (anyone can contribute — kept in a separate catalog)
# ---------------------------------------------------------------------------
with community_tab:
    st.caption(
        "Anyone can add data here. Community uploads are kept in a **separate catalog** from the "
        "Official Datasets above — they never mix."
    )
    render_browse_section(source="community", map_key="community_map")

    st.markdown("---")
    st.subheader("Add your own dataset")
    with st.form("community_upload_form", clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "GeoTIFF (.tif/.tiff), CSV (.csv), or zipped shapefile (.zip)",
            type=["tif", "tiff", "csv", "zip"], accept_multiple_files=True, key="community_uploader",
        )
        name = st.text_input("Name", key="community_name")
        description = st.text_area("Description", key="community_description")
        contributor = st.text_input("Your name (optional)", key="community_contributor")
        submitted = st.form_submit_button("Upload")

    if submitted:
        if not uploaded_files:
            st.warning("Choose at least one file to upload.")
        elif not name:
            st.warning("Please provide a name for the dataset.")
        else:
            for f in uploaded_files:
                file_bytes = f.getvalue()
                size_mb = len(file_bytes) / (1024 * 1024)
                if size_mb > 200:
                    st.warning(f"**{f.name}** is {size_mb:.1f} MB — exceeds the 200 MB cap, skipped.")
                    continue
                with st.spinner(f"Processing {f.name}..."):
                    record = process_and_store_upload(
                        filename=f.name, file_bytes=file_bytes,
                        name=name if len(uploaded_files) == 1 else f"{name} — {f.name}",
                        description=description, source="community",
                        contributor=contributor or None,
                    )
                if record.status == "error":
                    st.error(f"**{f.name}** failed to process: {record.error_message}")
                elif record.status == "non-spatial":
                    st.warning(f"**{f.name}** uploaded but no coordinates were found — listed without map footprint.")
                else:
                    st.success(f"**{f.name}** uploaded successfully.")
            st.rerun()

    st.markdown("---")
    st.subheader("Or add a dataset from a GitHub link")
    st.caption(
        "Found a dataset in a GitHub repo? Paste its link below (a repo file page or a raw "
        "file URL both work). The file stays hosted on GitHub — this app only remembers the "
        "link and fetches the data live whenever it's viewed or downloaded."
    )
    with st.form("community_link_form", clear_on_submit=True):
        link_url = st.text_input(
            "GitHub file link",
            placeholder="https://github.com/user/repo/blob/main/data/file.csv",
            key="community_link_url",
        )
        link_name = st.text_input("Name", key="community_link_name")
        link_description = st.text_area("Description", key="community_link_description")
        link_contributor = st.text_input("Your name (optional)", key="community_link_contributor")
        link_submitted = st.form_submit_button(f"{material('link')} Add from GitHub")

    if link_submitted:
        if not link_url:
            st.warning("Paste a GitHub link first.")
        elif not link_name:
            st.warning("Please provide a name for the dataset.")
        else:
            with st.spinner("Fetching from GitHub..."):
                record = process_and_store_link(
                    url=link_url, name=link_name, description=link_description,
                    source="community", contributor=link_contributor or None,
                )
            if record.status == "error":
                st.error(f"Could not add this link: {record.error_message}")
            elif record.status == "non-spatial":
                st.warning("Added, but no coordinates were found — listed without map footprint.")
            else:
                st.success(f"**{record.name}** added — now live from GitHub.")
            st.rerun()

# ---------------------------------------------------------------------------
# Admin Upload (password-gated, manages the Official catalog only)
# ---------------------------------------------------------------------------
with admin_tab:
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if "rare_data_admin_authed" not in st.session_state:
        st.session_state.rare_data_admin_authed = False

    if not st.session_state.rare_data_admin_authed:
        st.subheader("Admin sign-in")
        pw_input = st.text_input("Admin password", type="password")
        if st.button("Sign in"):
            if admin_password and pw_input == admin_password:
                st.session_state.rare_data_admin_authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        top_l, top_r = st.columns([4, 1])
        with top_l:
            st.subheader("Upload a new official dataset")
        with top_r:
            if st.button("Sign out"):
                st.session_state.rare_data_admin_authed = False
                st.rerun()

        with st.form("rare_data_upload_form", clear_on_submit=True):
            uploaded_files = st.file_uploader(
                "GeoTIFF (.tif/.tiff), CSV (.csv), or zipped shapefile (.zip)",
                type=["tif", "tiff", "csv", "zip"], accept_multiple_files=True,
            )
            name = st.text_input("Name")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Upload")

        if submitted:
            if not uploaded_files:
                st.warning("Choose at least one file to upload.")
            elif not name:
                st.warning("Please provide a name for the dataset.")
            else:
                for f in uploaded_files:
                    file_bytes = f.getvalue()
                    size_mb = len(file_bytes) / (1024 * 1024)
                    if size_mb > 200:
                        st.warning(f"**{f.name}** is {size_mb:.1f} MB — exceeds the 200 MB cap, skipped.")
                        continue
                    with st.spinner(f"Processing {f.name}..."):
                        record = process_and_store_upload(
                            filename=f.name, file_bytes=file_bytes,
                            name=name if len(uploaded_files) == 1 else f"{name} — {f.name}",
                            description=description, source="admin",
                        )
                    if record.status == "error":
                        st.error(f"**{f.name}** failed to process: {record.error_message}")
                    elif record.status == "non-spatial":
                        st.warning(f"**{f.name}** uploaded but no coordinates were found — listed without map footprint.")
                    else:
                        st.success(f"**{f.name}** uploaded successfully.")

        st.markdown("---")
        st.subheader("Existing official datasets")
        records = load_metadata(source="admin")
        if not records:
            st.caption("No datasets uploaded yet.")
        else:
            for r in records:
                cols = st.columns([3, 1.5, 1, 1, 1])
                cols[0].markdown(f"**{r['name']}**")
                cols[1].markdown(f"`{r['file_type']}` · {r['status']}")
                cols[2].markdown(f"{r['file_size_mb']:.2f} MB")
                cols[3].markdown(r["upload_date"][:10])
                if cols[4].button(":material/delete: Delete", key=f"del_{r['id']}"):
                    try:
                        ok = delete_record(r["id"], source="admin")
                        if ok:
                            st.rerun()
                        else:
                            st.error("Could not delete this dataset — storage is temporarily unavailable. Try again.")
                    except Exception as e:
                        st.error(f"Could not delete this dataset: {e}")
