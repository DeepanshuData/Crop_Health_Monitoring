"""CSV and PDF report creation for the verified local scene."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as ReportImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.crop_health_data import INDEX_DETAILS, image_png, index_rgba, statistics_frame


def build_statistics_csv(scene: dict[str, Any]) -> bytes:
    output = io.StringIO()
    statistics_frame(scene).to_csv(output, index=False, float_format="%.8f")
    return output.getvalue().encode("utf-8-sig")


def _scaled_png(image: np.ndarray, max_width: int = 1500) -> bytes:
    buffer = io.BytesIO(image_png(image))
    with Image.open(buffer) as source:
        if source.width > max_width:
            height = round(source.height * max_width / source.width)
            source = source.resize((max_width, height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        source.save(output, format="PNG", optimize=True)
        return output.getvalue()


def build_pdf_report(scene: dict[str, Any], location_label: str = "Mysuru, Karnataka, India") -> bytes:
    """Create a concise, non-diagnostic scene report with NDVI, NDRE and NDWI maps."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title="AgriVision Crop Health Intelligence Report",
        author="AgriVision",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AgriTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#183d2b"),
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AgriSubTitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#66736b"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="AgriBody",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=12,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AgriSection",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#244d35"),
            spaceBefore=5,
            spaceAfter=6,
        )
    )

    profile = scene["source_profile"]
    total_pixels = scene["total_pixels"]
    valid_pixels = scene["base_valid_pixels"]
    pixel_area = abs(profile["transform"].a * profile["transform"].e)
    valid_area_ha = valid_pixels * pixel_area / 10000
    footprint_area_ha = total_pixels * pixel_area / 10000
    report_date = datetime.now().date().isoformat()
    content = [
        Paragraph("AgriVision — GeoAI Crop Health Intelligence", styles["AgriTitle"]),
        Paragraph("Satellite Intelligence for Smarter Agriculture", styles["AgriSubTitle"]),
        Spacer(1, 5 * mm),
        Paragraph("Study area and source", styles["AgriSection"]),
    ]

    metadata_rows = [
        ["Study area", location_label, "Acquisition date", "6 February 2025"],
        ["Satellite / collection", "Sentinel-2 / COPERNICUS/S2_SR_HARMONIZED", "Resolution", "20 m"],
        ["Input bands", "B2, B3, B4, B5, B8, B11", "Source CRS", "Inherited source raster CRS (EPSG:32643 designation)"],
        ["Raster footprint estimate", f"{footprint_area_ha:,.2f} ha", "Valid-pixel footprint estimate", f"{valid_area_ha:,.2f} ha"],
        ["Valid pixels", f"{valid_pixels:,}", "Invalid pixels", f"{total_pixels - valid_pixels:,}"],
        ["Cloud cover", "Not available in source metadata", "Report generated", report_date],
    ]
    metadata_table = Table(metadata_rows, colWidths=[35 * mm, 95 * mm, 36 * mm, 101 * mm])
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f5ef")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f0f5ef")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#53645a")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#53645a")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dce4dc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    content.extend([metadata_table, Spacer(1, 4 * mm)])

    content.append(Paragraph("Index statistics", styles["AgriSection"]))
    frame = statistics_frame(scene)
    table_data = [[
        "Index",
        "Minimum",
        "Maximum",
        "Mean",
        "Median",
        "Std. dev.",
        "Valid pixels",
        "Invalid pixels",
    ]]
    for row in frame.to_dict(orient="records"):
        table_data.append(
            [
                row["Index Name"],
                f'{row["Minimum"]:.4f}',
                f'{row["Maximum"]:.4f}',
                f'{row["Mean"]:.4f}',
                f'{row["Median"]:.4f}',
                f'{row["Standard Deviation"]:.4f}',
                f'{row["Valid Pixel Count"]:,}',
                f'{row["Invalid Pixel Count"]:,}',
            ]
        )
    index_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[20 * mm, 25 * mm, 25 * mm, 23 * mm, 23 * mm, 25 * mm, 32 * mm, 32 * mm],
    )
    index_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244d35")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f5")]),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dce4dc")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    content.extend(
        [
            index_table,
            Spacer(1, 4 * mm),
            Paragraph(
                "<b>Interpretation:</b> These spectral-index statistics describe relative "
                "reflectance patterns in the supplied scene. They are not confirmed crop-health "
                "or agronomic diagnoses. NDWI is the McFeeters Green–NIR variant, "
                "(B3 − B8)/(B3 + B8), and is distinct from NDMI.",
                styles["AgriBody"],
            ),
            Paragraph(
                "<b>Quality and limitations:</b> Reflectance is divided by 10,000; all six "
                "source bands must be finite and positive; EVI additionally masks denominator "
                "magnitudes below 0.1. Invalid pixels are NoData. Scene cloud percentage is not "
                "available in the source metadata. Footprint area is a raster-grid estimate, "
                "not a surveyed field or administrative area.",
                styles["AgriBody"],
            ),
            PageBreak(),
            Paragraph("Selected index maps", styles["AgriTitle"]),
            Paragraph(
                "The map color stretch is for visualization only (2nd–98th valid-value percentiles); "
                "the underlying scientific values are not clipped.",
                styles["AgriSubTitle"],
            ),
            Spacer(1, 4 * mm),
        ]
    )

    for index_name in ("NDVI", "NDRE", "NDWI"):
        content.append(Paragraph(index_name, styles["AgriSection"]))
        content.append(Paragraph(INDEX_DETAILS[index_name]["purpose"], styles["AgriBody"]))
        png_bytes = _scaled_png(index_rgba(scene, index_name))
        content.append(
            ReportImage(
                io.BytesIO(png_bytes),
                width=240 * mm,
                height=145 * mm,
                kind="proportional",
            )
        )
        if index_name != "NDWI":
            content.append(PageBreak())

    document.build(content)
    return buffer.getvalue()
