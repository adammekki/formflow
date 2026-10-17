# Bounding-Box Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each extracted value highlighted at its exact location in the source document on the review screen, using deterministic locate-after-extract (no LLM for coordinates).

**Architecture:** A new `locator` service matches extracted values to word coordinates in the saved receipts (PyMuPDF text layer for native PDFs, Tesseract OCR for scans/images/garbage text layers). The pipeline saves full-size page renders per session; the router serves them and runs the locator before responding. The React review step gets a second pane with the page image and a scaled overlay div for the focused field's box.

**Tech Stack:** FastAPI, PyMuPDF (already a dep), pdf2image/Pillow (already used), pytesseract (new), React 19 + TS + Tailwind, vitest + testing-library.

**Spec:** `docs/superpowers/specs/2026-10-17-bounding-box-verification-design.md`

## Global Constraints

- Backend runs on Python 3.11 in Docker (`.venv` locally is 3.14 — write 3.11-compatible code).
- Anti-goal: never show a box that does not contain the value. No match → `bounding_box` stays null. No edit-distance fuzzy matching anywhere.
- OCR word confidence threshold: `MIN_OCR_CONF = 60`. Garbage-text-layer detection threshold: printable ratio `< 0.85`.
- Pixel space for all boxes = the full-size page JPEGs saved in the session's `pages/` dir, named `doc{doc_index:02d}_p{page:03d}.jpg` (0-based page).
- `bounding_box` wire shape (schema already exists in `app/routers/extraction.py`): `{"page": int, "x": float, "y": float, "width": float, "height": float}`, 0-based page index within the document.
- Backend test command: `.venv/bin/python -m pytest <file> -v` (run from repo root; `pytest.ini` sets `pythonpath`).
- Frontend test command: `npx vitest run <file>` (run from `frontend/`).
- Commit after each task with a conventional-commit message. (Git mutations only with the user's prior confirmation.)

## Review Focus

Inputs the spec implies that must not silently break:

1. `"14.03.2025"` must never parse as a number (two separators) — Task 1 pins `parse_number("14.03.2025") is None`.
2. German amounts `1.234,56` and `192,50` must equal `1234.56` / `192.5` — Task 1 pins both.
3. A value on page 2+ of a multi-page PDF must get `page: 1` etc., not page 0 — Task 3 test.
4. A value appearing twice in one document → the first occurrence in reading order wins — Task 3 test.
5. Phone photos with EXIF rotation must be served and OCR'd upright (`ImageOps.exif_transpose`) — Task 2 test.
6. OCR that misreads a number must produce no box, not a wrong box (confidence gate) — Task 4 test.

---

### Task 1: Locator matching core

**Files:**
- Create: `app/services/locator.py`
- Test: `tests/test_locator.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `MIN_OCR_CONF: float = 60`
  - `@dataclass class Word: x0: float; y0: float; x1: float; y1: float; text: str; line: int; conf: float = 100.0`
  - `normalize(s: str) -> str` — NFKD, strip combining marks, lowercase, collapse whitespace.
  - `parse_number(s: str) -> float | None`
  - `parse_date(s: str) -> str | None` — returns ISO `YYYY-MM-DD`.
  - `match_words(words: list[Word], value: str) -> tuple[float, float, float, float] | None` — returns the union rect `(x0, y0, x1, y1)` of the matched window, in the words' own coordinate space.

Matching rules for `match_words` (pinned by tests below): sort words by `(line, x0)`; slide windows of 1–8 words within the same line; skip any window containing a word with `conf < MIN_OCR_CONF`. Tiers in order, first window in reading order wins within a tier: (1) `normalize(window) == normalize(value)`; (2) needle contained in window, needle length ≥ 4 after normalize; (3) `parse_date(value)` and window parse to equal dates; (4) `parse_number` equality.

`parse_number` rules: find token `[-+]?\d[\d.,]*`; both separators → rightmost is decimal, other is thousands; one separator repeated → thousands; one separator once with exactly 3 trailing digits → thousands; otherwise decimal. Return None if `parse_date(s)` matches or no token found.

`parse_date` formats (day-first; 2-digit year → 2000s): ISO `2025-03-14`; `14.03.2025`; `14.3.2025`; `14/03/25`; `14. März 2025`; also German and English month names.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_locator.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_locator.py -v`
Expected: FAIL, `ModuleNotFoundError: app.services.locator`

- [ ] **Step 3: Implement `app/services/locator.py`**

Implement the interfaces above. Month map: `januar..dezember` + `january..december` (short forms `märz`→3 etc., case-folded, also accept umlaut-folded `marz`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_locator.py -v`
Expected: 17 PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/locator.py tests/test_locator.py
git commit -m "feat(locator): value-to-word matching with German number/date parsing"
```

---

### Task 2: Pipeline saves full-size page images

**Files:**
- Modify: `app/services/pipeline.py` (`extract` method, lines 142–214)
- Test: `tests/test_prepare_documents.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `FormFillingPipeline._prepare_documents(receipt_paths: list[str], pages_dir: str | None = None) -> tuple[list[bytes], str, list[dict]]` — returns `(all_images, doc_listing_str, documents)`. `documents` entries: `{"name": <basename>, "page_count": int}`. When `pages_dir` is set, creates it and writes every full-size page as `doc{di:02d}_p{pi:03d}.jpg` (0-based `di`, `pi`; JPEG quality 85).
  - `extract(self, receipt_paths: list[str], pages_dir: str | None = None) -> dict` — now returns `{"fields": [...], "documents": [...]}`. Existing callers reading only `["fields"]` are unaffected.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prepare_documents.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_prepare_documents.py -v`
Expected: FAIL, `AttributeError: ... no attribute '_prepare_documents'`

- [ ] **Step 3: Refactor `extract` in `app/services/pipeline.py`**

Move the document loop (current lines 163–190) into `_prepare_documents`. Keep the model-bound images resized via `_resize_image` exactly as today. New behavior only: full-size saves + manifest + `ImageOps.exif_transpose` on uploaded images. `extract` calls it and threads `documents` into the return dict.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_prepare_documents.py tests/test_extraction_fields.py -v`
Expected: PASS (existing parse tests keep passing)

- [ ] **Step 5: Commit**

```bash
git add app/services/pipeline.py tests/test_prepare_documents.py
git commit -m "feat(pipeline): save full-size page renders and a documents manifest"
```

---

### Task 3: Document resolution and PDF leg

**Files:**
- Modify: `app/services/locator.py`
- Test: `tests/test_locator.py` (append)

**Interfaces:**
- Consumes: Task 1 `Word`/`match_words`; Task 2 page-file naming and manifest shape.
- Produces:
  - `GARBAGE_RATIO = 0.85`
  - `resolve_document(source_document: str, known_names: list[str]) -> str | None` — exact, then case/whitespace-normalized match.
  - `locate_fields(receipt_paths: list[str], documents: list[dict], pages_dir: str, fields: list[dict]) -> None` — mutates each field: sets `bounding_box` (dict, pixel space of the saved page JPEG, 0-based `page`) and rewrites `source_document` to the matched filename. Skips fields with empty `value`.
  - Leg selection (PDF): per page, `page.get_text()` printable ratio `< GARBAGE_RATIO` → OCR fallback hook `_ocr_page_words(image_path) -> list[Word]` (Task 4 provides it; for now a stub raising `NotImplementedError`, unreachable in these tests).

Coordinate conversion: `scale = saved_image_width / pdf_page.rect.width` (get saved size via PIL on the page JPEG); box = `(x0*s, y0*s, (x1-x0)*s, (y1-y0)*s)` rounded to 1 decimal.

Resolution flow per field: resolved doc → search its pages in order, first match wins. Unresolved → search every document; accept only if exactly one document contains a match (uniqueness rule), then rewrite `source_document` to that document's name.

- [ ] **Step 1: Write the failing tests**

Build fixture PDFs with fitz (`insert_text((x, y), text)`), run `_prepare_documents` for the pages dir, then call `locate_fields` and assert on the mutated fields:

```python
def _setup_docs(tmp_path, texts_by_name):
    paths = []
    for name, pages in texts_by_name.items():
        p = tmp_path / name
        doc = fitz.open()
        for text in pages:
            page = doc.new_page()
            page.insert_text((72, 72 + 20 * pages.index(text)), text)
        doc.save(p); doc.close()
        paths.append(str(p))
    pages_dir = tmp_path / "pages"
    _, _, documents = _pipeline()._prepare_documents(paths, str(pages_dir))
    return paths, documents, str(pages_dir)
```

Tests:
- `test_locates_value_with_pixel_box` — field `{"value": "Hotel Metropol Berlin", "source_document": "hotel.pdf", ...}`; assert `bounding_box["page"] == 0`, `x ≈ 72 * scale` (compute scale from saved image width / 595pt page), and `width > 0`.
- `test_locates_value_on_second_page` — value on page index 1 → `bounding_box["page"] == 1`.
- `test_first_duplicate_wins` — same value on both pages → `page == 0`.
- `test_unresolved_source_uses_unique_global_match` — `source_document="unknown"`, value exists only in `hotel.pdf` → box set and `field["source_document"] == "hotel.pdf"`.
- `test_ambiguous_global_match_gives_no_box` — value in both docs, unresolved source → `bounding_box is None`, `source_document` unchanged.
- `test_empty_value_is_skipped` — `value: ""` → `bounding_box is None`.
- `test_resolve_document_case_insensitive` — `resolve_document("Hotel.PDF", ["hotel.pdf"]) == "hotel.pdf"`; `"nope.pdf"` → None.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_locator.py -v`
Expected: FAIL on the 7 new tests (resolve/locate missing)

- [ ] **Step 3: Implement resolution + PDF leg in `app/services/locator.py`**

Per interfaces above. PyMuPDF word tuples `(x0, y0, x1, y1, text, block, line, word_no)` map to `Word(..., line=(block << 16) | line, conf=100.0)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_locator.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/locator.py tests/test_locator.py
git commit -m "feat(locator): PDF text-layer leg with document resolution and uniqueness fallback"
```

---

### Task 4: OCR leg + Tesseract dependency

**Files:**
- Modify: `app/services/locator.py` (replace the `_ocr_page_words` stub; leg selection for image documents)
- Modify: `requirements.txt`, `Dockerfile`, `README.md`
- Test: `tests/test_locator.py` (append)

**Interfaces:**
- Consumes: Task 1 (`Word`, `match_words`), Task 3 (`locate_fields` structure).
- Produces:
  - `_ocr_page_words(image_path: str) -> list[Word]` — `pytesseract.image_to_data`, `lang="eng+deu"`; maps TSV rows to `Word` with `conf=float(row["conf"])`, `line=(block_num << 16) | line_num`, pixel coordinates (already in saved-image space).

Behavior: image documents go straight to the OCR leg on their saved page JPEG. PDF pages whose text layer is garbage (ratio `< GARBAGE_RATIO`) OCR the saved page JPEG. `match_words` already enforces `MIN_OCR_CONF`, so misread tokens cannot match.

- [ ] **Step 1: Write the failing tests**

```python
import shutil, pytest

tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")

@tesseract
def test_ocr_leg_locates_value_on_garbage_text_layer(tmp_path):
    # PDF whose only content is a rendered image of text (no text layer):
    # render a fitz text page to a pixmap, embed it into a new PDF as an image.
    ...
    locate_fields(paths, documents, pages_dir, [field("Parkhaus City", "scan.pdf")])
    assert field["bounding_box"] is not None

@tesseract
def test_ocr_leg_gives_no_box_for_absent_value(tmp_path):
    ...
    assert field["bounding_box"] is None
```

- [ ] **Step 2: Add dependencies**

`requirements.txt`: `pytesseract>=0.3.10`. `Dockerfile` base stage apt list: add `tesseract-ocr` and `tesseract-ocr-deu`. `README.md` local-dev section: add `brew install tesseract` (bundles German data).

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_locator.py -k ocr -v`
Expected: FAIL (stub `NotImplementedError`) — or SKIP if tesseract missing locally; verify the failure inside Docker/CI if so.

- [ ] **Step 4: Implement `_ocr_page_words` and image-leg routing**

Per interfaces. Route in `locate_fields`: non-PDF path → OCR leg directly on `pages_dir/doc{di:02d}_p{pi:03d}.jpg`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_locator.py -v`
Expected: all PASS (or OCR tests SKIP with reason printed)

- [ ] **Step 6: Commit**

```bash
git add app/services/locator.py requirements.txt Dockerfile README.md tests/test_locator.py
git commit -m "feat(locator): OCR leg via Tesseract for scans and garbage text layers"
```

---

### Task 5: Router wiring, page endpoint, feedback carry

**Files:**
- Modify: `app/routers/extraction.py` (`/process` handler, session dict, `/session/{id}` handler; new page endpoint)
- Modify: `app/services/pipeline.py` (`store_feedback`, both `corrections.append` branches)
- Test: `tests/test_pages_endpoint.py`, `tests/test_feedback.py`

**Interfaces:**
- Consumes: Task 2 (`extract(..., pages_dir=...)`, `documents`), Task 3 (`locate_fields`).
- Produces:
  - `GET /api/extract/session/{session_id}` response gains `documents: [{"name": str, "page_count": int}]`.
  - `GET /api/extract/session/{session_id}/pages/{doc_index}/{page}.jpg` → JPEG FileResponse from `{temp_dir}/pages/doc{doc_index:02d}_p{page:03d}.jpg`; 404 when session or file missing.
  - Session dict gains `"documents"` and `"pages_dir"`.
  - Feedback correction entries carry `"bounding_box": field.get("bounding_box")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pages_endpoint.py — TestClient(app); inject a fake session:
from app.routers.extraction import verification_sessions
# create tmp pages dir with doc00_p000.jpg (tiny PIL image), register session s1
# GET /api/extract/session/s1/pages/0/0.jpg -> 200, content-type image/jpeg
# GET /api/extract/session/s1/pages/0/9.jpg -> 404
# GET /api/extract/session/nope/pages/0/0.jpg -> 404
# cleanup: verification_sessions.pop("s1")

# tests/test_feedback.py — call store_feedback with a field carrying
# bounding_box; read the written JSON; assert both corrected and uncorrected
# entries contain the box.
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pages_endpoint.py tests/test_feedback.py -v`
Expected: FAIL (404 on route; missing key)

- [ ] **Step 3: Implement**

In `/process`: `pages_dir = os.path.join(temp_dir, "pages")`; pass to `pipeline.extract`; then `await run_in_threadpool(locate_fields, saved_receipts, extraction_result["documents"], pages_dir, extraction_result["fields"])` (`from starlette.concurrency import run_in_threadpool` — OCR can block for seconds). Store `documents` and `pages_dir` in the session. Add the page endpoint with int path params. Add `bounding_box` to both branches of `store_feedback`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -v`
Expected: full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/extraction.py app/services/pipeline.py tests/test_pages_endpoint.py tests/test_feedback.py
git commit -m "feat(api): locate boxes during /process, serve session page images, keep boxes in feedback"
```

---

### Task 6: Frontend API types and session fetch

**Files:**
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/api.test.ts`

**Interfaces:**
- Consumes: Task 5 endpoints.
- Produces:
  - `export type BoundingBox = { page: number; x: number; y: number; width: number; height: number }`
  - `ExtractedField` gains `bounding_box: BoundingBox | null`
  - `export type SessionDocument = { name: string; page_count: number }`
  - `export type SessionInfo = { session_id: string; client_name: string; field_count: number; documents: SessionDocument[] }`
  - `getSession(sessionId: string): Promise<SessionInfo>` — `GET /api/extract/session/{id}`
  - `pageImageUrl(sessionId: string, docIndex: number, page: number): string` — `apiUrl(`/api/extract/session/${sessionId}/pages/${docIndex}/${page}.jpg`)`

- [ ] **Step 1: Write the failing tests**

```ts
it("parses the session manifest", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    JSON.stringify({ session_id: "s1", client_name: "uni-ulm", field_count: 3,
      documents: [{ name: "hotel.pdf", page_count: 2 }] }), { status: 200 })));
  expect((await getSession("s1")).documents[0]).toEqual({ name: "hotel.pdf", page_count: 2 });
});

