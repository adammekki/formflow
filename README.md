# FormFlow

**Generalized AI Form-Filling Platform**

Transform any PDF form filling workflow using open-source LLMs with built-in explainability, multi-language support, and continuous learning capabilities.

FormFlow reads a stack of receipts with a vision model and fills in a university travel-expense form. It ships with a desktop web frontend, so a traveller can go from "I have receipts" to "I have the form" without touching an API.

## How it works

1. **Pick your form.** Choose an already-configured university, or upload a blank PDF form. For a new one, the model reads the form, proposes an institution name, and you confirm it.
2. **Upload receipts.** Drop in all the PDFs and images from the trip; they are read together so they can be cross-referenced.
3. **Review.** Every value the model extracted, with its confidence and source document. Correct anything wrong and untick what you do not need.
4. **Download.** The filled PDF, built from the fields you kept.

## Features

- 🔍 **Form Schema Discovery** — Analyse a PDF form and infer what each field means
- 📄 **Multi-Language Receipt Processing** — German, English, French, Spanish, Arabic
- 📦 **Explainability** — Each value carries a confidence score and the document it came from
- 🔧 **Config-Driven** — Onboard a new university with YAML, no code changes
- 📈 **Continuous Learning** — User corrections are captured as feedback data
- 🐳 **Containerized** — Backend and frontend are separate services
- 🖥️ **Web frontend** — A four-step desktop UI in `frontend/`

## Quick Start

### Prerequisites

- Docker & Docker Compose
- [Ollama](https://ollama.com) running on the host, with a vision model pulled
- (Local development only) Python 3.11+, Node 20+, Poppler

### Docker

1. **Configure:**
   ```bash
   cp .env.example .env
   ```

2. **Pull the vision model (first time only).** The compose file uses a native
   Ollama on the host, so this runs on your machine, not in a container:
   ```bash
   ollama pull ministral-3:8b
   ```

3. **Start both services:**
   ```bash
   docker compose up -d
   ```

4. **Open it:**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## Local Development

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Poppler is required for PDF -> image conversion
brew install poppler            # macOS
apt-get install poppler-utils   # Debian/Ubuntu

ollama serve
ollama pull ministral-3:8b

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

The frontend calls the API directly. Point it somewhere else with `VITE_API_BASE`
(see `frontend/.env.example`); in the production image this is a build argument,
because the value is compiled into the bundle.

## Project Structure

```
formflow/
├── app/                          # FastAPI backend
│   ├── main.py                   # Application entry point and logging setup
│   ├── config.py                 # Settings (environment + .env)
│   ├── routers/
│   │   ├── health.py             # Health, liveness, readiness
│   │   ├── forms.py              # Schema discovery, onboarding, client list
│   │   └── extraction.py         # Receipt extraction, verification, download
│   └── services/
│       ├── inference.py          # Ollama / vLLM client
│       ├── pdf_form.py           # Read and fill AcroForm fields (pymupdf)
│       ├── naming.py             # Slugs and safe filenames
│       ├── schema_discovery.py   # Form analysis agent
│       └── pipeline.py           # Extraction and form-filling pipeline
├── frontend/                     # React + Vite + TypeScript SPA
│   └── src/
│       ├── api.ts                # Typed API client
│       ├── App.tsx               # Four-step flow and transitions
│       └── steps/                # One component per step
├── configs/{client_name}/
│   ├── config.yaml               # Fields, languages, currency
│   └── extraction_prompt.txt     # Optional custom extraction prompt
├── templates/{client_name}/
│   ├── form_template.pdf         # The blank fillable form
│   └── output/                   # Generated filled PDFs
├── feedback/                     # Correction data captured during review
├── tests/                        # Backend test suite
└── docs/superpowers/             # Design documents and implementation plans
```

## Onboarding a University

The UI does this in step 1 — upload the blank form and confirm the proposed name.
The equivalent API calls:

```bash
# 1. Analyse the blank form. Stages the upload; writes nothing yet.
#    The PDF must have real form fields, not be a scan.
curl -X POST "http://localhost:8000/api/forms/discover-schema" \
  -F "form_template=@/path/to/blank-form.pdf"

# 2. Confirm the institution name. This saves the form and its config, and
#    refuses (409) if a university with the same slug already exists.
curl -X POST "http://localhost:8000/api/forms/confirm-schema" \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": "<from step 1>", "institution_name": "Universität Hamburg"}'
```

The generated `config.yaml` is a starting point: refine the field descriptions and
the extraction prompt if the model's guesses need sharpening.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check including inference backend status |
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe (503 until inference is reachable) |
| GET | `/api/forms/clients` | List configured universities with display names |
| GET | `/api/forms/clients/{client_name}` | Full configuration for one university |
| POST | `/api/forms/discover-schema` | Analyse an uploaded blank form; returns a proposal |
| POST | `/api/forms/confirm-schema` | Save a staged form under the confirmed name |
| POST | `/api/extract/process` | Upload receipts; returns a session and extracted fields |
| POST | `/api/extract/verify` | Submit kept/corrected values and fill the PDF |
| GET | `/api/extract/download/{client_name}/{filename}` | Download a filled PDF |
| GET | `/api/extract/session/{session_id}` | Status of an extraction session |

`/api/extract/verify` accepts `kept_fields` (the fields to place on the form) and
returns `unmatched_fields`: any value that matched no field on the form, so a stale
config is reported rather than silently producing a half-empty PDF.

## Configuration

Settings come from the environment or `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `development` | Environment name |
| `LOG_LEVEL` | `INFO` | Application log level |
| `INFERENCE_PROVIDER` | `ollama` | `ollama` or `vllm` |
| `INFERENCE_BASE_URL` | `http://localhost:11434` | Inference server |
| `INFERENCE_MODEL` | `ministral-3:8b` | Vision model to use |
| `INFERENCE_TIMEOUT` | `120` | Inference timeout, seconds |
| `CONFIGS_DIR` | `/app/configs` | Where client configs live |
| `TEMPLATES_DIR` | `/app/templates` | Where form templates and output live |
| `FEEDBACK_DIR` | `/app/feedback` | Where correction data is written |
| `CORS_ORIGINS` | `localhost:3000`, `127.0.0.1:3000`, `localhost:8000` | Allowed browser origins (comma-separated) |
| `VITE_API_BASE` | `http://localhost:8000` | Frontend: API base URL (build-time in production) |

Per-client settings — field definitions, supported languages, target currency,
prompt — live in `configs/{client_name}/config.yaml`. See `configs/uni-hamburg/config.yaml`.

## Tests

```bash
# Backend
pytest

# Frontend
npm --prefix frontend test
```

## Production

```bash
# docker-compose.prod.yml runs vLLM with GPU support
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

Notes:

- The production API runs a **single worker**. Extraction sessions are held in
  process memory, so a second worker would not find a session created by the first.
- `configs/` and `templates/` must be writable: onboarding writes to both, and
  filling writes generated PDFs.
- Set the frontend's public API URL at build time with the `VITE_API_BASE` build arg.

## Known Limitations

- **Three bundled configs are stale.** `uni-heidelberg`, `uni-koln` and `uni-ulm`
  store field names that no longer match their PDFs (human labels rather than the
  form's internal field names), so only some values can be placed. Those runs show
  an on-screen warning instead of failing quietly. Regenerate the config through
  schema discovery to fix them; `tests/test_pdf_form.py` pins their match rate as a
  tripwire.
- **No authentication.** Anything that can reach the API can create configs and
  read generated forms. Intended for a trusted local or office network.
- **Sessions are in-memory.** Restarting the API loses in-flight extractions.

## License

[MIT License](LICENSE)
