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


def test_fill_reports_values_with_no_field(tmp_path):
    """A stale field name must be reported, never dropped silently."""
    out = str(tmp_path / "filled.pdf")
    unmatched = fill_form_fields(
        "templates/uni-hamburg/form_template.pdf",
        out,
        {"Name": "A", "NotAFieldOnThisForm": "B"},
    )
    assert unmatched == ["NotAFieldOnThisForm"]
    assert read_form_fields(out)["Name"] == "A"


def test_bundled_configs_still_fill_their_own_fields(tmp_path):
    """Characterises the shipped configs: how many of each config's field names
    actually exist on its template. Regenerating them needs the vision model."""
    import yaml

    matched = {}
    for uni in TEMPLATES:
        config = yaml.safe_load(open(f"configs/{uni}/config.yaml"))
        names = [f["field_name"] for f in config.get("fields", [])]
        widgets = read_form_fields(f"templates/{uni}/form_template.pdf")
        matched[uni] = sum(1 for name in names if name in widgets)

    # uni-hamburg is healthy; the other three configs are stale and must be
    # regenerated. This assertion is the tripwire, and it fails loudly the day
    # someone regenerates them and forgets to raise the bar.
    assert matched["uni-hamburg"] >= 40
    assert matched["uni-heidelberg"] < 30 or matched["uni-heidelberg"] >= 90
