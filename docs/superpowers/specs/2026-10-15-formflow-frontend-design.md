# FormFlow Frontend — Design

**Date:** 2026-10-15
**Status:** Draft, awaiting approval
**Scope:** A desktop web frontend for the existing FormFlow backend, plus the small backend changes it depends on.

## Intent

FormFlow today is a FastAPI service with no user interface. Getting a travel-expense
form filled means calling the API by hand. This design adds a small frontend that a
traveller can actually use.

The driving moment: someone has just come back from a trip. They are tired, they
want this over with, and they are not going to read instructions. The backend does
the hard part already — it reads receipts with a vision model and fills the PDF. The
frontend's only job is to get them from "I have receipts" to "I have a filled form"
with as little thought as possible.

## Who it is for

The traveller submitting a reimbursement. Not an administrator, not a developer.
They may be non-technical or simply impatient. There is no separate operator UI in
this scope: onboarding a new university's form is part of the same flow.

## Goals

- Four short steps, each a single screen, in plain language.
- The traveller only has to make decisions that genuinely need them.
- Any mistake is correctable on screen before anything is finalised.
- The frontend is a separate service from the FastAPI backend, talking to it over HTTP.

## Non-goals

- Mobile / responsive-first design. Desktop is the target.
- Authentication, accounts, or per-user history.
- An administration area for editing configs by hand.
- Changing the vision model, the extraction logic, or the schema-discovery prompts.

## Anti-goals

Things that would mean this failed even if it technically works:

- A traveller abandons the flow because it asks them to understand a concept
  ("config", "client", "schema", "session").
- The frontend exposes a field, error, or file path that only a developer would
  find meaningful.
- The service split is fake: the frontend reaches into the backend's filesystem,
  imports its code, or shares a process with it.

## Constraints

- The backend is Python 3.11 / FastAPI; do not rewrite it.
- In production, `configs/` and `templates/` are mounted read-only (see
  `docker-compose.prod.yml`). The flow writes to both.
- Production runs `uvicorn --workers 4`. Extraction sessions are stored in a
  per-process in-memory dict (`app/routers/extraction.py`).
- The four bundled universities are fillable AcroForms, but the installed
  `fillpdfs` version fails to parse two of them (see Open Questions).
- Inference can take minutes; a single extraction request may run up to the
  configured 10-minute timeout.

## Decisions made by the user

1. **Desktop target**, not mobile.
2. **Config creation is part of the main flow** — no hidden admin page.
3. **Start step branches**: pick an existing university, or upload a blank form.
4. **The agent chooses the institution's name**; the user confirms or corrects it.
5. **Full config, always.** No trimming fields at config time — a later user might
   need what an earlier one removed.
6. **Field selection happens after extraction.** The user reviews everything that
   was extracted and ticks what they want to keep.
7. **Frontend stays separate from the backend** (service boundary).
8. Keep it simple; it should look good without becoming elaborate.

## Decisions left to the builder (my calls, vetoable)

- **Stack:** React + Vite + TypeScript, Tailwind for styling. Containerised, served
  separately, calling the backend over HTTP.
- **No state library, no router bloat.** A single page with four steps is enough;
  a small state machine over a handful of components beats a framework.
- **Naming:** the agent must propose an **institution name** (e.g.
  "Universität Hamburg"), which is what the user sees and edits. `form_title` alone
  (e.g. "Reisekostenabrechnung") would make the dropdown unusable, since every
  university's form is titled similarly. The institution name is slugified into the
  `client_name` used in URLs and paths; editing the name before saving is what fixes
  the slug.
- **Source document label:** show the caller's **original filename**, not the
  backend's internal `receipt_0.pdf`. Requires preserving the original name through
  extraction (see backend change 6).
- **"Something wrong?"** is static reassurance text only. The backend already stores
  corrections as feedback; no free-text channel is added.
- **API base URL** is an environment setting. The browser calls the backend directly;
  the deployed origin is added to CORS at deploy time.
- **Errors:** every backend failure surfaces as a plain, retryable message on the
  current screen — never a raw stack trace or status code.

## The flow

### Step 1 — Start

One question on screen: *which university is this for?*

- A dropdown lists universities that already have a config. Choosing one goes
  straight to step 2.
- A secondary action — "My university isn't listed" — reveals a file input for the
  blank expense report.
- On upload, the agent analyses the form (schema discovery). It returns a proposed
  name and title. The user sees the proposed institution name in an editable text
  field and confirms it. Saving happens on confirm.
- After confirm, the user lands on step 2. There is no field-by-field review here;
  review happens in step 3.

### Step 2 — Upload receipts

A drop zone accepting multiple PDFs and images. A short line explains that multiple
receipts are fine and are read together (the backend already cross-references them).
Uploading starts extraction and moves to step 3.

### Step 3 — Review and choose

Everything the model extracted, as a list. For each field:

- the human-readable name (prefer `semantic_name`, fall back to `field_name`),
- the extracted value in an editable input,
- a confidence indicator,
- which document it came from.

Fields with low confidence or no value are visually prioritised so the traveller
looks at the risky ones first. Every row has a checkbox; only ticked fields end up in
the PDF. Sensible default: tick the confident ones, leave obvious junk unticked.

### Step 4 — Done

