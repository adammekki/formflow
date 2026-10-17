"""
FormFlow - Bounding Box Locator

Deterministic value-to-coordinate matching, no LLM involved: given the
words of a document page (from the PDF text layer or OCR), find where an
extracted value appears and return its rectangle.
"""

import re
import unicodedata
from dataclasses import dataclass

# Tesseract per-word confidence floor: below this a misread token could put
# a box on the wrong value, so the match is refused instead.
MIN_OCR_CONF = 60


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    line: int
    conf: float = 100.0


def normalize(s: str) -> str:
    """Fold case, accents and whitespace so variants of the same text compare equal."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


_MONTHS = {
    "januar": 1, "january": 1, "jan": 1,
    "februar": 2, "february": 2, "feb": 2,
    "marz": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "oct": 10, "okt": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "december": 12, "dec": 12, "dez": 12,
}


def _iso(year: int, month: int, day: int) -> str | None:
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _year(y: int) -> int:
    return 2000 + y if y < 100 else y


def parse_date(s: str) -> str | None:
    """Parse a date to ISO YYYY-MM-DD. Day-first; German and English month names."""
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", s)
    if m:
        return _iso(_year(int(m[3])), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        return _iso(_year(int(m[3])), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{1,2})\.?\s+([A-Za-zäöüÄÖÜ]+)\.?\s+(\d{4})", s)
    if m:
        month = _MONTHS.get(normalize(m[2]))
        if month:
            return _iso(int(m[3]), month, int(m[1]))
    return None


_NUM_TOKEN = re.compile(r"[-+]?\d[\d.,]*")


def parse_number(s: str) -> float | None:
    """Parse an amount in either German or English separator conventions.

    Both separators -> rightmost is the decimal point. One separator,
    repeated -> thousands. One separator with exactly 3 trailing digits ->
    thousands; otherwise decimal. Dates are never numbers.
    """
    if parse_date(s):
        return None
    m = _NUM_TOKEN.search(s)
    if not m:
        return None
    token = m.group(0)
    dots = token.count(".")
    commas = token.count(",")
    if dots and commas:
        if token.rfind(".") > token.rfind(","):
            token = token.replace(",", "")
        else:
            token = token.replace(".", "").replace(",", ".")
    elif commas:
        if commas > 1:
            token = token.replace(",", "")
        else:
            head, _, tail = token.partition(",")
            token = head + tail if len(tail) == 3 else head + "." + tail
    elif dots:
        if dots > 1:
            token = token.replace(".", "")
        else:
            head, _, tail = token.partition(".")
            if len(tail) == 3:
                token = head + tail
    try:
        return float(token)
    except ValueError:
        return None


def _windows(ordered: list[Word]):
    """Yield 1-8 word windows within each line, in reading order."""
    by_line: dict[int, list[Word]] = {}
    for wd in ordered:
        by_line.setdefault(wd.line, []).append(wd)
    for line_words in by_line.values():
        for i in range(len(line_words)):
            for j in range(i + 1, min(i + 9, len(line_words) + 1)):
                yield line_words[i:j]


def _raw(win: list[Word]) -> str:
    return " ".join(w.text for w in win)


def _confident(win: list[Word]) -> bool:
    return all(w.conf >= MIN_OCR_CONF for w in win)


def _union(win: list[Word]) -> tuple[float, float, float, float]:
    return (
        min(w.x0 for w in win),
        min(w.y0 for w in win),
        max(w.x1 for w in win),
        max(w.y1 for w in win),
    )


def match_words(words: list[Word], value: str) -> tuple[float, float, float, float] | None:
    """Find `value` among `words`, return the union rect of the matched window.

    Tiers in order (first window in reading order wins within a tier):
    exact normalized equality; containment for needles of 4+ chars; equal
    parsed dates; equal parsed numbers. Windows containing a word below
    MIN_OCR_CONF are never matched.
    """
    if not value or not value.strip():
        return None
    ordered = sorted(words, key=lambda w: (w.line, w.x0))
    needle = normalize(value)

    for win in _windows(ordered):
        if _confident(win) and normalize(_raw(win)) == needle:
            return _union(win)

    if len(needle) >= 4:
        for win in _windows(ordered):
            if _confident(win) and needle in normalize(_raw(win)):
                return _union(win)

    date_value = parse_date(value)
    if date_value:
        for win in _windows(ordered):
            if _confident(win) and parse_date(_raw(win)) == date_value:
                return _union(win)

    num_value = parse_number(value)
    if num_value is not None:
        for win in _windows(ordered):
            win_num = parse_number(_raw(win)) if _confident(win) else None
            if win_num is not None and win_num == num_value:
                return _union(win)

    return None
