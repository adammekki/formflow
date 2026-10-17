# FormFlow Backend API Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the FormFlow FastAPI backend so a traveller-facing frontend can onboard a new university form, upload receipts, choose which extracted fields to keep, and download a filled PDF.

**Architecture:** The existing FastAPI app keeps its shape. A new `app/services/pdf_form.py` replaces the broken `pdfrw`-based form read/write with `pymupdf`; a new `app/services/naming.py` centralises slug and filename safety. The router changes are additive or narrowly breaking — no rewrite of the inference or extraction logic.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pymupdf (already installed transitively, promoted to a direct dependency), pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-formflow-frontend-design.md`

## Global Constraints

- Python 3.11 (the Docker base image is `python:3.11-slim`); no new third-party dependency except promoting `pymupdf` to a direct requirement.
- `pymupdf` reads and fills all four bundled forms. `pdfrw`/`fillpdfs` must not be used for form read or write after Task 1.
- Keep the existing HTTP API shape unless a task says otherwise. Frontend-visible JSON keys are case-sensitive and fixed by this plan.
- Slug format: lowercase, `[a-z0-9-]`, one or more hyphen-separated segments, derived from the institution name (umlauts transliterated: ä→ae, ö→oe, ü→ue, ß→ss).
- Never overwrite an existing `configs/<slug>/` or `templates/<slug>/`.
- Do not change the inference client, the extraction prompts for receipts, or `app/evaluate.py`.

## Review Focus

Inputs and failure modes the spec implies but no task's happy path exercises. Each line gets a test in the task named in brackets.

1. A **non-fillable** PDF (a scan) is uploaded for discovery — the user must get a clear "no fillable fields" error, not a silent zero-field success. [Task 4]
2. **Non-ASCII** field values (umlauts, accents) must survive read → fill → read unchanged. [Task 1]
3. Two institution names that **slugify the same** (differing only by case, punctuation, or umlaut spelling) must be refused, not merged. [Task 5]
4. An upload **filename containing a path** (`../../etc/passwd`) or a leading dot must not escape or hide inside the temp directory. [Task 2]
5. `kept_fields` containing a name that was **never extracted** must be ignored without error, while the real fields still fill. [Task 3]

---

### Task 1: Form read/write via pymupdf

**Files:**
- Create: `pytest.ini`
- Create: `app/services/pdf_form.py`
- Create: `tests/test_pdf_form.py`
- Modify: `app/services/schema_discovery.py:16` (import), `:129` (call)
- Modify: `app/services/pipeline.py:17` (import), `:333` (call)
- Modify: `requirements.txt:9`

**Interfaces:**
- Produces:
  - `read_form_fields(pdf_path: str) -> dict[str, str]` — every named widget's `field_name` → current `field_value` (empty string when unset).
  - `fill_form_fields(template_path: str, output_path: str, values: dict[str, str]) -> None` — set each matching widget, regenerate its appearance, save to `output_path`.

- [ ] **Step 1: Add pytest configuration**

`pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 2: Write the failing test**

`tests/test_pdf_form.py` — use the real bundled templates; assert on a field name known to exist.

```python
import pytest
from app.services.pdf_form import read_form_fields, fill_form_fields

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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_pdf_form.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.pdf_form'`

- [ ] **Step 4: Implement `app/services/pdf_form.py`**

Open the PDF with `pymupdf.open`. For each page's `widgets()`, skip widgets whose `field_name` is `None`. To fill, set `widget.field_value = str(value)` then call `widget.update()` before `doc.save(output_path)`. `update()` is required so the value is visible in viewers, not just stored in the form dictionary.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_pdf_form.py -v`
Expected: PASS — 8 tests.

- [ ] **Step 6: Swap the two call sites**

