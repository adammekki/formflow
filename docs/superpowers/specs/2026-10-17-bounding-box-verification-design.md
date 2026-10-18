# Bounding-Box Verification — Design

Date: 2026-10-17
Status: Draft, pending builder check and partner approval

## Intent and why

The review step today shows extracted values as a table with a text-only
"Where from" column (`frontend/src/steps/ReviewStep.tsx`). Users verifying
a travel-expense form must trust or manually hunt through receipts. Showing
each value highlighted at its exact location in the source document makes
verification faster and builds trust in the extraction.

## Goals

- Every extracted field gets a bounding box: which document, which page,
  where on the page.
- The review step shows the source document next to the field table and
  highlights the box for the focused field.
- Works for native PDFs (booking confirmations, e-tickets) and for
  scans/photos of paper receipts.
- Locating is deterministic: no LLM involvement in producing coordinates.

## Non-goals

- Model-based grounding (asking ministral for coordinates) — dropped.
  Vision-model coordinates are unreliable and would add tokens/latency.
- Editing or drawing boxes in the UI.
- Multiple boxes per field (a value appearing several times) — v1 shows
  the first confident match only.
- Browser-side PDF rendering (PDF.js) — the backend serves rendered page
  images instead.

## Anti-goals

- **A box that does not contain the value.** A wrong box destroys trust in
  the feature; showing no box is always better than showing a wrong one.
  Any match the locator is not confident in is dropped, and the field
  falls back to today's text-only "Where from".

## Constraints

- Backend: FastAPI app in `app/`. PyMuPDF is already a dependency
  (`requirements.txt`: `pymupdf>=1.24.0`). Pillow and `pdf2image` are
  already used in `app/services/pipeline.py`.
- Frontend: React 19 + TypeScript + Vite + Tailwind in `frontend/`.
  The verification page is `frontend/src/steps/ReviewStep.tsx`.
- The API schema already carries boxes: `BoundingBox` model and
  `bounding_box` field on `ExtractedField` in
  `app/routers/extraction.py` (currently always null — nothing fills it).
  The frontend type `ExtractedField` in `frontend/src/api.ts` does not
  have it yet.
- Sessions: `/api/extract/process` already saves uploaded receipts to a
  per-session temp dir and stores the session in `verification_sessions`;
  `/api/extract/verify` wipes the temp dir when done. Page images live in
  the same temp dir and are cleaned up with it.

## Decisions made by the partner

- Approach: **locate-after-extract** (deterministic), not model-emitted
  boxes. Chosen after a spike on 4 real receipt PDFs showed PyMuPDF
  extracts clean text and exact rects from all of them
  (printable ratio 1.00; every in-document value found).
- Serving shape: **JSON + page images** (option A), with the React
  frontend drawing overlays — not server-side annotated images. Faster
  per request, cacheable, and interactions are free client-side.
- The UI is the existing ReviewStep in the React app, not a new page.

## Architecture

### Backend: new `app/services/locator.py`

Input: saved receipt paths + extracted fields (each with `field_name`,
`value`, `source_document`). Output: the same fields with `bounding_box`
filled where a confident match was found.

Two legs, tried in order:

1. **PyMuPDF leg** (native PDFs). For the document named by
   `source_document`, extract words per page
   (`page.get_text("words")`). Match the field value against the words:
   - normalized substring (unicode fold, case, whitespace) over
     consecutive words on the same line,
   - numeric-aware matching for amounts and dates, parse-and-compare,
     not string hackery. All four clients are German universities
     (EUR, en+de), so both separator conventions are in scope:
     `192.5`, `EUR 192.50`, `192,50`, `1.234,56` must all match the
     same numeric value. Decimal-vs-thousands disambiguation is part
     of the parser. Dates: model output may be ISO `2025-03-14` while
     the document prints `14.03.2025`, `14.3.2025`, `14/03/25`, or
     `14. März 2025` — these must round-trip.
   The match rectangle is the union of the matched words' rects, in PDF
   points, converted to page-image pixels (× render_scale, see below).
2. **OCR leg** (images, scans, and PDFs whose text layer is missing or
   garbage). Render page if needed, run Tesseract TSV output
   (word + coordinates + per-word confidence), apply the same matching
   with a strict rule: every matched word must meet a confidence
   threshold (start at 60, tune on samples), and matching uses only the
   normalization and numeric/date parse rules — **no edit-distance
   fuzzy matching**, because near-miss numbers are exactly how a box
   lands on the wrong value (anti-goal). Anything short of that is a
   null box, never a guess. Garbage detection for the leg switch:
   printable-character ratio of `page.get_text()` below a threshold.

