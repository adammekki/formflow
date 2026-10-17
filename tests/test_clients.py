from fastapi.testclient import TestClient
import pytest
import yaml

import app.config as config
from app.main import app

client = TestClient(app)


def _patch_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path / "configs"))
    monkeypatch.setattr(config.settings, "templates_dir", str(tmp_path / "templates"))
    (tmp_path / "configs").mkdir()
    (tmp_path / "templates").mkdir()


def _add_university(tmp_path, name, config_text):
    config_dir = tmp_path / "configs" / name
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(config_text)
    template_dir = tmp_path / "templates" / name
    template_dir.mkdir(parents=True)
    (template_dir / "form_template.pdf").write_bytes(b"%PDF-1.4")


@pytest.mark.parametrize("uni", ["uni-hamburg", "uni-heidelberg", "uni-koln", "uni-ulm"])
def test_bundled_configs_carry_a_display_name(uni):
    """The dropdown shows this, so every shipped config needs one."""
    with open(f"configs/{uni}/config.yaml") as fh:
        loaded = yaml.safe_load(fh)
    assert loaded.get("institution_name")


def test_lists_institution_names(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    _add_university(
        tmp_path,
        "uni-hamburg",
        "client_name: uni-hamburg\ninstitution_name: Universität Hamburg\nfields: []\n",
    )

    clients = client.get("/api/forms/clients").json()["clients"]
    assert clients[0]["institution_name"] == "Universität Hamburg"


def test_falls_back_to_directory_name(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    _add_university(tmp_path, "legacy", "client_name: legacy\nfields: []\n")

    clients = client.get("/api/forms/clients").json()["clients"]
    assert clients[0]["institution_name"] == "legacy"


def test_university_without_a_form_template_is_not_listed(tmp_path, monkeypatch):
    """A config with no form cannot fill anything, so it must not be offered."""
    _patch_dirs(monkeypatch, tmp_path)
    ghost = tmp_path / "configs" / "ghost"
    ghost.mkdir()
    (ghost / "config.yaml").write_text(
        "client_name: ghost\ninstitution_name: Ghost University\nfields: []\n"
    )

    assert client.get("/api/forms/clients").json()["clients"] == []
