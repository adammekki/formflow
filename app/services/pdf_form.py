"""Read and fill AcroForm fields using pymupdf.

Replaces the previous pdfrw-based path, which could not parse the compressed
object streams in some of the university forms.
"""

import os

import pymupdf


def template_field_rects(pdf_path: str) -> list[dict]:
    """Return each named widget's page and rectangle, in PDF points.

    The review screen draws these as the form lines that will be filled.
    Widgets without a field name are skipped, matching read_form_fields.
    """
    fields: list[dict] = []
    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc):
            for widget in page.widgets():
                if not widget.field_name:
                    continue
                rect = widget.rect
                fields.append({
                    "field_name": widget.field_name,
                    "page": page_number,
                    "x": rect.x0,
                    "y": rect.y0,
                    "width": rect.width,
                    "height": rect.height,
                })
    return fields


def render_template_preview(template_path: str, out_dir: str) -> dict:
    """Render the form template and return its preview manifest.

    Pages are saved as ``p{page:03d}.jpg``; widget rectangles are scaled from
    PDF points into those images' pixels, so the review screen can draw the
    target lines without any coordinate math of its own.
    """
    from pdf2image import convert_from_path

    os.makedirs(out_dir, exist_ok=True)
    images = convert_from_path(template_path)

    with pymupdf.open(template_path) as doc:
        widths = [page.rect.width for page in doc]

    pages = []
    scales = []
    for page_number, image in enumerate(images):
        image.save(os.path.join(out_dir, f"p{page_number:03d}.jpg"), format="JPEG", quality=85)
        scale = image.width / widths[page_number] if widths[page_number] else 1.0
        scales.append(scale)
        pages.append({"page": page_number, "width": image.width, "height": image.height})

    fields = []
    for field in template_field_rects(template_path):
        if field["page"] >= len(scales):
            continue
        scale = scales[field["page"]]
        fields.append({
            "field_name": field["field_name"],
            "page": field["page"],
            "x": round(field["x"] * scale, 1),
            "y": round(field["y"] * scale, 1),
            "width": round(field["width"] * scale, 1),
            "height": round(field["height"] * scale, 1),
        })

    return {"pages": pages, "fields": fields}


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
) -> list[str]:
    """Write ``values`` into matching widgets and save to ``output_path``.

    ``widget.update()`` regenerates the field's appearance stream so the value
    is visible in PDF viewers, not merely stored in the form dictionary.

    Returns the value keys that matched no widget, so a config whose field names
    no longer exist on the form is reported instead of silently dropped.
    """
    matched: set[str] = set()
    with pymupdf.open(template_path) as doc:
        for page in doc:
            for widget in page.widgets():
                if widget.field_name in values:
                    widget.field_value = str(values[widget.field_name])
                    widget.update()
                    matched.add(widget.field_name)
        doc.save(output_path)

    return [name for name in values if name not in matched]