In `app/services/schema_discovery.py`, replace `from fillpdf import fillpdfs` and the `fillpdfs.get_form_fields(str(temp_path))` call with `read_form_fields`. Keep the existing `clean_pdf_fields` / `decode_pdf_field_name` helpers (harmless; pymupdf already returns clean names).
In `app/services/pipeline.py`, replace `from fillpdf import fillpdfs` and the `fillpdfs.write_fillable_pdf(...)` call with `fill_form_fields`.
In `requirements.txt`, replace `fillpdf>=0.7.0` with `pymupdf>=1.24.0`.

- [ ] **Step 7: Verify nothing still imports fillpdf, run the full suite, and commit**

Run: `grep -rn "fillpdf" app/ || echo clean`
Run: `pytest -v`
Expected: no matches; all tests PASS.

```bash
git add pytest.ini app/services/pdf_form.py app/services/schema_discovery.py app/services/pipeline.py tests/test_pdf_form.py requirements.txt
git commit -m "feat: read and fill form fields with pymupdf"
```

---

### Task 2: Naming utilities and safe receipt filenames

**Files:**
- Create: `app/services/naming.py`
- Create: `tests/test_naming.py`
- Modify: `app/routers/extraction.py:97-107` (save logic)

**Interfaces:**
- Produces:
  - `slugify(name: str) -> str` — `"Universität Köln"` → `"universitat-koln"`.
  - `safe_filename(name: str) -> str` — basename only, no path separators, no leading dot, never empty.
  - `unique_filename(name: str, taken: set[str]) -> str` — `"a.pdf"` twice → `"a.pdf"`, `"a_1.pdf"`.
- Consumes: nothing.

- [ ] **Step 1: Write the failing test**

`tests/test_naming.py`:

```python
from app.services.naming import slugify, safe_filename, unique_filename

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_naming.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `app/services/naming.py`**

Transliterate umlauts before lowercasing (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`); for `slugify`, replace any run of non-`[a-z0-9]` with a single `-` and strip leading/trailing `-`. For `safe_filename`, take `os.path.basename`, strip leading dots and separators, and fall back to `"receipt"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_naming.py -v`
Expected: PASS.

- [ ] **Step 5: Preserve original names when saving uploads**

In `app/routers/extraction.py`, replace `f"receipt_{i}{ext}"` with the sanitized original name, uniquified against the names already saved this request, and keep the existing extension filter. The saved basename must equal what the traveller uploaded, because `pipeline.extract` derives `source_document` from `os.path.basename(path)`.

- [ ] **Step 6: Commit**

```bash
git add app/services/naming.py app/routers/extraction.py tests/test_naming.py
git commit -m "feat: slugify names and preserve original receipt filenames"
```

---

### Task 3: Fill only the kept fields

**Files:**
- Modify: `app/routers/extraction.py:55-58` (`VerifyRequest`), `:160-163` (call)
- Modify: `app/services/pipeline.py:287-338` (`fill_form`)
- Create: `tests/test_fill_form.py`

**Interfaces:**
- Consumes: `fill_form_fields`, `read_form_fields` (Task 1).
- Produces: `FormFillingPipeline.fill_form(extracted_data, verified_data, kept_fields: list[str] | None = None) -> dict` — when `kept_fields` is `None`, behaviour is unchanged (fill everything); otherwise fill exactly the named fields, taking `verified_data` values where present and extracted values otherwise. A `kept_fields` name that matches no extracted field is ignored.
- Produces: `VerifyRequest` gains `kept_fields: list[str] | None = None`.

- [ ] **Step 1: Write the failing test**

`tests/test_fill_form.py` — build a pipeline against `uni-hamburg` without touching inference.

