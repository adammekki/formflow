"""Read and fill AcroForm fields using pymupdf.

Replaces the previous pdfrw-based path, which could not parse the compressed
object streams in some of the university forms.
"""

import pymupdf


def read_form_fields(pdf_path: str) -> dict[str, str]:
    """Return each named widget's field name mapped to its current value.

    Widgets without a field name are skipped. An unset value is returned as
    an empty string.
    """
    fields: dict[str, str] = {}
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            for widget in page.widgets():
                if not widget.field_name:
                    continue
                value = widget.field_value
                fields[widget.field_name] = "" if value is None else str(value)
    return fields


def fill_form_fields(
    template_path: str, output_path: str, values: dict[str, str]
) -> None:
    """Write ``values`` into matching widgets and save to ``output_path``.

    ``widget.update()`` regenerates the field's appearance stream so the value
    is visible in PDF viewers, not merely stored in the form dictionary.
    """
    with pymupdf.open(template_path) as doc:
        for page in doc:
            for widget in page.widgets():
                if widget.field_name in values:
                    widget.field_value = str(values[widget.field_name])
                    widget.update()
        doc.save(output_path)
