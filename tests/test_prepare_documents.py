import io, os
import fitz
from PIL import Image
from PIL.ExifTags import Base as ExifBase
from app.services.pipeline import FormFillingPipeline


def _pipeline():
    p = FormFillingPipeline.__new__(FormFillingPipeline)
    p.client_name = "uni-hamburg"
    p.config = {}
    return p


def _make_pdf(path, pages):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")
    doc.save(path)
    doc.close()


def test_saves_full_size_pages_and_manifest(tmp_path):
    pdf = tmp_path / "receipt one.pdf"
    _make_pdf(pdf, 2)
    pages_dir = tmp_path / "pages"

    _, _, docs = _pipeline()._prepare_documents([str(pdf)], str(pages_dir))

    assert docs == [{"name": "receipt one.pdf", "page_count": 2}]
    for pi in (0, 1):
        f = pages_dir / f"doc00_p{pi:03d}.jpg"
        assert f.exists()
        with Image.open(f) as img:
            assert img.width > 1024  # full-size, not the model resize


def test_image_upload_is_exif_transposed_and_saved(tmp_path):
    img_path = tmp_path / "photo.jpg"
    img = Image.new("RGB", (100, 200), "white")
    exif = img.getexif(); exif[ExifBase.Orientation] = 6
    img.save(img_path, exif=exif)
    pages_dir = tmp_path / "pages"

    _, _, docs = _pipeline()._prepare_documents([str(img_path)], str(pages_dir))

    assert docs == [{"name": "photo.jpg", "page_count": 1}]
    with Image.open(pages_dir / "doc00_p000.jpg") as out:
        assert (out.width, out.height) == (200, 100)  # rotated upright