Document resolution: `source_document` is model-echoed free text.
Match it against the known saved filenames (case/whitespace
insensitive). If it matches none, search **all** documents and accept
the box only when the value matches in exactly one document
(uniqueness rule); otherwise null box. This keeps the anti-goal while
surviving the model paraphrasing a filename.

`bounding_box.page` is the page index within that document (0-based).
The document is identified via the field's `source_document` resolved
as above, so the wire schema does not change.

### Backend: page images

`pipeline.extract` already renders every PDF page to a JPEG via
`pdf2image`/poppler (~200 DPI) for the vision model (resized to
1024px). At the same moment, save the full-size render of each page
into the session temp dir. The locator computes boxes in exactly this
image's pixel space (PDF points × 200/72), so there is one coordinate
system end to end and no resize mismatch. Uploaded images are served
and OCR'd as the same converted JPEG — one pixel space again — after
normalizing orientation with `ImageOps.exif_transpose`.

New endpoint: `GET /api/extract/session/{session_id}/pages/{doc_index}/{page}.jpg`
serves a rendered page from the session temp dir. The existing
`GET /api/extract/session/{session_id}` response gains a `documents`
manifest: for each uploaded document, its name, page count, and page
image URLs. Session cleanup on `/verify` deletes the images with the
temp dir; no new lifecycle code.

### Backend: wiring

`/api/extract/process` runs the locator after extraction, before storing
the session and responding. Cost: milliseconds for text-layer PDFs,
~0.5–2s per page when OCR is needed. Boxes are also stored in the
session's `extracted_data`; `store_feedback` is updated to carry
`bounding_box` into the feedback JSON (it currently rebuilds field
dicts and would drop it).

### Frontend

- `frontend/src/api.ts`: add `bounding_box` to `ExtractedField`
  (`{ page: number; x: number; y: number; width: number; height: number } | null`),
  a `DocumentPages` type for the manifest, and a `getSession(sessionId)`
  call.
- `ReviewStep.tsx`: two-pane layout on wide screens (stacked on narrow):
  field table on the left (unchanged component), new
  `DocumentViewer` component on the right.
- `DocumentViewer`: given the session manifest and the focused field,
  fetches and shows the relevant page image, and draws the box as an
  absolutely-positioned div scaled by displayed width / natural width.
  Focusing a field row (click or keyboard focus) jumps the viewer to that
  field's document and page and shows its box. Fields without a box leave
  the viewer showing the first page of the first document, no overlay.

## Builder's calls (made by the designer, marked as calls)

- Overlay = positioned div, not canvas: tens of boxes at most, no perf
  concern, simpler and accessible.
- Serve rendered JPEGs at a fixed DPI rather than streaming the PDF:
  all coordinate math stays server-side, one source of truth.
- Two locator legs only (PyMuPDF → OCR). A pdfplumber leg was considered
  and dropped: the spike showed PyMuPDF works on the partner's samples,
  and OCR covers the garbage-text-layer case by reading pixels.
- OCR adds a system dependency (Tesseract binary + `pytesseract`),
  with the German language pack: clients are en+de, so the Docker image
  gets `tesseract-ocr` + `tesseract-ocr-deu`; local dev documents
  `brew install tesseract` (bundles deu) or `tesseract-lang`.
- OCR confidence rule: threshold on Tesseract's per-word confidence,
  no edit-distance matching (see locator legs).
- `source_document` mismatch: filename normalization, then all-document
  search with a uniqueness rule (see locator legs).
- First-match-only per field in v1.
- Boxes feed back into the stored feedback JSON (free: `extracted_data`
  already persists, boxes ride along).

## Testing

- Backend unit tests for the locator matching logic: exact, reformatted
  amounts (`192.5` vs `EUR 192.50` vs `192,50` vs `1.234,56`), date
  variants (ISO vs `14.03.2025` vs `14. März 2025`), cross-page values,
  `source_document` paraphrase with unique vs ambiguous global match,
  no-match → null box. Fixture PDFs generated in-test with PyMuPDF
  (text insertion), mirroring how the existing test suite works
  (`tests/`). OCR leg tested with a rendered image of a generated PDF,
  including a below-threshold-confidence case → null box.
- Frontend: `ReviewStep.test.tsx` gains a case asserting the viewer shows
  the focused field's document and renders the overlay div at the scaled
  position; `api.test.ts` covers the new types/parsing.

## Open risks

- OCR accuracy on photos of paper (curl, blur, perspective) is unknown.
  Mitigation: no-confident-match → no box, never a wrong box.
- In-memory `verification_sessions` means page images vanish on server
  restart; acceptable, sessions are short-lived and this matches the
  existing design.
