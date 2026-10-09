
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


LIMITATION = (
    "AI-assisted forensic analysis does not establish that a document "
    "is fraudulent. Official verification with the issuing organization "
    "should be performed when authenticity is critical."
)


def generate_report(analysis):
    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("DocShield AI", styles["Title"]))
    story.append(Paragraph("Document Forensic Analysis Report", styles["Heading2"]))
    story.append(Spacer(1, 12))

    info = [
        ["Document", str(analysis["document_name"])],
        ["Document ID", str(analysis["document_id"])],
        ["Analysis timestamp", str(analysis["created_at"])],
        ["Risk score", f'{analysis["risk_score"]}/100'],
        ["Risk level", str(analysis["risk_level"])],
        ["Findings", str(analysis["findings_count"])],
    ]

    table = Table(info, colWidths=[42 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEF7")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)

    story.append(Spacer(1, 14))
    story.append(Paragraph("Verification Summary", styles["Heading2"]))
    story.append(Paragraph(str(analysis["summary"]), styles["BodyText"]))

    story.append(Spacer(1, 14))
    story.append(Paragraph("Findings and Evidence", styles["Heading2"]))

    findings = analysis.get("findings", [])

    if not findings:
        story.append(Paragraph(
            "No findings were recorded. This does not prove authenticity.",
            styles["BodyText"],
        ))

    for finding in findings:
        evidence = finding.get("evidence") or {}

        story.append(Paragraph(
            f'{finding.get("category", "unknown")} — '
            f'{finding.get("type", "finding")}',
            styles["Heading3"],
        ))

        details = [
            f'Severity: {finding.get("severity", "unknown")}',
            f'Confidence: {finding.get("confidence", "unknown")}',
            f'Page: {finding.get("page", "not specified")}',
            f'Message: {finding.get("message", "")}',
            f'Evidence coordinates: {evidence}',
        ]

        for detail in details:
            story.append(Paragraph(str(detail), styles["BodyText"]))
            story.append(Spacer(1, 3))

        story.append(Spacer(1, 8))

    story.append(Paragraph("Methodology", styles["Heading2"]))
    story.append(Paragraph(
        "The risk score combines finding severity, confidence and category "
        "weighting using a cumulative-risk heuristic. It is a screening score, "
        "not a calibrated probability of fraud.",
        styles["BodyText"],
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Limitations", styles["Heading2"]))
    story.append(Paragraph(LIMITATION, styles["BodyText"]))

    doc.build(story)
    return output.getvalue()