import io
import urllib.request
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

GREEN       = colors.HexColor("#1a9850")
DARK        = colors.HexColor("#1a1a2e")
LIGHT_GREEN = colors.HexColor("#d9ef8b")
LIGHT_GRAY  = colors.HexColor("#f5f5f5")

PAGE_W = A4[0] - 4 * cm    # usable width inside 2 cm margins


# ─── helpers ──────────────────────────────────────────────────────────────────

def _styles():
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=s["Heading1"], fontSize=20,
            textColor=DARK, spaceAfter=4, alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=s["Normal"], fontSize=11,
            textColor=colors.gray, spaceAfter=12, alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "Section", parent=s["Heading2"], fontSize=13,
            textColor=GREEN, spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=s["Normal"], fontSize=10, leading=14,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=s["Normal"], fontSize=8,
            textColor=colors.gray, alignment=TA_CENTER, spaceAfter=6,
        ),
        "note": ParagraphStyle(
            "Note", parent=s["Normal"], fontSize=9,
            textColor=colors.gray, leading=13,
        ),
    }


def _meta_table(district: str, date_range: str) -> Table:
    data = [
        ["District:",       district],
        ["Analysis Period:", date_range],
        ["Generated:",      datetime.now().strftime("%B %d, %Y at %H:%M UTC")],
        ["Data Source:",    "Google Earth Engine (GEE)"],
    ]
    t = Table(data, colWidths=[4 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",    (0, 0), (0, -1), DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GRAY, colors.white]),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


def _stats_table(stats: dict, st_styles: dict) -> list:
    data = [["Metric", "Value"]] + [[k, str(v)] for k, v in stats.items()]
    t = Table(data, colWidths=[10 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return [Paragraph("Key Statistics", st_styles["section"]), t, Spacer(1, 0.4 * cm)]


def _class_table(class_areas: dict, st_styles: dict) -> list:
    total = sum(class_areas.values()) or 1
    data  = [["Class", "Area (km²)", "% of Total"]]
    for label, area in class_areas.items():
        data.append([label, f"{area:.2f}", f"{area/total*100:.1f}%"])
    data.append(["TOTAL", f"{total:.2f}", "100%"])
    t = Table(data, colWidths=[9 * cm, 4 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",     (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",   (0, -1), (-1, -1), LIGHT_GREEN),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [LIGHT_GRAY, colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return [
        Paragraph("Area by Classification (km²)", st_styles["section"]),
        t, Spacer(1, 0.4 * cm),
    ]


def _fetch_image(url: str, timeout: int = 45) -> io.BytesIO | None:
    """Download image from URL → BytesIO (returns None on failure)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return io.BytesIO(resp.read())
    except Exception:
        return None


def _rl_image(buf: io.BytesIO, width: float, caption: str,
              st_styles: dict) -> list:
    """Wrap a BytesIO PNG → ReportLab Image + caption paragraph."""
    try:
        img = RLImage(buf, width=width, height=width)   # square thumbnails
        return [img, Paragraph(caption, st_styles["caption"])]
    except Exception:
        return [Paragraph(f"[Map unavailable: {caption}]", st_styles["caption"])]


# ─── public API ───────────────────────────────────────────────────────────────

def build_report(
    module_name: str,
    district: str,
    date_range: str,
    stats: dict,
    class_areas: dict,
    extra_notes: str = "",
) -> bytes:
    """Generic PDF report for any analysis module (no embedded maps)."""
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    st_styles = _styles()
    story     = []

    story.append(Paragraph("GEOPORTAL ANALYSIS", st_styles["title"]))
    story.append(Paragraph(f"{module_name} Analysis Report",  st_styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=10))
    story.append(_meta_table(district, date_range))
    story.append(Spacer(1, 0.4 * cm))
    story.extend(_stats_table(stats, st_styles))
    if class_areas:
        story.extend(_class_table(class_areas, st_styles))
    if extra_notes:
        story.append(Paragraph("Notes & Interpretation", st_styles["section"]))
        story.append(Paragraph(extra_notes, st_styles["body"]))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "This report was generated automatically by the GEOPORTAL ANALYSIS. "
        "All analyses are computed on-demand using Google Earth Engine satellite imagery. "
        "Results are for informational purposes and should be validated against ground-truth "
        "data before use in policy or planning decisions.",
        st_styles["note"],
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def _rl_image_from_bytes(png_bytes: bytes, width: float, caption: str, st_styles: dict) -> list:
    """Wrap already-in-memory PNG bytes (e.g. matplotlib figures) into a ReportLab flowable."""
    if not png_bytes:
        return [Paragraph(f"[Figure unavailable: {caption}]", st_styles["caption"])]
    try:
        img = RLImage(io.BytesIO(png_bytes), width=width, height=width)
        return [img, Paragraph(caption, st_styles["caption"])]
    except Exception:
        return [Paragraph(f"[Figure unavailable: {caption}]", st_styles["caption"])]


def build_uhi_report(
    district: str,
    date_range: str,
    lst_stats: dict,
    ndbi_stats: dict,
    regression: dict | None,
    bivariate_png: bytes,
    scatter_png: bytes,
    lst_thumb_url: str,
    ndbi_thumb_url: str,
    grid_size: int,
    n_cells_no_data: int,
    extra_notes: str = "",
) -> bytes:
    """
    Urban Heat Island (LST vs NDBI) PDF report with embedded raster maps and
    bivariate/regression figures.

    Layout
    ──────
    Page 1 : title · metadata · LST & NDBI statistics
    Page 2 : LST map · NDBI map (full width each)
    Page 3 : bivariate grid map · regression scatter (2-column) · regression stats
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    st_styles = _styles()
    story = []

    story.append(Paragraph("GEOPORTAL ANALYSIS", st_styles["title"]))
    story.append(Paragraph("Urban Heat Island — LST vs Impervious Surface (NDBI)", st_styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=10))
    story.append(_meta_table(district, date_range))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Land Surface Temperature — Statistics", st_styles["section"]))
    story.append(_stats_table(lst_stats, st_styles)[1])
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("NDBI (Impervious Surface Proxy) — Statistics", st_styles["section"]))
    story.append(_stats_table(ndbi_stats, st_styles)[1])
    story.append(Spacer(1, 0.4 * cm))

    if extra_notes:
        story.append(Paragraph("Methodology & Notes", st_styles["section"]))
        story.append(Paragraph(extra_notes, st_styles["body"]))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Land Surface Temperature Map", st_styles["section"]))
    lst_buf = _fetch_image(lst_thumb_url)
    if lst_buf:
        try:
            story.append(RLImage(lst_buf, width=PAGE_W, height=PAGE_W * 0.75))
        except Exception:
            pass
    story.append(Paragraph(f"LST (°C) — {district}, {date_range}.", st_styles["caption"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Impervious Surface Map (NDBI)", st_styles["section"]))
    ndbi_buf = _fetch_image(ndbi_thumb_url)
    if ndbi_buf:
        try:
            story.append(RLImage(ndbi_buf, width=PAGE_W, height=PAGE_W * 0.75))
        except Exception:
            pass
    story.append(Paragraph(f"NDBI — {district}, {date_range}.", st_styles["caption"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Bivariate Classification & Regression", st_styles["section"]))
    story.append(Paragraph(
        f"Zonal means computed over a {grid_size}×{grid_size} grid clipped to the district boundary "
        f"({n_cells_no_data} cell(s) outside the imagery footprint, shown hatched below).",
        st_styles["body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    col_w = (PAGE_W - 0.5 * cm) / 2
    left_cell = _rl_image_from_bytes(bivariate_png, col_w, "LST × NDBI bivariate classification per grid cell.", st_styles)
    right_cell = _rl_image_from_bytes(scatter_png, col_w, "OLS regression of LST on NDBI.", st_styles)
    row_table = Table([[left_cell, right_cell]], colWidths=[col_w, col_w])
    row_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(KeepTogether(row_table))
    story.append(Spacer(1, 0.4 * cm))

    if regression:
        reg_data = [
            ["Metric", "Value"],
            ["Slope", str(regression.get("slope"))],
            ["Intercept", str(regression.get("intercept"))],
            ["R²", str(regression.get("r2"))],
            ["p-value", f"{regression.get('p_value'):.4g}" if regression.get("p_value") is not None else "—"],
            ["n (grid cells)", str(regression.get("n"))],
        ]
        reg_table = Table(reg_data, colWidths=[8 * cm, 8 * cm])
        reg_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(Paragraph("Regression Statistics", st_styles["section"]))
        story.append(reg_table)
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "This report was generated automatically by the GEOPORTAL ANALYSIS. "
        "All analyses are computed on-demand using Google Earth Engine satellite imagery. "
        "Results are for informational purposes and should be validated against ground-truth "
        "data before use in policy or planning decisions.",
        st_styles["note"],
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def build_rusle_report(
    district: str,
    year: int,
    stats: dict,
    class_areas: dict,
    factor_maps: dict,
    factor_means: dict,
    extra_notes: str = "",
) -> bytes:
    """
    RUSLE-specific PDF report with embedded factor maps.

    Layout
    ──────
    Page 1 : title · metadata · statistics · erosion class table
    Page 2 : methodology notes · final soil loss map (full width)
    Page 3+: factor maps in 2-column grid (R, K, LS, C, P) with captions
    """
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    st_styles = _styles()
    story     = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("GEOPORTAL ANALYSIS", st_styles["title"]))
    story.append(Paragraph("RUSLE — Soil Erosion Risk Analysis Report", st_styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=10))
    story.append(_meta_table(district, str(year)))
    story.append(Spacer(1, 0.4 * cm))

    # ── Statistics ─────────────────────────────────────────────────────────────
    story.extend(_stats_table(stats, st_styles))

    # ── Classification table ───────────────────────────────────────────────────
    if class_areas:
        story.extend(_class_table(class_areas, st_styles))

    # ── Factor means table ────────────────────────────────────────────────────
    story.append(Paragraph("RUSLE Factor Spatial Means", st_styles["section"]))
    fm_data = [["Factor", "Spatial Mean (district)", "Nyagisozi study ref."]]
    study_refs = {"R": "981.12", "K": "0.0347", "LS": "51.02", "C": "0.178", "P": "0.367"}
    for key in ["R", "K", "LS", "C", "P"]:
        label_match = next((k for k in factor_means if k.startswith(key)), None)
        val  = factor_means.get(label_match, 0) if label_match else 0
        meta = factor_maps.get(key, {})
        fm_data.append([
            f"{key} — {meta.get('label', key).split('—')[-1].strip()}",
            str(val),
            study_refs.get(key, "—"),
        ])
    fm_table = Table(fm_data, colWidths=[8*cm, 4*cm, 4*cm])
    fm_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(fm_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Methodology notes ──────────────────────────────────────────────────────
    if extra_notes:
        story.append(Paragraph("Methodology & Notes", st_styles["section"]))
        story.append(Paragraph(extra_notes, st_styles["body"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── Final Soil Loss Map (full width) ──────────────────────────────────────
    story.append(Paragraph("Final Soil Loss Map  (A = R × K × LS × C × P)", st_styles["section"]))
    a_meta = factor_maps.get("A", {})
    a_buf  = _fetch_image(a_meta.get("thumb_url", ""))
    if a_buf:
        try:
            img = RLImage(a_buf, width=PAGE_W, height=PAGE_W * 0.65)
            story.append(img)
        except Exception:
            pass
    story.append(Paragraph(
        f"Annual soil loss (t·ha⁻¹·yr⁻¹) — {district} district, {year}. "
        "Colour scale: green = very low (<10) → red = extreme (>200 t/ha/yr).",
        st_styles["caption"],
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Factor Maps (2-column grid) ────────────────────────────────────────────
    story.append(Paragraph("Individual RUSLE Factor Maps", st_styles["section"]))
    factor_order = ["R", "K", "LS", "C", "P"]
    col_w   = (PAGE_W - 0.5 * cm) / 2      # two columns with small gap
    img_h   = col_w * 0.85

    for i in range(0, len(factor_order), 2):
        pair = factor_order[i:i+2]
        cells = []
        for key in pair:
            meta = factor_maps.get(key, {})
            buf  = _fetch_image(meta.get("thumb_url", ""))
            cell_story = []
            if buf:
                try:
                    cell_story.append(RLImage(buf, width=col_w, height=img_h))
                except Exception:
                    pass
            cell_story.append(Paragraph(
                f"<b>{meta.get('label', key)}</b><br/>"
                f"{meta.get('description', '')}",
                st_styles["caption"],
            ))
            cells.append(cell_story)

        # pad to 2 columns if odd number
        while len(cells) < 2:
            cells.append([Spacer(1, 1)])

        row_table = Table([cells], colWidths=[col_w, col_w], spaceBefore=6)
        row_table.setStyle(TableStyle([
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(KeepTogether(row_table))
        story.append(Spacer(1, 0.3 * cm))

    # ── Disclaimer ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "This report was generated automatically by the GEOPORTAL ANALYSIS. "
        "All analyses are computed on-demand using Google Earth Engine satellite imagery. "
        "Results are for informational purposes and should be validated against ground-truth "
        "data before use in policy or planning decisions.",
        st_styles["note"],
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
