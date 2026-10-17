import io
import shutil

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.routers.extraction import verification_sessions
from app.services.pipeline import FormFillingPipeline

client = TestClient(app)


def test_process_survives_locator_failure(tmp_path, monkeypatch):
    """Box location is an aid: a failure in it must not fail extraction."""
    configs_dir = tmp_path / "configs" / "uni-hamburg"
    configs_dir.mkdir(parents=True)
    (configs_dir / "config.yaml").write_text("fields: []\n")
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path / "configs"))

    async def fake_extract(self, receipt_paths, pages_dir=None):
        return {
            "fields": [
                {
                    "field_name": "Name",
                    "value": "Müller",
                    "source_document": "a.pdf",
                    "bounding_box": None,
                    "confidence": 0.9,
                    "reasoning": None,
                }
            ],
            "documents": [{"name": "a.pdf", "page_count": 1}],
        }

    def boom(*args, **kwargs):
        raise RuntimeError("tesseract not installed")

    monkeypatch.setattr(FormFillingPipeline, "extract", fake_extract)
    monkeypatch.setattr("app.routers.extraction.locate_fields", boom)

    response = client.post(
        "/api/extract/process",
        data={"client_name": "uni-hamburg"},
        files={"receipts": ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["extracted_fields"][0]["bounding_box"] is None

    session = verification_sessions.pop(response.json()["session_id"], None)
    if session:
        shutil.rmtree(session["temp_dir"], ignore_errors=True)
