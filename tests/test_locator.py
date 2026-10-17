from app.services.locator import Word, match_words, normalize, parse_date, parse_number


def w(text, x0=0, y0=0, line=0, conf=100.0):
    return Word(x0=x0, y0=y0, x1=x0 + 50, y1=y0 + 12, text=text, line=line, conf=conf)


def test_normalize_folds_case_accents_and_whitespace():
    assert normalize("  Müller,\n JÖRG ") == "muller, jorg"


def test_parse_number_dot_decimal():
    assert parse_number("EUR 192.50") == 192.5


def test_parse_number_german_comma_decimal():
    assert parse_number("192,50") == 192.5


def test_parse_number_german_thousands():
    assert parse_number("1.234,56") == 1234.56


def test_parse_number_bare_three_digit_group_is_thousands():
    assert parse_number("1.234") == 1234


def test_parse_number_rejects_dates():
    assert parse_number("14.03.2025") is None


def test_parse_number_rejects_non_numbers():
    assert parse_number("Berlin") is None


def test_parse_date_iso():
    assert parse_date("2025-03-14") == "2025-03-14"


def test_parse_date_german_dot():
    assert parse_date("14.03.2025") == "2025-03-14"


def test_parse_date_slash_two_digit_year():
    assert parse_date("14/03/25") == "2025-03-14"


def test_parse_date_german_month_name():
    assert parse_date("14. März 2025") == "2025-03-14"


def test_match_words_exact_window():
    words = [w("Dr."), w("Maximilian", x0=60), w("Hofmann", x0=170)]
    assert match_words(words, "Dr. Maximilian Hofmann") == (0, 0, 220, 12)


def test_match_words_reformatted_amount():
    words = [w("EUR"), w("192.50", x0=60)]
    assert match_words(words, "192.5") == (0, 0, 110, 12)


def test_match_words_german_date_for_iso_value():
    words = [w("14.03.2025")]
    assert match_words(words, "2025-03-14") == (0, 0, 50, 12)


def test_match_words_first_occurrence_wins():
    words = [w("Berlin"), w("Berlin", y0=20, line=1)]
    assert match_words(words, "Berlin") == (0, 0, 50, 12)


def test_match_words_no_match_returns_none():
    assert match_words([w("Berlin")], "Stuttgart") is None


def test_match_words_skips_low_confidence_windows():
    words = [w("192.50", conf=40)]
    assert match_words(words, "192.5") is None


# --- Task 3: document resolution + PDF leg ---------------------------------

import os

import fitz
import pytest
from PIL import Image

from app.services.locator import locate_fields, resolve_document
from app.services.pipeline import FormFillingPipeline


def _pipeline():
    p = FormFillingPipeline.__new__(FormFillingPipeline)
    p.client_name = "uni-hamburg"
    p.config = {}
    return p


def _field(value, source_document):
    return {
        "field_name": "f",
        "value": value,
        "source_document": source_document,
        "bounding_box": None,
        "confidence": 0.9,
        "reasoning": None,
    }


def _setup_docs(tmp_path, texts_by_name):
    paths = []
    for name, pages in texts_by_name.items():
        p = tmp_path / name
        doc = fitz.open()
        for text in pages:
            page = doc.new_page()
            page.insert_text((72, 72 + 20 * pages.index(text)), text)
        doc.save(p)
        doc.close()
        paths.append(str(p))
    pages_dir = tmp_path / "pages"
    _, _, documents = _pipeline()._prepare_documents(paths, str(pages_dir))
    return paths, documents, str(pages_dir)


def test_resolve_document_case_insensitive():
    assert resolve_document("Hotel.PDF", ["hotel.pdf"]) == "hotel.pdf"
    assert resolve_document("nope.pdf", ["hotel.pdf"]) is None


def test_locates_value_with_pixel_box(tmp_path):
    paths, documents, pages_dir = _setup_docs(tmp_path, {"hotel.pdf": ["Hotel Metropol Berlin"]})
    field = _field("Hotel Metropol Berlin", "hotel.pdf")

    locate_fields(paths, documents, pages_dir, [field])

    box = field["bounding_box"]
    assert box is not None and box["page"] == 0
    page_file = FormFillingPipeline._page_path(pages_dir, 0, 0)
    with Image.open(page_file) as img:
        scale = img.width / 595  # fitz default A4 width in points
    assert box["x"] == pytest.approx(72 * scale, abs=2)
    assert box["width"] > 0


def test_locates_value_on_second_page(tmp_path):
    paths, documents, pages_dir = _setup_docs(
        tmp_path, {"hotel.pdf": ["nothing here", "Hotel Metropol Berlin"]}
    )
    field = _field("Hotel Metropol Berlin", "hotel.pdf")

    locate_fields(paths, documents, pages_dir, [field])

    assert field["bounding_box"]["page"] == 1


def test_first_duplicate_wins(tmp_path):
    paths, documents, pages_dir = _setup_docs(
        tmp_path, {"hotel.pdf": ["Hotel Metropol Berlin", "Hotel Metropol Berlin"]}
    )
    field = _field("Hotel Metropol Berlin", "hotel.pdf")

    locate_fields(paths, documents, pages_dir, [field])

    assert field["bounding_box"]["page"] == 0


def test_unresolved_source_uses_unique_global_match(tmp_path):
    paths, documents, pages_dir = _setup_docs(
        tmp_path,
        {"flight.pdf": ["EuroWings Express"], "hotel.pdf": ["Hotel Metropol Berlin"]},
    )
    field = _field("Hotel Metropol Berlin", "unknown")

    locate_fields(paths, documents, pages_dir, [field])

    assert field["bounding_box"] is not None
    assert field["source_document"] == "hotel.pdf"


def test_ambiguous_global_match_gives_no_box(tmp_path):
    paths, documents, pages_dir = _setup_docs(
        tmp_path,
        {"flight.pdf": ["Dr. Maximilian Hofmann"], "hotel.pdf": ["Dr. Maximilian Hofmann"]},
    )
    field = _field("Dr. Maximilian Hofmann", "unknown")

    locate_fields(paths, documents, pages_dir, [field])

    assert field["bounding_box"] is None
    assert field["source_document"] == "unknown"


def test_empty_value_is_skipped(tmp_path):
    paths, documents, pages_dir = _setup_docs(tmp_path, {"hotel.pdf": ["Hotel Metropol Berlin"]})
    field = _field("", "hotel.pdf")

    locate_fields(paths, documents, pages_dir, [field])

    assert field["bounding_box"] is None