it("builds the page image URL", () => {
  expect(pageImageUrl("s1", 0, 1)).toBe("http://localhost:8000/api/extract/session/s1/pages/0/1.jpg");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/api.test.ts`
Expected: FAIL, `getSession is not defined`

- [ ] **Step 3: Implement the types and functions in `frontend/src/api.ts`**

Per interfaces; route through the existing `request<T>` helper.

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run src/api.test.ts && npm run build`
Expected: PASS; build may fail on `ExtractedField` fixtures missing `bounding_box` in test files — that is Task 8's step, so for now only confirm `src/api.ts` itself type-checks via `npx tsc --noEmit -p tsconfig.app.json` and note fixture fixes belong to Task 8.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/api.test.ts
git commit -m "feat(frontend): bounding box and session manifest types in the API client"
```

---

### Task 7: DocumentViewer component

**Files:**
- Create: `frontend/src/components/DocumentViewer.tsx`
- Test: `frontend/src/components/DocumentViewer.test.tsx`

**Interfaces:**
- Consumes: `BoundingBox` from `../api`.
- Produces:
  - `DocumentViewer({ imageUrl, box, documentName, page }: { imageUrl: string; box: BoundingBox | null; documentName: string; page: number })` — renders the page image (`w-full`) and, when `box` is set, an overlay div `data-testid="bbox-overlay"` positioned in **percentages** of the natural image size (`left: (box.x / naturalWidth) * 100}%` etc., read on the img's `onLoad`), styled `absolute border-2 border-accent bg-accent/20`. Image `alt`: `Page ${page + 1} of ${documentName}`.

Percentages (not pixels) so the overlay survives container resizes with no listeners.

- [ ] **Step 1: Write the failing test**

```tsx
it("positions the overlay in percentages of the natural image", async () => {
  render(<DocumentViewer imageUrl="/x.jpg" documentName="hotel.pdf" page={0}
    box={{ page: 0, x: 100, y: 50, width: 200, height: 25 }} />);
  const img = screen.getByAltText("Page 1 of hotel.pdf");
  Object.defineProperty(img, "naturalWidth", { value: 1000 });
  Object.defineProperty(img, "naturalHeight", { value: 500 });
  fireEvent.load(img);
  const overlay = screen.getByTestId("bbox-overlay");
  expect(overlay.style.left).toBe("10%");
  expect(overlay.style.top).toBe("10%");
  expect(overlay.style.width).toBe("20%");
  expect(overlay.style.height).toBe("5%");
});

it("renders no overlay without a box", () => {
  render(<DocumentViewer imageUrl="/x.jpg" documentName="hotel.pdf" page={0} box={null} />);
  expect(screen.queryByTestId("bbox-overlay")).toBeNull();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/components/DocumentViewer.test.tsx`
Expected: FAIL, module not found

- [ ] **Step 3: Implement `DocumentViewer.tsx`**

Per interfaces; keep natural dimensions in state from `onLoad`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/components/DocumentViewer.test.tsx`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DocumentViewer.tsx frontend/src/components/DocumentViewer.test.tsx
git commit -m "feat(frontend): document viewer with percentage-scaled bounding-box overlay"
```

---

### Task 8: ReviewStep two-pane integration

**Files:**
- Modify: `frontend/src/steps/ReviewStep.tsx`
- Modify: `frontend/src/components/FieldRow.tsx` (add optional `onSelect?: () => void`, called from the `<tr>`'s `onClick`)
- Modify: `frontend/src/App.tsx` (container width)
- Test: `frontend/src/steps/ReviewStep.test.tsx`

**Interfaces:**
- Consumes: Task 6 (`getSession`, `pageImageUrl`, `BoundingBox`), Task 7 (`DocumentViewer`).
- Produces: review screen = two panes on `lg` (stacked below): existing field table left; viewer right showing the focused field's document/page with its box. Default focus: null → viewer shows `documents[0]` page 0, no overlay. Doc resolution: `documents.findIndex(d => d.name === field.source_document)`; `-1` or null box → no overlay.

- [ ] **Step 1: Update existing tests to the new API surface**

In every `ExtractedField` fixture across test files, add `bounding_box: null`. In `ReviewStep.test.tsx`'s `vi.mock("../api", ...)` block, add `getSession: vi.fn()`; in a `beforeEach`, `vi.mocked(api.getSession).mockResolvedValue({ session_id: "s1", client_name: "c", field_count: 2, documents: [{ name: "Rechnung.pdf", page_count: 1 }] })`.

- [ ] **Step 2: Write the failing test**

```tsx
it("shows the focused field's page and box in the viewer", async () => {
  const boxed: api.ExtractedField[] = [{ ...FIELDS[0], bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 } }];
  render(<ReviewStep sessionId="s1" fields={boxed} onDone={vi.fn()} />);
  await userEvent.click(screen.getByLabelText("Name")); // focuses the row
  expect(await screen.findByAltText("Page 1 of Rechnung.pdf")).toBeTruthy();
  expect(screen.getByTestId("bbox-overlay")).toBeTruthy();
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `npx vitest run src/steps/ReviewStep.test.tsx`
Expected: FAIL, no `bbox-overlay`

- [ ] **Step 4: Implement**

`ReviewStep`: `useEffect` → `getSession(sessionId)` into state (on error, keep table-only view — no viewer, no crash); `focusedIndex` state; layout `grid gap-6 lg:grid-cols-2`; `FieldRow` gets `onSelect={() => setFocusedIndex(i)}`. Viewer props from the focused field via the resolution rule above, else document 0 page 0. `App.tsx`: container class becomes `w-full ${step === "review" ? "max-w-6xl" : "max-w-3xl"}`.

- [ ] **Step 5: Run full frontend suite**

Run: `npm test && npm run lint && npm run build`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/steps/ReviewStep.tsx frontend/src/components/FieldRow.tsx frontend/src/App.tsx frontend/src/steps/ReviewStep.test.tsx
git commit -m "feat(frontend): two-pane review screen linking fields to their source location"
```

---

## Self-Review Notes

- Spec coverage: two-pane UI ✓ (T8), PyMuPDF leg ✓ (T3), OCR leg ✓ (T4), garbage detection ✓ (T3/T4), German formats ✓ (T1), uniqueness fallback ✓ (T3), EXIF ✓ (T2), feedback carry ✓ (T5), page endpoint + manifest ✓ (T5), Docker/README ✓ (T4), `source_document` rewrite so the frontend can map fields to manifest entries ✓ (T3).
- Type consistency: `BoundingBox`/`bounding_box` names match the existing backend schema; `documents` manifest shape identical in T2/T5/T6; page-file naming identical in T2/T5/T6.
- Proportion: code blocks are tests and pinned values only; implementations are left to the builder.
