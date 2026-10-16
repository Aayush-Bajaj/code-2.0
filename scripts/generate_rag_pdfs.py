"""
Helper script to generate SEBI BRSR and GHG Protocol reference PDFs in data/rag_docs/
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "rag_docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def build_brsr_pdf():
    pdf_path = DOCS_DIR / "sebi_brsr_framework.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, spaceAfter=10)
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=12, leading=16, spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=13, spaceAfter=6)
    
    story = [
        Paragraph("Securities and Exchange Board of India (SEBI)", title_style),
        Paragraph("Business Responsibility and Sustainability Reporting (BRSR) Core Framework", h2_style),
        Paragraph("Principle 6: Businesses should respect and make efforts to protect and restore the environment.", body_style),
        Spacer(1, 10),
        Paragraph("1. Essential Indicators - Greenhouse Gas Emissions (Scope 1 and Scope 2)", h2_style),
        Paragraph(
            "Under Principle 6 of the BRSR format, entities must disclose gross Scope 1 and gross Scope 2 greenhouse gas emissions "
            "expressed in metric tonnes of CO<sub>2</sub> equivalent (tCO<sub>2</sub>e). Scope 1 emissions encompass direct emissions "
            "from owned or controlled sources, such as stationary fuel combustion in backup generators (diesel gensets), boilers, and furnaces, "
            "as well as mobile combustion from company-operated vehicles. Scope 2 emissions encompass indirect emissions from the generation "
            "of purchased electricity, heat, or steam consumed by the reporting entity.",
            body_style
        ),
        Spacer(1, 6),
        Paragraph("2. Scope 3 Emissions in Value Chains and Supply Chains", h2_style),
        Paragraph(
            "Under leadership indicators, companies are encouraged to map and report Scope 3 upstream and downstream emissions, "
            "specifically freight logistics, transportation of raw materials, and supplier operations. For MSME vendors supplying to "
            "top listed companies, primary energy and fuel records are requested to substantiate Scope 3 emissions calculations.",
            body_style
        ),
        Spacer(1, 6),
        Paragraph("3. GHG Emission Intensity Metrics", h2_style),
        Paragraph(
            "Disclosures must state emissions intensity per rupee of turnover or physical unit of production output. "
            "Data should be substantiated by verifiable bills, utility meter readings, and operational runtime logs. "
            "Independent third-party audits are required for top listed firms, while supply-chain outputs support the data these frameworks request.",
            body_style
        ),
    ]
    doc.build(story)
    print(f"Generated {pdf_path}")


def build_ghg_protocol_pdf():
    pdf_path = DOCS_DIR / "ghg_protocol_corporate_standard.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, spaceAfter=10)
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=12, leading=16, spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=13, spaceAfter=6)
    
    story = [
        Paragraph("GHG Protocol Corporate Accounting and Reporting Standard", title_style),
        Paragraph("World Resources Institute (WRI) and World Business Council for Sustainable Development (WBCSD)", h2_style),
        Spacer(1, 10),
        Paragraph("Chapter 4: Setting Operational Boundaries - Scopes 1, 2, and 3", h2_style),
        Paragraph(
            "The GHG Protocol defines three operational accounting scopes to categorize direct and indirect emission sources: "
            "<br/><b>Scope 1 Direct GHG Emissions:</b> Emissions from operations owned or controlled by the organization, including combustion of fossil fuels (diesel, natural gas, petrol) in stationary equipment such as generators and furnaces. "
            "<br/><b>Scope 2 Electricity Indirect Emissions:</b> Emissions resulting from the generation of purchased electricity consumed by the company. Scope 2 accounting requires reporting location-based grid average emission factors published by regional electrical authorities. "
            "<br/><b>Scope 3 Other Indirect Emissions:</b> An optional reporting category that accounts for all other indirect emissions resulting from organization activities from sources not owned or controlled, notably upstream freight and distribution.",
            body_style
        ),
        Spacer(1, 6),
        Paragraph("Chapter 6: Calculating GHG Emissions and Activity Data", h2_style),
        Paragraph(
            "Emissions must be calculated through the fundamental equation: "
            "<br/><b>GHG Emissions (kg CO<sub>2</sub>e) = Activity Data x Emission Factor</b><br/>"
            "Activity data measures the magnitude of human activity resulting in greenhouse gas emissions (e.g., litres of diesel fuel consumed, kilowatt-hours of grid electricity used, or tonne-kilometres of freight transported). Emission factors quantify the mass of greenhouse gas emitted per unit of activity.",
            body_style
        ),
        Spacer(1, 6),
        Paragraph("Chapter 9: Managing Inventory Quality and Uncertainty Ranges", h2_style),
        Paragraph(
            "Emissions estimations inherently carry scientific and measurement uncertainty. In manufacturing environments with imperfect records, uncertainty ranges (low and high bounds) must be explicitly quantified to account for equipment maintenance degradation, load variations, and fuel quality tolerances. Reports must clearly declare that emissions figures are estimates subject to stated assumptions and do not constitute formal third-party regulatory certification.",
            body_style
        ),
    ]
    doc.build(story)
    print(f"Generated {pdf_path}")


if __name__ == "__main__":
    build_brsr_pdf()
    build_ghg_protocol_pdf()
