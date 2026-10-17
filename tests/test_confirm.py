from fastapi.testclient import TestClient

import app.config as config
from app.main import app

client = TestClient(app)


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "templates_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path / "configs"))


def _stage(tmp_path, proposal_id="p1", with_config=False):
    staged = tmp_path / ".staging" / proposal_id
    staged.mkdir(parents=True)
    (staged / "form_template.pdf").write_bytes(b"%PDF-1.4")
    if with_config:
        (staged / "config.yaml").write_text("client_name: pending\nfields: []\n")


def test_duplicate_slug_is_refused(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path)
    _stage(tmp_path)
    (tmp_path / "configs" / "universitat-koln").mkdir(parents=True)  # already on board

    r = client.post(
        "/api/forms/confirm-schema",
        json={"proposal_id": "p1", "institution_name": "Universität Köln"},
    )
    assert r.status_code == 409


def test_blank_name_is_rejected(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path)
    _stage(tmp_path)

    r = client.post(
        "/api/forms/confirm-schema",
        json={"proposal_id": "p1", "institution_name": "   "},
    )
    assert r.status_code == 422


def test_saves_config_and_template(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path)
    _stage(tmp_path, with_config=True)

    r = client.post(
        "/api/forms/confirm-schema",
        json={"proposal_id": "p1", "institution_name": "Universität Köln"},
    )
    assert r.json()["client_name"] == "universitat-koln"
    assert (tmp_path / "configs" / "universitat-koln" / "config.yaml").exists()
    assert (tmp_path / "universitat-koln" / "form_template.pdf").exists()
