
from datetime import datetime, timezone
from typing import Any, Literal

import base64

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.services.visual_forensics import analyze_image_bytes
from app.services.pdf_forensics import analyze_pdf_bytes

import uuid

from fastapi.responses import Response
from app.services.history import (
    initialize_history,
    save_analysis,
    get_analysis,
    list_history,
)
from app.services.reporting import generate_report


app = FastAPI(
    title="DocShield AI API",
    description="Visual and PDF forensics, risk scoring, and document verification.",
    version="1.0.0",
)
initialize_history()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------- Shared finding schema ----------

class Evidence(BaseModel):
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    finding_id: str
    category: str
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    page: int | None = None
    message: str
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence = Field(default_factory=Evidence)


class RiskRequest(BaseModel):
    findings: list[Finding] = Field(default_factory=list)


# ---------- Risk scoring configuration ----------

SEVERITY_WEIGHTS = {
    "low": 10,
    "medium": 25,
    "high": 50,
    "critical": 80,
}

CATEGORY_WEIGHTS = {
    "text": 1.0,
    "metadata": 0.9,
    "fonts": 0.9,
    "consistency": 1.0,
    "visual": 1.1,
    "pdf_structure": 1.1,
    "signature": 1.0,
}

RISK_LEVELS = [
    (20, "VERY LOW"),
    (40, "LOW"),
    (60, "MODERATE"),
    (80, "HIGH"),
    (100, "VERY HIGH"),
]


def calculate_risk(findings: list[Finding]) -> dict[str, Any]:
    # Ignore repeated finding IDs so duplicate submissions
    # do not inflate the risk score.
    unique_findings = []
    seen_ids = set()

    for finding in findings:
        if finding.finding_id in seen_ids:
            continue

        seen_ids.add(finding.finding_id)
        unique_findings.append(finding)

    # Combine independent risk contributions.
    remaining_safety = 1.0

    for finding in unique_findings:
        severity_weight = SEVERITY_WEIGHTS[finding.severity]
        category = finding.category.strip().lower()
        category_weight = CATEGORY_WEIGHTS.get(category, 1.0)

        contribution = (
            severity_weight
            * finding.confidence
            * category_weight
        )

        # Prevent a single finding from contributing more than 100.
        contribution = min(contribution, 100.0)

        remaining_safety *= 1.0 - contribution / 100.0

    risk_score = round((1.0 - remaining_safety) * 100)
    risk_score = max(0, min(100, risk_score))

    for maximum, level in RISK_LEVELS:
        if risk_score <= maximum:
            risk_level = level
            break
    else:
        risk_level = "VERY HIGH"

    if not unique_findings:
        summary = "No findings were submitted. This does not establish document authenticity."
    elif risk_score <= 20:
        summary = "Few or low-weight suspicious indicators were detected. Verification may still be necessary."
    elif risk_score <= 40:
        summary = "Some suspicious indicators were detected. Review the findings and supporting evidence."
    elif risk_score <= 60:
        summary = "Several or stronger suspicious indicators were detected. Further verification is recommended."
    elif risk_score <= 80:
        summary = "Multiple significant suspicious indicators were detected. Verify the document with its issuer."
    else:
        summary = "Numerous or strong suspicious indicators were detected. Prompt independent verification is recommended."

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "summary": summary,
        "findings_count": len(unique_findings),
        "methodology": (
            "Severity weight × confidence × category multiplier. "
            "Contributions are combined using a cumulative-risk formula. "
            "Repeated finding IDs are counted once. This is a screening "
            "heuristic, not a probability of fraud."
        ),
    }


# ---------- API endpoints ----------

@app.get("/")
def root():
    return {
        "message": "DocShield AI API is running",
        "documentation": "/docs",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "DocShield AI",
        "timestamp": datetime.now(timezone.utc),
    }


@app.post("/api/test-finding")
def test_finding(finding: Finding):
    return {
        "accepted": True,
        "finding": finding.model_dump(),
    }


@app.post("/api/risk-score")
def risk_score(request: RiskRequest):
    return calculate_risk(request.findings)


@app.post("/api/visual-analysis")
async def visual_analysis(file: UploadFile = File(...)):
    """Analyze an uploaded image without storing the original."""
    allowed_types = {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/tiff",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image type. Upload PNG, JPEG, WEBP, or TIFF.",
        )

    try:
        image_bytes = await file.read(10 * 1024 * 1024 + 1)

        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 10 MB limit.",
            )

        result = analyze_image_bytes(image_bytes)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    finally:
        await file.close()

    findings = []

    for index, region in enumerate(result["regions"], start=1):
        findings.append({
            "finding_id": f"visual-{index:03d}",
            "category": "visual",
            "type": "possible_visual_anomaly",
            "severity": "medium",
            "page": 1,
            "message": "Potential manipulation detected. Review this image region.",
            "confidence": 0.55,
            "evidence": {
                "x": region["x"],
                "y": region["y"],
                "width": region["width"],
                "height": region["height"],
                "details": {
                    "reason": region["reason"],
                    "area_pixels": region["area"],
                    "coordinate_system": "image_pixels",
                },
            },
        })

    return {
        "image_width": result["image_width"],
        "image_height": result["image_height"],
        "findings": findings,
        "finding_count": len(findings),
        "message": result["message"],
        "heatmap_format": "png",
        "heatmap_base64": base64.b64encode(
            result["heatmap_png"]
        ).decode("ascii"),
        "original_document_stored": False,
    }


@app.post("/api/pdf-analysis")
async def pdf_analysis(file: UploadFile = File(...)):
    """Inspect PDF structure without retaining the uploaded original."""
    if file.content_type not in (
        "application/pdf",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=415,
            detail="Please upload a PDF file.",
        )

    try:
        pdf_bytes = await file.read(20 * 1024 * 1024 + 1)

        if len(pdf_bytes) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="PDF exceeds the 20 MB upload limit.",
            )

        if not pdf_bytes.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file does not have a valid PDF header.",
            )

        result = analyze_pdf_bytes(pdf_bytes)

        return result

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    finally:
        await file.close()


@app.post("/api/analyze-demo")
def analyze_demo():
    """Create a synthetic analysis record to test history and reports."""
    demo_findings = [
        {
            "finding_id": "demo-visual-001",
            "category": "visual",
            "type": "possible_visual_anomaly",
            "severity": "medium",
            "page": 1,
            "message": "Synthetic demo finding for testing.",
            "confidence": 0.65,
            "evidence": {
                "x": 100,
                "y": 120,
                "width": 80,
                "height": 40,
            },
        }
    ]

    validated = [Finding(**item) for item in demo_findings]
    risk = calculate_risk(validated)

    record = save_analysis(
        document_id=str(uuid.uuid4()),
        document_name="synthetic-demo.pdf",
        risk=risk,
        findings=demo_findings,
    )

    return record


@app.get("/api/history")
def history_endpoint():
    return {"analyses": list_history()}


@app.get("/api/history/{document_id}")
def history_detail(document_id: str):
    record = get_analysis(document_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis record not found.",
        )

    return record


@app.get("/api/report/{document_id}")
def report_endpoint(document_id: str):
    record = get_analysis(document_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis record not found.",
        )

    pdf_bytes = generate_report(record)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="docshield-report-{document_id}.pdf"'
            )
        },
    )