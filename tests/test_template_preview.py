import os
import shutil
import tempfile

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routers.extraction import verification_sessions
from app.services.pdf_form import render_template_preview, template_field_rects

client = TestClient(app)


def _form_pdf(path: str, name: str = "AntragstellerIn_Name") -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_name = name
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 72, 300, 90)
    page.add_widget(widget)
    doc.save(path)
    doc.close()


def test_template_field_rects_reports_page_and_rect(tmp_path):
    form = tmp_path / "form.pdf"
    _form_pdf(form, "AntragstellerIn_Name")

    fields = template_field_rects(str(form))

    assert fields[0]["field_name"] == "AntragstellerIn_Name"
    assert fields[0]["page"] == 0
    assert fields[0]["x"] == pytest.approx(72, abs=1)
    assert fields[0]["width"] == pytest.approx(228, abs=1)


def test_render_template_preview_scales_rects_to_rendered_pixels(tmp_path):
    form = tmp_path / "form.pdf"
    _form_pdf(form, "Reiseziel")
    out_dir = tmp_path / "template_pages"

    preview = render_template_preview(str(form), str(out_dir))

    assert preview["pages"][0]["page"] == 0
    with Image.open(os.path.join(out_dir, "p000.jpg")) as img:
        scale = img.width / 595  # A4 width in points
        assert preview["pages"][0]["width"] == img.width
    assert preview["fields"][0]["field_name"] == "Reiseziel"
    assert preview["fields"][0]["x"] == pytest.approx(72 * scale, abs=2)


@pytest.fixture()
def fake_template_session():
    temp_dir = tempfile.mkdtemp(prefix="formflow_tpl_")
    template_dir = os.path.join(temp_dir, "template_pages")
    os.makedirs(template_dir)
    Image.new("RGB", (10, 10), "white").save(os.path.join(template_dir, "p000.jpg"))
    verification_sessions["tpl1"] = {
        "temp_dir": temp_dir,
        "client_name": "uni-ulm",
        "extracted_data": [],
        "receipt_paths": [],
        "documents": [],
        "pages_dir": os.path.join(temp_dir, "pages"),
        "template": {
            "pages": [{"page": 0, "width": 10, "height": 10}],
            "fields": [
                {"field_name": "Reiseziel", "page": 0, "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}
            ],
        },
    }
    yield
    verification_sessions.pop("tpl1", None)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_serves_the_template_manifest(fake_template_session):
    r = client.get("/api/extract/session/tpl1/template")

    assert r.status_code == 200
    assert r.json()["fields"][0]["field_name"] == "Reiseziel"


def test_serves_a_template_page_image(fake_template_session):
    r = client.get("/api/extract/session/tpl1/template/pages/0.jpg")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


def test_missing_template_page_is_404(fake_template_session):
    assert client.get("/api/extract/session/tpl1/template/pages/9.jpg").status_code == 404
