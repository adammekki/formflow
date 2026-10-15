from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_non_fillable_pdf_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    monkeypatch.setattr("app.config.settings.configs_dir", str(tmp_path / "configs"))
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    blank = str(tmp_path / "blank.pdf")
    doc.save(blank)

    with open(blank, "rb") as fh:
        r = client.post(
            "/api/forms/discover-schema",
            files={"form_template": ("blank.pdf", fh, "application/pdf")},
        )

    assert r.status_code == 200
    assert r.json()["status"] == "error"
    assert "field" in r.json()["error"].lower()


def test_staging_does_not_write_a_config(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    monkeypatch.setattr("app.config.settings.configs_dir", str(tmp_path / "configs"))
    monkeypatch.setattr(
        "app.routers.forms.FormSchemaDiscoveryAgent.discover_schema", _fake_discover
    )

    with open("templates/uni-hamburg/form_template.pdf", "rb") as fh:
        r = client.post(
            "/api/forms/discover-schema",
            files={"form_template": ("f.pdf", fh, "application/pdf")},
        )

    body = r.json()
    assert body["institution_name"] == "Universität Hamburg"
    assert not (tmp_path / "configs").exists()
    assert (tmp_path / ".staging" / body["proposal_id"] / "form_template.pdf").exists()


async def _fake_discover(self, pdf_bytes, client_name=None):
    return {
        "institution_name": "Universität Hamburg",
        "form_title": "Reisekosten",
        "form_language": "German",
        "fields": [
            {
                "field_name": "Name",
                "data_type": "text",
                "description": "Surname",
                "required": True,
            }
        ],
        "pdf_fields_raw": {"Name": ""},
    }
