from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
SAMPLE = Path(__file__).parent / "sample_invoice.pdf"


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_extract_returns_text():
    with open(SAMPLE, "rb") as f:
        r = client.post("/extract", files={"file": ("sample_invoice.pdf", f, "application/pdf")})
    assert r.status_code == 200
    assert r.json()["has_text"] is True
    assert "2350 AZN" in r.json()["text"]


def test_extract_rejects_non_pdf():
    r = client.post("/extract", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400


def test_validate_flags_bad_invoice():
    bad = {"type": "invoice", "amount": 0, "currency": "AZN", "due_date": "", "confidence": 0.99}
    r = client.post("/validate", json=bad)
    assert r.json()["status"] == "needs_review"
    assert r.json()["valid"] is False
