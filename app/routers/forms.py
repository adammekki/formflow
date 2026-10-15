"""
FormFlow - Forms Router

Endpoints for form template management and schema discovery.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
import shutil
import uuid
import yaml

from app.config import settings
from app.services.naming import slugify
from app.services.schema_discovery import FormSchemaDiscoveryAgent


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forms")


class FormField(BaseModel):
    """Schema for a discovered form field."""
    name: str
    field_type: str
    description: Optional[str] = None
    required: bool = False


class FormSchemaResponse(BaseModel):
    """Response model for form schema discovery."""
    status: str
    proposal_id: Optional[str] = None
    institution_name: Optional[str] = None
    form_title: Optional[str] = None
    form_language: Optional[str] = None
    field_count: int = 0
    fields: list[FormField] = []
    raw_fields: dict = {}  # Original field names from PDF
    error: Optional[str] = None  # Error message if discovery failed


def normalize_field_name(field_name):
    """The model occasionally returns a list of aliases for a single field."""
    if isinstance(field_name, list):
        return "_".join(str(f) for f in field_name)
    return str(field_name)


@router.post("/discover-schema", response_model=FormSchemaResponse)
async def discover_form_schema(
    form_template: UploadFile = File(..., description="PDF form template to analyze"),
):
    """
    Analyze a PDF form template and discover its field schema.

    This endpoint:
    1. Extracts all fillable fields from the PDF using pymupdf
    2. Uses vision model to analyze the form and infer field meanings
    3. Proposes an institution name and stages the upload

    Nothing is written to configs/ here. The traveller confirms the proposed
    name through /confirm-schema, which moves the staged files into place.
    """
    # Validate file type
    if not form_template.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await form_template.read()
    proposal_id = str(uuid.uuid4())
    staging_dir = os.path.join(settings.templates_dir, ".staging", proposal_id)

    # Run discovery before creating anything, so a form with no usable fields
    # leaves no staging directory behind.
    try:
        agent = FormSchemaDiscoveryAgent()
        schema = await agent.discover_schema(contents)

        # Check for errors in the schema response. The raw model output stays in
        # the logs: the traveller only ever sees a sentence they can act on.
        if "error" in schema:
            error_msg = schema.get("error", "Unknown error")
            logger.warning(
                "Schema discovery failed: %s | raw response: %s",
                error_msg,
                str(schema.get("raw_response", ""))[:500],
            )
            return FormSchemaResponse(
                status="error",
                raw_fields=schema.get("pdf_fields_raw", {}),
                error=error_msg,
            )

        # Normalize fields in schema before staging
        normalized_fields = []
        for f in schema.get("fields", []):
            normalized_f = dict(f)  # Copy the field
            normalized_f["field_name"] = normalize_field_name(f.get("field_name", "unknown"))
            normalized_fields.append(normalized_f)

        # Stage the upload and the draft config for /confirm-schema to move
        os.makedirs(staging_dir, exist_ok=True)
        with open(os.path.join(staging_dir, "form_template.pdf"), "wb") as f:
            f.write(contents)

        draft_config = {
            "client_name": "pending",
            "institution_name": schema.get("institution_name", "Unknown institution"),
            "form_title": schema.get("form_title", "Unknown Form"),
            "form_language": schema.get("form_language", "unknown"),
            "supported_languages": ["en", "de"],
            "target_currency": "EUR",
            "fields": normalized_fields,
            "pdf_fields_raw": list(schema.get("pdf_fields_raw", {}).keys()),
        }

        with open(os.path.join(staging_dir, "config.yaml"), "w") as f:
            yaml.dump(draft_config, f, default_flow_style=False, allow_unicode=True)

        return FormSchemaResponse(
            status="success",
            proposal_id=proposal_id,
            institution_name=draft_config["institution_name"],
            form_title=draft_config["form_title"],
            form_language=draft_config["form_language"],
            field_count=len(normalized_fields),
            fields=[FormField(
                name=normalize_field_name(f["field_name"]),
                field_type=f.get("data_type", "text"),
                description=f.get("description") or f.get("semantic_name"),
                required=f.get("required", False)
            ) for f in normalized_fields],
            raw_fields=schema.get("pdf_fields_raw", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema discovery failed: {str(e)}")

class ConfirmSchemaRequest(BaseModel):
    """Confirmation of the agent's proposed institution name."""
    proposal_id: str
    institution_name: str


