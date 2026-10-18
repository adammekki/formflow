import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routers.extraction import verification_sessions

client = TestClient(app)


@pytest.fixture()
def fake_session():
    temp_dir = tempfile.mkdtemp(prefix="formflow_test_")
    pages_dir = os.path.join(temp_dir, "pages")
    os.makedirs(pages_dir)
    Image.new("RGB", (10, 10), "white").save(os.path.join(pages_dir, "doc00_p000.jpg"))
    verification_sessions["s1"] = {
        "temp_dir": temp_dir,
        "client_name": "uni-hamburg",
        "extracted_data": [],
        "receipt_paths": [],
        "documents": [{"name": "hotel.pdf", "page_count": 1}],
        "pages_dir": pages_dir,
    }
    yield
    verification_sessions.pop("s1", None)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_serves_a_session_page(fake_session):
    r = client.get("/api/extract/session/s1/pages/0/0.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


def test_missing_page_is_404(fake_session):
    assert client.get("/api/extract/session/s1/pages/0/9.jpg").status_code == 404


def test_missing_session_is_404(fake_session):
    assert client.get("/api/extract/session/nope/pages/0/0.jpg").status_code == 404


def test_session_manifest_lists_documents(fake_session):
    r = client.get("/api/extract/session/s1")
    assert r.status_code == 200
    assert r.json()["documents"] == [{"name": "hotel.pdf", "page_count": 1}]