```python
import pytest
from app.services.pipeline import FormFillingPipeline
from app.services.pdf_form import read_form_fields

EXTRACTED = [
    {"field_name": "Name", "value": "Original"},
    {"field_name": "Vorname", "value": "Keepme"},
]

@pytest.fixture
def pipeline(monkeypatch):
    p = FormFillingPipeline.__new__(FormFillingPipeline)   # skip __init__/config load
    p.client_name = "uni-hamburg"
    return p

@pytest.mark.asyncio
async def test_keeps_only_ticked_fields(pipeline, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    (tmp_path / "uni-hamburg").mkdir()
    (tmp_path / "uni-hamburg" / "form_template.pdf").write_bytes(
        open("templates/uni-hamburg/form_template.pdf", "rb").read())
    result = await pipeline.fill_form(EXTRACTED, {"Name": "Corrected"}, kept_fields=["Name"])
    fields = read_form_fields(result["path"])
    assert fields["Name"] == "Corrected"
    assert not fields["Vorname"]

@pytest.mark.asyncio
async def test_unknown_kept_field_is_ignored(pipeline, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    (tmp_path / "uni-hamburg").mkdir()
    (tmp_path / "uni-hamburg" / "form_template.pdf").write_bytes(
        open("templates/uni-hamburg/form_template.pdf", "rb").read())
    result = await pipeline.fill_form(EXTRACTED, {}, kept_fields=["Name", "Nonexistent"])
    assert read_form_fields(result["path"])["Name"] == "Original"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fill_form.py -v`
Expected: FAIL — `fill_form() got an unexpected keyword argument 'kept_fields'`.

- [ ] **Step 3: Implement the filter in `pipeline.fill_form`**

After merging extracted and verified values into `form_data`, apply the filter when `kept_fields is not None`: `form_data = {k: v for k, v in form_data.items() if k in set(kept_fields)}`. Do not change `store_feedback`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fill_form.py -v`
Expected: PASS.

- [ ] **Step 5: Pass the selection through the router**

Add `kept_fields` to `VerifyRequest` and forward it in the `pipeline.fill_form(...)` call in the `verify` endpoint.

- [ ] **Step 6: Commit**

```bash
git add app/routers/extraction.py app/services/pipeline.py tests/test_fill_form.py
git commit -m "feat: fill only the fields the user kept"
```

---

### Task 4: Discovery proposes an institution name without saving

**Files:**
- Modify: `app/services/schema_discovery.py:146-165` (prompt), `:109-203` (return value)
- Modify: `app/routers/forms.py:27-128` (`FormSchemaResponse`, `discover_form_schema`)
- Create: `tests/test_discover.py`

**Interfaces:**
- Consumes: `read_form_fields` (Task 1).
- Produces: `POST /api/forms/discover-schema` takes **only** `form_template` (no `client_name`) and returns
  `{"status":"success","proposal_id":str,"institution_name":str,"form_title":str,"form_language":str,"field_count":int,"fields":[{"name":str,"field_type":str,"description":str|None,"required":bool}],"raw_fields":dict}`,
  or `{"status":"error","error":str}`.
  It writes **nothing** to `configs/`; the uploaded template is staged at `templates/.staging/{proposal_id}/form_template.pdf`.
- Produces: `FormSchemaDiscoveryAgent.discover_schema` returns an extra `institution_name` key.

- [ ] **Step 1: Write the failing test**

`tests/test_discover.py` — stub the agent so no model is needed.

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_non_fillable_pdf_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    monkeypatch.setattr("app.config.settings.configs_dir", str(tmp_path / "configs"))
    import pymupdf
    doc = pymupdf.open(); doc.new_page(); blank = str(tmp_path / "blank.pdf"); doc.save(blank)
    with open(blank, "rb") as fh:
        r = client.post("/api/forms/discover-schema", files={"form_template": ("blank.pdf", fh, "application/pdf")})
    assert r.status_code == 200
    assert r.json()["status"] == "error"
    assert "field" in r.json()["error"].lower()

def test_staging_does_not_write_a_config(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.templates_dir", str(tmp_path))
    monkeypatch.setattr("app.config.settings.configs_dir", str(tmp_path / "configs"))
    monkeypatch.setattr("app.routers.forms.FormSchemaDiscoveryAgent.discover_schema", _fake_discover)
    with open("templates/uni-hamburg/form_template.pdf", "rb") as fh:
        r = client.post("/api/forms/discover-schema", files={"form_template": ("f.pdf", fh, "application/pdf")})
    body = r.json()
    assert body["institution_name"] == "Universität Hamburg"
    assert not (tmp_path / "configs").exists()
    assert (tmp_path / ".staging" / body["proposal_id"] / "form_template.pdf").exists()

async def _fake_discover(self, pdf_bytes, client_name=None):
    return {"institution_name": "Universität Hamburg", "form_title": "Reisekosten",
            "form_language": "German", "fields": [{"field_name": "Name", "data_type": "text",
            "description": "Surname", "required": True}], "pdf_fields_raw": {"Name": ""}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_discover.py -v`
