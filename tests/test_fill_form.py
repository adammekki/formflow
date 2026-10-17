import pytest

from app.services.pdf_form import read_form_fields
from app.services.pipeline import FormFillingPipeline

EXTRACTED = [
    {"field_name": "Name", "value": "Original"},
    {"field_name": "Vorname", "value": "Keepme"},
]


@pytest.fixture
def pipeline(monkeypatch):
    p = FormFillingPipeline.__new__(FormFillingPipeline)  # skip __init__/config load
    p.client_name = "uni-hamburg"
    return p


def _stage_template(tmp_path):
    (tmp_path / "uni-hamburg").mkdir()
    (tmp_path / "uni-hamburg" / "form_template.pdf").write_bytes(
        open("templates/uni-hamburg/form_template.pdf", "rb").read()
    )


@pytest.mark.asyncio
async def test_keeps_only_ticked_fields(pipeline, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    _stage_template(tmp_path)
    result = await pipeline.fill_form(EXTRACTED, {"Name": "Corrected"}, kept_fields=["Name"])
    fields = read_form_fields(result["path"])
    assert fields["Name"] == "Corrected"
    assert not fields["Vorname"]


@pytest.mark.asyncio
async def test_unknown_kept_field_is_ignored(pipeline, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    _stage_template(tmp_path)
    result = await pipeline.fill_form(EXTRACTED, {}, kept_fields=["Name", "Nonexistent"])
    assert read_form_fields(result["path"])["Name"] == "Original"


@pytest.mark.asyncio
async def test_unmatched_fields_are_reported(pipeline, tmp_path, monkeypatch):
    """A field name the form does not have must be reported, not dropped."""
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    _stage_template(tmp_path)
    result = await pipeline.fill_form(
        EXTRACTED + [{"field_name": "NotOnThisForm", "value": "x"}], {}
    )
    assert result["unmatched_fields"] == ["NotOnThisForm"]
