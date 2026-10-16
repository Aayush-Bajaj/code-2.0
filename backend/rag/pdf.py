"""
backend/rag/pdf.py — High-fidelity PDF generation using ReportLab.

Renders:
  - Header: Carbon Passport, facility metadata, reporting period.
  - Sections: Narrative markdown converted to typography.
  - Emissions Table: Scopes, categories, calculated kg CO2e, and low-high uncertainty ranges.
  - Footer: "Estimates, not a third-party audit" on every page.
  - Chemical formulas: Strictly use <sub> tags (e.g. CO<sub>2</sub>e), NEVER Unicode subscript characters.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)

from backend.schemas import Report, ReportSection


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that draws dynamic page numbers and mandatory audit disclaimer footer:
    'Estimates, not a third-party audit' on every page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))  # Slate gray

        # Running Header (top rule and title on pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 760, "Carbon Passport — MSME Supply Chain Decarbonisation Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 755, 572, 755)

        # Running Footer on EVERY page per Requirement 6
        footer_text = "Estimates, not a third-party audit"
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 40, 572, 40)

        self.drawString(40, 28, footer_text)
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(572, 28, page_str)
        self.restoreState()


def _sanitize_co2_subscripts(text: str) -> str:
    """
    Converts any Unicode subscript characters to HTML <sub> tags.
    Prompt rule: 'Use the <sub> tag for CO2 subscripts, never Unicode subscript characters.'
    """
    # Replace Unicode subscript 2 '₂' with <sub>2</sub>
    text = text.replace("CO₂e", "CO<sub>2</sub>e")
    text = text.replace("CO₂", "CO<sub>2</sub>")
    text = text.replace("tCO₂e", "tCO<sub>2</sub>e")
    text = text.replace("CO2e", "CO<sub>2</sub>e")
    text = text.replace("CO2", "CO<sub>2</sub>")
    # Clean redundant nested tags if any
    text = re.sub(r"CO<sub>\s*2\s*</sub><sub>\s*2\s*</sub>", "CO<sub>2</sub>", text)
    return text


def _markdown_to_reportlab(md: str) -> List[str]:
    """Converts basic markdown headers, bold, bullets into ReportLab paragraph strings."""
    lines = md.splitlines()
    paragraphs = []
    in_bullet_list = False

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue

        # Subscript replacement
        line_s = _sanitize_co2_subscripts(line_s)

        # Markdown bold / italic to ReportLab XML
        line_s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line_s)
        line_s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", line_s)
        line_s = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", line_s)

        # Headers
        if line_s.startswith("### "):
            paragraphs.append(("H3", line_s[4:]))
        elif line_s.startswith("## "):
            paragraphs.append(("H2", line_s[3:]))
        elif line_s.startswith("# "):
            paragraphs.append(("H1", line_s[2:]))
        elif line_s.startswith("- ") or line_s.startswith("* "):
            paragraphs.append(("BULLET", line_s[2:]))
        else:
            paragraphs.append(("BODY", line_s))

    return paragraphs


def build_report_pdf(report: Report, output_path: Path) -> Path:
    """
    Generates a PDF document from Report object and saves to output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "SecH1",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )
    h2_style = ParagraphStyle(
        "SecH2",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "BulletText",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
    )
    table_hdr_style = ParagraphStyle(
        "TableHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("CARBON PASSPORT", title_style))
    story.append(Paragraph("Enterprise Decarbonisation & Supply Chain Verification Report", subtitle_style))

    # Metadata grid
    fac_name = report.facts_snapshot.get("facility_name", "Industrial Manufacturing Facility")
    period = report.facts_snapshot.get("reporting_period", "Current Operating Cycle")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    meta_data = [
        [
            Paragraph(f"<b>Facility:</b> {fac_name}", body_style),
            Paragraph(f"<b>Reporting Period:</b> {period}", body_style),
            Paragraph(f"<b>Audit Date:</b> {date_str}", body_style),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[200, 180, 152])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # 2. Emissions Table with Low/High Ranges
    facts = report.facts_snapshot.get("facts", {})
    s1_val = facts.get("total.scope1.co2e_kg", {}).get("display", "N/A")
    s1_low = facts.get("total.scope1.low_kg", {}).get("display", "N/A")
    s1_high = facts.get("total.scope1.high_kg", {}).get("display", "N/A")

    s2_val = facts.get("total.scope2.co2e_kg", {}).get("display", "N/A")
    s2_low = facts.get("total.scope2.low_kg", {}).get("display", "N/A")
    s2_high = facts.get("total.scope2.high_kg", {}).get("display", "N/A")

    s3_val = facts.get("total.scope3.co2e_kg", {}).get("display", "N/A")
    s3_low = facts.get("total.scope3.low_kg", {}).get("display", "N/A")
    s3_high = facts.get("total.scope3.high_kg", {}).get("display", "N/A")

    tot_val = facts.get("total.all.co2e_kg", {}).get("display", "N/A")
    tot_low = facts.get("total.all.low_kg", {}).get("display", "N/A")
    tot_high = facts.get("total.all.high_kg", {}).get("display", "N/A")

    table_data = [
        [
            Paragraph("Emissions Category", table_hdr_style),
            Paragraph("Calculated CO<sub>2</sub>e", table_hdr_style),
            Paragraph("Low Bound", table_hdr_style),
            Paragraph("High Bound", table_hdr_style),
            Paragraph("Uncertainty Range", table_hdr_style),
        ],
        [
            Paragraph("<b>Scope 1:</b> Direct Combustion", table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s1_val), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s1_low), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s1_high), table_cell_style),
            Paragraph("Genset / Diesel Comb.", table_cell_style),
        ],
        [
            Paragraph("<b>Scope 2:</b> Grid Electricity", table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s2_val), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s2_low), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s2_high), table_cell_style),
            Paragraph("CO<sub>2</sub> Only (Grid WA)", table_cell_style),
        ],
        [
            Paragraph("<b>Scope 3:</b> Value Chain Freight", table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s3_val), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s3_low), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(s3_high), table_cell_style),
            Paragraph("HGV Logistics", table_cell_style),
        ],
        [
            Paragraph("<b>Total Enterprise Footprint</b>", table_cell_style),
            Paragraph(f"<b>{_sanitize_co2_subscripts(tot_val)}</b>", table_cell_style),
            Paragraph(_sanitize_co2_subscripts(tot_low), table_cell_style),
            Paragraph(_sanitize_co2_subscripts(tot_high), table_cell_style),
            Paragraph("Combined Inventory", table_cell_style),
        ],
    ]

    em_table = Table(table_data, colWidths=[150, 95, 95, 95, 97])
    em_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),  # Dark Navy
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (0, 3), (-1, 3), colors.white),
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#EFF6FF")),  # Highlight total
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(em_table)
    story.append(Spacer(1, 14))

    # 3. Report Narrative Sections
    for section in report.sections:
        story.append(Paragraph(section.title, h1_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=6))

        parsed_paragraphs = _markdown_to_reportlab(section.content_markdown)
        for p_type, p_text in parsed_paragraphs:
            if p_type == "H1":
                story.append(Paragraph(p_text, h1_style))
            elif p_type == "H2":
                story.append(Paragraph(p_text, h2_style))
            elif p_type == "H3":
                story.append(Paragraph(p_text, h2_style))
            elif p_type == "BULLET":
                story.append(Paragraph(f"&bull; {p_text}", bullet_style))
            else:
                story.append(Paragraph(p_text, body_style))

        story.append(Spacer(1, 8))

    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path


def build_report_pdf_bytes(report: Report) -> bytes:
    """Renders PDF into memory buffer and returns raw bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50,
    )
    # We can write to a temporary file or use SimpleDocTemplate on buffer
    temp_path = Path("data/cache/temp_report.pdf")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    build_report_pdf(report, temp_path)
    return temp_path.read_bytes()