@router.post("/confirm-schema")
async def confirm_schema(request: ConfirmSchemaRequest):
    """
    Save a staged form under the name the traveller confirmed.

    The agent proposes an institution name during discovery; this endpoint is
    where the user's correction takes effect. The slugified name becomes the
    client id used by the extraction endpoints.
    """
    institution_name = request.institution_name.strip()
    slug = slugify(institution_name)

    # Checked before the staging lookup so a blank name always reads as a name
    # problem, whatever the proposal's state.
    if not institution_name or not slug:
        raise HTTPException(status_code=422, detail="Please provide the university's name")

    staging_dir = os.path.join(settings.templates_dir, ".staging", request.proposal_id)
    if not os.path.isdir(staging_dir):
        raise HTTPException(
            status_code=404,
            detail="This form is no longer available. Please upload it again.",
        )

    config_dir = os.path.join(settings.configs_dir, slug)
    template_dir = os.path.join(settings.templates_dir, slug)
    if os.path.exists(config_dir) or os.path.exists(template_dir):
        raise HTTPException(
            status_code=409,
            detail=f"{institution_name} is already set up. Please pick it from the list.",
        )

    draft_path = os.path.join(staging_dir, "config.yaml")
    draft: dict = {}
    if os.path.exists(draft_path):
        with open(draft_path, "r") as f:
            draft = yaml.safe_load(f) or {}
    draft["client_name"] = slug
    draft["institution_name"] = institution_name

    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(template_dir, exist_ok=True)

    with open(os.path.join(config_dir, "config.yaml"), "w") as f:
        yaml.dump(draft, f, default_flow_style=False, allow_unicode=True)

    shutil.move(
        os.path.join(staging_dir, "form_template.pdf"),
        os.path.join(template_dir, "form_template.pdf"),
    )
    shutil.rmtree(staging_dir, ignore_errors=True)

    return {
        "status": "success",
        "client_name": slug,
        "institution_name": institution_name,
    }


@router.get("/clients")
async def list_clients():
    """List configured clients with the name to show the traveller."""
    clients = []
    configs_path = settings.configs_dir
    
    if os.path.exists(configs_path):
        for entry in os.listdir(configs_path):
            client_path = os.path.join(configs_path, entry)
            if not os.path.isdir(client_path):
                continue

            config_file = os.path.join(client_path, "config.yaml")
            configured = os.path.exists(config_file)

            # Without a form template there is nothing to fill, so the
            # university cannot be used and must not be offered.
            template_file = os.path.join(
                settings.templates_dir, entry, "form_template.pdf"
            )
            if not os.path.exists(template_file):
                continue

            # The traveller picks their university by its display name. Configs
            # written before that field existed fall back to the directory name.
            institution_name = entry
            if configured:
                try:
                    with open(config_file, "r") as f:
                        loaded = yaml.safe_load(f) or {}
                    institution_name = loaded.get("institution_name") or entry
                except Exception:
                    pass

            clients.append({
                "name": entry,
                "institution_name": institution_name,
                "configured": configured,
            })
    
    return {"clients": clients}


@router.get("/clients/{client_name}")
async def get_client_config(client_name: str):
    """Get configuration for a specific client."""
    config_path = os.path.join(settings.configs_dir, client_name, "config.yaml")
    
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Client '{client_name}' not found")
    
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    return {"client_name": client_name, "config": config}