Expected: FAIL — the route still requires `client_name`, and the response has no `proposal_id`.

- [ ] **Step 3: Add the institution name to the discovery prompt**

In `schema_discovery.py`, extend the requested JSON with `"institution_name"` ("the university or organisation the form belongs to, in its own language"). Default to `form_title` when the model omits it.

- [ ] **Step 4: Reject forms with no fillable fields**

After reading fields, if the result is empty, return `{"status": "error", "error": "This PDF has no fillable form fields..."}` before calling the model.

- [ ] **Step 5: Stage instead of saving**

In `forms.py`, drop the `client_name` query parameter, generate `proposal_id = str(uuid.uuid4())`, and write **both** the upload and the draft config to `templates/.staging/{proposal_id}/` (`form_template.pdf` and `config.yaml` with `client_name: pending`, the discovered `institution_name`, `form_title`, `form_language`, and `fields`). Return the proposal in the response model. Remove the config-writing block that targeted `configs/<client_name>/`.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_discover.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/schema_discovery.py app/routers/forms.py tests/test_discover.py
git commit -m "feat: propose an institution name and stage the upload"
```

---

### Task 5: Confirm the name and save the config

**Files:**
- Modify: `app/routers/forms.py` (new endpoint)
- Create: `tests/test_confirm.py`

**Interfaces:**
- Consumes: `slugify` (Task 2), the staged template (Task 4).
- Produces: `POST /api/forms/confirm-schema` with body `{"proposal_id": str, "institution_name": str}` →
  `{"status":"success","client_name":str,"institution_name":str}`.
  Errors: `422` when `institution_name` is blank; `404` for an unknown `proposal_id`; `409` when `configs/<slug>` already exists.

- [ ] **Step 1: Write the failing test**

`tests/test_confirm.py`:

```python
from fastapi.testclient import TestClient
from app.main import app
import app.config as config

client = TestClient(app)

