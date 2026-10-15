import pytest

from app.services.pdf_form import fill_form_fields, read_form_fields

TEMPLATES = {
    "uni-hamburg": "Name",
    "uni-heidelberg": "UHD",
    "uni-koln": "Personalnummer",
    "uni-ulm": "AntragstellerIn_Name_Vorname",
}


@pytest.mark.parametrize("uni,field", TEMPLATES.items())
def test_reads_fields_from_every_bundled_form(uni, field):
    fields = read_form_fields(f"templates/{uni}/form_template.pdf")
    assert len(fields) > 50
    assert field in fields


@pytest.mark.parametrize("uni,field", TEMPLATES.items())
def test_fill_roundtrips_non_ascii_value(uni, field, tmp_path):
    out = str(tmp_path / "filled.pdf")
    fill_form_fields(f"templates/{uni}/form_template.pdf", out, {field: "Müller, Jörg"})
    assert read_form_fields(out)[field] == "Müller, Jörg"
