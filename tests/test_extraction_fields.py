import pytest

from app.services.pipeline import FormFillingPipeline


def _pipeline(config):
    p = FormFillingPipeline.__new__(FormFillingPipeline)  # skip __init__/config load
    p.client_name = "uni-hamburg"
    p.config = config
    return p


@pytest.mark.asyncio
async def test_mock_extraction_returns_dummy_values_without_the_model(monkeypatch):
    """With MOCK_EXTRACTION on, the review screen can be seen in seconds."""
    monkeypatch.setattr("app.config.settings.mock_extraction", True)
    monkeypatch.setattr("app.config.settings.mock_extraction_seconds", 0)

    pipeline = _pipeline(
        {
            "fields": [
                {"field_name": "Name", "semantic_name": "Last Name"},
                {"field_name": "IBAN", "semantic_name": "IBAN Account Number"},
            ]
        }
    )

    fields = (await pipeline.extract([]))["fields"]

    assert [f["field_name"] for f in fields] == ["Name", "IBAN"]
    assert fields[0]["semantic_name"] == "Last Name"
    assert fields[0]["source_document"]
    # A spread of confidences, so the review screen shows its real states.
    assert len({f["confidence"] for f in fields}) > 1


def test_parse_attaches_the_form_s_plain_language_name():
    """The review screen shows semantic_name, so it must survive parsing."""
    pipeline = _pipeline(
        {"fields": [{"field_name": "UHD", "semantic_name": "Personnel number"}]}
    )

    fields = pipeline._parse_extraction_response(
        '{"fields": [{"field_name": "UHD", "value": "12345", "confidence": 0.9}]}'
    )

    assert fields[0]["semantic_name"] == "Personnel number"


def test_parse_leaves_semantic_name_empty_when_the_config_lacks_one():
    pipeline = _pipeline({"fields": [{"field_name": "UHD"}]})

    fields = pipeline._parse_extraction_response(
        '{"fields": [{"field_name": "UHD", "value": "12345", "confidence": 0.9}]}'
    )

    assert fields[0]["semantic_name"] is None
