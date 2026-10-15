"""Filename and slug helpers shared by the form routes."""

import os
import re
import unicodedata

_SLUG_SEPARATORS = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn an institution name into a lowercase, hyphen-separated id.

    Diacritics are folded to their base letter, so "Universität Köln" becomes
    "universitat-koln". U-umlauts fold to "u", not "ue", matching the slug
    form the design fixes for institution names.
    """
    normalized = unicodedata.normalize("NFKD", name.replace("ß", "ss"))
    without_marks = "".join(c for c in normalized if not unicodedata.combining(c))
    return _SLUG_SEPARATORS.sub("-", without_marks.lower()).strip("-")


def safe_filename(name: str) -> str:
    """Reduce an uploaded filename to a safe basename.

    Path separators, directories, and leading dots are removed so a caller
    cannot escape the directory the file is written to.
    """
    base = re.split(r"[\\/]", name or "")[-1]
    base = base.lstrip(". ")
    return base or "receipt"


def unique_filename(name: str, taken: set[str]) -> str:
    """Return ``name``, suffixed with ``_1``, ``_2``... if already taken."""
    if name not in taken:
        return name

    stem, ext = os.path.splitext(name)
    counter = 1
    while f"{stem}_{counter}{ext}" in taken:
        counter += 1
    return f"{stem}_{counter}{ext}"
