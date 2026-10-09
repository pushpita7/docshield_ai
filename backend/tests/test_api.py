
from io import BytesIO

import pymupdf
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app


client = TestClient(app)


def make_test_image():
    """Create a synthetic image in memory."""
    image = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((180, 100, 420, 250), fill="gray")
    draw.text((30, 30), "SYNTHETIC TEST DOCUMENT", fill="black")

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def make_test_pdf():
    """Create a synthetic PDF in memory."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 80), "SYNTHETIC DOCSHIELD TEST")
    page.insert_text((60, 120), "Not a real certificate.")

    output = doc.tobytes()
    doc.close()
    return output


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_risk_score_with_findings():
    payload = {
        "findings": [
            {
                "finding_id": "visual-test-001",
                "category": "visual",
                "type": "possible_visual_anomaly",
                "severity": "high",
                "page": 1,
                "message": "Synthetic test finding.",
                "confidence": 0.8,
                "evidence": {
                    "x": 10,
                    "y": 20,
                    "width": 100,
                    "height": 50
                }
            }
        ]
    }

    response = client.post("/api/risk-score", json=payload)

    assert response.status_code == 200

    result = response.json()
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in [
        "VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"
    ]
    assert result["findings_count"] == 1
    assert "summary" in result


def test_empty_risk_score():
    response = client.post(
        "/api/risk-score",
        json={"findings": []}
    )

    assert response.status_code == 200
    assert response.json()["risk_score"] == 0
    assert response.json()["risk_level"] == "VERY LOW"


def test_duplicate_finding_ids_count_once():
    finding = {
        "finding_id": "duplicate-001",
        "category": "visual",
        "type": "possible_visual_anomaly",
        "severity": "high",
        "page": 1,
        "message": "Synthetic duplicate test.",
        "confidence": 0.8,
        "evidence": {}
    }

    response = client.post(
        "/api/risk-score",
        json={"findings": [finding, finding]}
    )

    assert response.status_code == 200
    assert response.json()["findings_count"] == 1


def test_visual_analysis():
    response = client.post(
        "/api/visual-analysis",
        files={
            "file": (
                "synthetic.png",
                make_test_image(),
                "image/png"
            )
        }
    )

    assert response.status_code == 200

    result = response.json()
    assert result["image_width"] == 600
    assert result["image_height"] == 400
    assert isinstance(result["findings"], list)
    assert result["heatmap_format"] == "png"
    assert len(result["heatmap_base64"]) > 0
    assert result["original_document_stored"] is False


def test_invalid_image_rejected():
    response = client.post(
        "/api/visual-analysis",
        files={
            "file": (
                "broken.png",
                b"not a real image",
                "image/png"
            )
        }
    )

    assert response.status_code == 400


def test_pdf_analysis():
    response = client.post(
        "/api/pdf-analysis",
        files={
            "file": (
                "synthetic.pdf",
                make_test_pdf(),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 200

    result = response.json()
    assert result["page_count"] == 1
    assert result["pdf_object_count"] > 0
    assert len(result["pages"]) == 1
    assert isinstance(result["findings"], list)


def test_invalid_pdf_rejected():
    response = client.post(
        "/api/pdf-analysis",
        files={
            "file": (
                "broken.pdf",
                b"not a real PDF",
                "application/pdf"
            )
        }
    )

    assert response.status_code == 400