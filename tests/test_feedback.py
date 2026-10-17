import json

import pytest

from app.config import settings
from app.services.pipeline import FormFillingPipeline


def _pipeline():
    p = FormFillingPipeline.__new__(FormFillingPipeline)
    p.client_name = "uni-hamburg"
    p.config = {}
    return p


@pytest.mark.asyncio
async def test_feedback_keeps_bounding_boxes(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "feedback_dir", str(tmp_path))
    box = {"page": 0, "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}
    original = [
        {"field_name": "kept", "value": "A", "bounding_box": box},
        {"field_name": "fixed", "value": "B", "bounding_box": box},
    ]

    await _pipeline().store_feedback("sess1", original, {"fixed": "B2"}, [])

    with open(tmp_path / "uni-hamburg" / "sess1.json") as f:
        data = json.load(f)
    entries = {c["field_name"]: c for c in data["corrections"]}
    assert entries["kept"]["bounding_box"] == box
    assert entries["fixed"]["bounding_box"] == box
