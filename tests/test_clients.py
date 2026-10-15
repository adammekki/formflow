from fastapi.testclient import TestClient

import app.config as config
from app.main import app

client = TestClient(app)


def test_lists_institution_names(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path))
    d = tmp_path / "uni-hamburg"
    d.mkdir()
    (d / "config.yaml").write_text(
        "client_name: uni-hamburg\ninstitution_name: Universität Hamburg\nfields: []\n"
    )

    clients = client.get("/api/forms/clients").json()["clients"]
    assert clients[0]["institution_name"] == "Universität Hamburg"


def test_falls_back_to_directory_name(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path))
    d = tmp_path / "legacy"
    d.mkdir()
    (d / "config.yaml").write_text("client_name: legacy\nfields: []\n")

    clients = client.get("/api/forms/clients").json()["clients"]
    assert clients[0]["institution_name"] == "legacy"
