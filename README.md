# FormFlow

**Generalized AI Form-Filling Platform**

Transform any PDF form filling workflow using open-source LLMs with built-in explainability, multi-language support, and continuous learning capabilities.

## Features

- 🔍 **Form Schema Discovery** - Automatically analyze PDF forms to understand field structure
- 📄 **Multi-Language Receipt Processing** - Extract data from receipts in German, English, French, Spanish, Arabic
- 📦 **Bounding Box Explainability** - See exactly where each value was extracted from
- 🔧 **Config-Driven** - Onboard new clients with YAML configuration, no code changes
- 📈 **Continuous Learning** - Capture user corrections for future model improvement
- 🐳 **Containerized** - Docker-first architecture for easy deployment

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (For local dev without Docker) Python 3.11+, Poppler

### Development Setup

1. **Clone and configure:**
   ```bash
   cd formflow
   cp .env.example .env
   ```

2. **Start the stack:**
   ```bash
   docker-compose up
   ```

3. **Pull the vision model (first time only):**
   ```bash
   docker exec -it formflow-ollama ollama pull ministral-3:8b
   ```

4. **Access the API:**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

### Local Development (without Docker)

1. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. **Install Poppler** (for PDF processing):
   ```bash
   # macOS
   brew install poppler
   
   # Ubuntu/Debian
   apt-get install poppler-utils
   ```

3. **Start Ollama separately:**
   ```bash
   ollama serve
   ollama pull qwen3-vl:8b
   ```

4. **Run the app:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Project Structure

```
formflow/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Application settings
│   ├── routers/
│   │   ├── health.py        # Health check endpoints
│   │   ├── forms.py         # Form management endpoints
│   │   └── extraction.py    # Extraction endpoints
│   └── services/
│       ├── inference.py     # Ollama/vLLM client
│       ├── schema_discovery.py  # Form analysis agent
│       └── pipeline.py      # Extraction pipeline
├── configs/
│   └── {client_name}/
│       ├── config.yaml      # Client configuration
│       └── extraction_prompt.txt
├── templates/
│   └── {client_name}/
│       └── form_template.pdf
├── feedback/                 # Training data from corrections
├── docker-compose.yml       # Development setup
├── docker-compose.prod.yml  # Production setup
├── Dockerfile
└── requirements.txt
```

## Client Onboarding

1. **Create client directory:**
   ```bash
   mkdir -p configs/new_client
   mkdir -p templates/new_client
   ```

2. **Copy and customize config:**
   ```bash
   cp configs/example_company/config.yaml configs/new_client/
   ```

3. **Upload form template via API:**
   ```bash
   curl -X POST "http://localhost:8000/api/forms/discover-schema?client_name=new_client" \
     -F "form_template=@/path/to/form.pdf"
   ```

4. **Refine the generated schema and extraction prompt**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with dependency status |
| POST | `/api/forms/discover-schema` | Analyze PDF form template |
| GET | `/api/forms/clients` | List configured clients |
| POST | `/api/extract/process` | Extract data from receipts |
| POST | `/api/extract/verify` | Submit verified data and fill PDF |

## Configuration Reference

See `configs/example_company/config.yaml` for full configuration options including:
- Field definitions with PDF mappings
- Language support settings
- Currency handling
- Extraction prompts
- Validation rules

## Production Deployment

1. **Configure for vLLM:**
   ```bash
   # Edit .env
   INFERENCE_PROVIDER=vllm
   INFERENCE_BASE_URL=http://vllm:8000/v1
   ```

2. **Deploy with GPU support:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## License

[MIT License](LICENSE)