The filled PDF is generated from the ticked fields and offered as a download. A
discreet "something wrong?" note lets the user flag problems; the backend already
captures corrections as feedback.

## Backend interface

### Used as-is

| Call | Purpose |
|------|---------|
| `GET /api/forms/clients` | List configured universities |
| `GET /api/forms/clients/{name}` | Read one config (used for its `form_title`) |
| `POST /api/forms/discover-schema` | Analyse an uploaded blank form |
| `POST /api/extract/process` | Upload receipts, run extraction, get a `session_id` |
| `POST /api/extract/verify` | Submit kept/corrected values, get a download URL |
| `GET /api/extract/download/{client}/{file}` | Fetch the filled PDF |
| `GET /api/extract/session/{id}` | Session status (if needed) |

### Required backend changes

These are small and must be done for the flow above to work. Each stays behind the
existing HTTP contract.

1. **Confirm the name before saving.** `discover-schema` currently requires
   `client_name` up front and writes the config immediately. The flow needs: analyse
   → return the agent's proposed name → let the user edit → *then* save under the
   confirmed name. Either return a proposal before writing, or add a rename step.

2. **Fill only the ticked fields.** `verify` merges *all* extracted fields into the
   PDF and only overrides with `verified_fields`. The user's ticks must be able to
   *exclude* a field, not just override its value. Prefer an explicit list of kept
   fields over a convention.

3. **Human-facing names in the client list.** `GET /api/forms/clients` returns
   directory slugs only. The dropdown needs the display title, which currently
   costs one `GET /clients/{name}` per university.

4. **Writable mounts in production.** Creating a config writes `configs/<slug>/` and
   `templates/<slug>/form_template.pdf`; filling writes
   `templates/<slug>/output/`. The prod compose mounts both read-only.

5. **Return an institution name from discovery.** The schema-discovery response
   carries `form_title` and `form_language` only. Add an institution name so step 1
   has something human to show and to slugify. Store it in the config.

6. **Preserve original upload filenames.** `extract` renames uploads to
   `receipt_{i}{ext}` before analysis, so `source_document` comes back as
   `receipt_0.pdf`. Step 3 must show the name the traveller recognises.

7. **Replace `pdfrw` with `pymupdf` for form field read/write.** Two call sites:
   `fillpdfs.get_form_fields` in `app/services/schema_discovery.py` and
   `fillpdfs.write_fillable_pdf` in `app/services/pipeline.py`. Fixes
   `uni-heidelberg` and `uni-koln`. Confirmed.

8. **Refuse a duplicate institution name.** On slug collision, reject and ask the user
   for a different name rather than overwriting an existing config or template.

## Deployment

- New service `frontend` in `docker-compose.yml` and `docker-compose.prod.yml`,
  built from its own Dockerfile, on its own port.
- It reaches the backend by service name over the existing `formflow-network`.
- Production `app` runs `--workers 1` instead of 4, so the in-memory session store
  stays correct.
- `configs/` and `templates/` must be writable on the app service (they are
  read-only in `docker-compose.prod.yml` today).
- Backend CORS already allows `http://localhost:3000`; the deployed origin is added
  at deploy time. The API base URL is an environment setting.

## Open questions

- **`fillpdfs`/`pdfrw` cannot parse two of the four bundled forms.** Root cause found
  and documented under "Decisions resolved after review": pdfrw fails on the
  compressed object streams in `uni-heidelberg` and `uni-koln`; `pymupdf` handles all
  four. Not a Python or library-version issue.
- **In-memory sessions.** Resolved by pinning production to one worker.
- **Long-running extraction.** One request can run for minutes. Whether a plain
  loading state is enough, or progress feedback is needed, is a UX call for the
  builder.

## Decisions resolved after review

1. **The two broken forms — root cause found.** `uni-heidelberg` and `uni-koln` fail in
   `pdfrw`, the unmaintained (2018) PDF parser that `fillpdfs` wraps, while parsing
   their compressed object streams. Confirmed *not* a Python-version issue (fails
   identically on 3.10, 3.12, 3.14) and *not* a library-version issue (fails with both
   `pdfrw2` 0.5.0 and the original `pdfrw` 0.4). `uni-hamburg` and `uni-ulm` parse
   fine. `pymupdf` — already installed as a transitive dependency of `fillpdf` —
   reads all four without error. **Resolution: replace the `pdfrw`-based read/write
   calls with `pymupdf`.** No new dependency. Confirmed.

2. **Sessions across workers — decided.** Pin production to a single worker (`--workers 1`).
   Inference is serial anyway per the Ollama configuration, and it keeps the existing
   in-memory session store correct.

3. **Shared or single institution — decided for now.** One deployment holds everything
   in one place; no per-deployment config isolation yet. On a `client_name` collision,
   **refuse and ask for a different name** — never overwrite. Per-deployment configs
   are explicitly deferred to a later effort.

## Acceptance criteria

- A user can go from landing to a downloaded filled PDF without seeing a developer term.
- A user can pick an existing university and never see the upload-a-form path.
- A new university can be onboarded, named, and reused from the dropdown afterwards.
- Unticking a field leaves it out of the PDF; editing a value puts the edit in the PDF.
- The frontend runs as its own container and holds no backend code or filesystem access.