def test_duplicate_slug_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "templates_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path / "configs"))
    staged = tmp_path / ".staging" / "p1"
    staged.mkdir(parents=True)
    (staged / "form_template.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "configs" / "universitat-koln").mkdir(parents=True)   # already on board

    r = client.post("/api/forms/confirm-schema", json={"proposal_id": "p1", "institution_name": "Universität Köln"})
    assert r.status_code == 409

def test_blank_name_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "templates_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path / "configs"))
    r = client.post("/api/forms/confirm-schema", json={"proposal_id": "p1", "institution_name": "   "})
    assert r.status_code == 422

def test_saves_config_and_template(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "templates_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path / "configs"))
    staged = tmp_path / ".staging" / "p1"; staged.mkdir(parents=True)
    (staged / "form_template.pdf").write_bytes(b"%PDF-1.4")
    (staged / "config.yaml").write_text("client_name: pending\nfields: []\n")   # written by Task 4

    r = client.post("/api/forms/confirm-schema", json={"proposal_id": "p1", "institution_name": "Universität Köln"})
    assert r.json()["client_name"] == "universitat-koln"
    assert (tmp_path / "configs" / "universitat-koln" / "config.yaml").exists()
    assert (tmp_path / "uni-koln" / "form_template.pdf").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_confirm.py -v`
Expected: FAIL — 404, route not found.

- [ ] **Step 3: Confirm the staged draft exists**

Task 4 writes `config.yaml` beside the staged `form_template.pdf`, so confirm only has to move both. If it does not, fix Task 4 before continuing.

- [ ] **Step 4: Implement the endpoint**

Slugify the name (422 if the slug is empty), refuse when `configs/<slug>` exists (409), move the staged directory's files into `templates/<slug>/` and `configs/<slug>/`, and stamp `client_name` + `institution_name` into the saved config.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_confirm.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/forms.py tests/test_confirm.py
git commit -m "feat: confirm institution name and save config"
```

---

### Task 6: Client list returns display names

**Files:**
- Modify: `app/routers/forms.py:130-146` (`list_clients`)
- Create: `tests/test_clients.py`

**Interfaces:**
- Produces: `GET /api/forms/clients` → `{"clients":[{"name":str,"institution_name":str,"configured":bool}]}`, where `institution_name` falls back to the directory name when the config lacks it.

- [ ] **Step 1: Write the failing test**

`tests/test_clients.py`:

```python
from fastapi.testclient import TestClient
from app.main import app
import app.config as config

client = TestClient(app)

def test_lists_institution_names(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path))
    d = tmp_path / "uni-hamburg"; d.mkdir()
    (d / "config.yaml").write_text("client_name: uni-hamburg\ninstitution_name: Universität Hamburg\nfields: []\n")
    assert client.get("/api/forms/clients").json()["clients"][0]["institution_name"] == "Universität Hamburg"

def test_falls_back_to_directory_name(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "configs_dir", str(tmp_path))
    d = tmp_path / "legacy"; d.mkdir()
    (d / "config.yaml").write_text("client_name: legacy\nfields: []\n")
    assert client.get("/api/forms/clients").json()["clients"][0]["institution_name"] == "legacy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_clients.py -v`
Expected: FAIL — `KeyError: 'institution_name'`.

- [ ] **Step 3: Implement the lookup**

Read each `config.yaml` (skip unreadable ones) and add `institution_name`. This replaces the frontend's need to call `GET /clients/{name}` per university.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_clients.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/forms.py tests/test_clients.py
git commit -m "feat: return institution display names in the client list"
```

---

### Task 7: Production configuration

**Files:**
- Modify: `Dockerfile:64` (worker count)
- Modify: `docker-compose.prod.yml:18-19` (writable mounts)
- Modify: `app/config.py:34` (CORS parsing)
- Create: `tests/test_settings.py`

**Interfaces:**
- Produces: `settings.cors_origins` parses a comma-separated `CORS_ORIGINS` env value.

- [ ] **Step 1: Write the failing test**

`tests/test_settings.py`:

```python
from app.config import Settings

def test_cors_origins_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a:3000,http://b:3000")
    assert Settings().cors_origins == ["http://a:3000", "http://b:3000"]

def test_cors_origins_parses_json_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://c:3000"]')
    assert Settings().cors_origins == ["http://c:3000"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings.py -v`
Expected: FAIL — pydantic tries to JSON-decode the comma-separated value and raises.

- [ ] **Step 3: Implement a field validator**

Add a `field_validator("cors_origins", mode="before")` that accepts a comma-separated string, a JSON list string, or a list. Keep the existing defaults.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Pin one worker and make the mounts writable**

Change the Dockerfile production `CMD` to `--workers 1` (the in-memory session store is per-process; verify would otherwise fail on the normal path). Drop `:ro` from the `configs` and `templates` mounts in `docker-compose.prod.yml` — config creation and PDF output both write there.

- [ ] **Step 6: Run the whole suite and commit**

Run: `pytest -v`
Expected: all PASS.

```bash
git add Dockerfile docker-compose.prod.yml app/config.py tests/test_settings.py
git commit -m "fix: single worker, writable mounts, parse CORS origins"
```
