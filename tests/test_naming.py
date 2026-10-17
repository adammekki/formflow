from app.services.naming import safe_filename, slugify, unique_filename


def test_slugify_transliterates_umlauts():
    assert slugify("Universität Köln") == "universitat-koln"
    assert slugify("  Uni   Hamburg!! ") == "uni-hamburg"


def test_safe_filename_strips_paths_and_dots():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("/abs/Rechnung März.pdf") == "Rechnung März.pdf"
    assert safe_filename(".hidden") == "hidden"
    assert safe_filename("") == "receipt"


def test_unique_filename_suffixes_collisions():
    assert unique_filename("a.pdf", {"a.pdf"}) == "a_1.pdf"
    assert unique_filename("a.pdf", set()) == "a.pdf"
