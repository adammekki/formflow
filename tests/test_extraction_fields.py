from app.services.pipeline import FormFillingPipeline


def _pipeline(config):
    p = FormFillingPipeline.__new__(FormFillingPipeline)  # skip __init__/config load
    p.client_name = "uni-hamburg"
    p.config = config
    return p


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
