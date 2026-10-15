"""
FormFlow - Forms Router

Endpoints for form template management and schema discovery.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from app.config import settings
from app.services.schema_discovery import FormSchemaDiscoveryAgent


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
    client_name: str
    field_count: int
    fields: list[FormField]
    raw_fields: dict  # Original field names from PDF
    error: Optional[str] = None  # Error message if discovery failed

@router.post("/discover-schema", response_model=FormSchemaResponse)
async def discover_form_schema(
    client_name: str,
    form_template: UploadFile = File(..., description="PDF form template to analyze"),
):
    """
    Analyze a PDF form template and discover its field schema.
    
    This endpoint:
    1. Extracts all fillable fields from the PDF using pymupdf
    2. Uses vision model to analyze the form and infer field meanings
    3. Returns a draft schema for refinement during client onboarding
    """
    # Validate file type
    if not form_template.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Create client directory if it doesn't exist
    client_dir = os.path.join(settings.templates_dir, client_name)
    os.makedirs(client_dir, exist_ok=True)
    
    # Save the uploaded template
    template_path = os.path.join(client_dir, "form_template.pdf")
    contents = await form_template.read()
    with open(template_path, "wb") as f:
        f.write(contents)
    
    # Run schema discovery
    try:
        agent = FormSchemaDiscoveryAgent()
        schema = await agent.discover_schema(contents, client_name)
        
        # Check for errors in the schema response
        if "error" in schema:
            error_msg = schema.get("error", "Unknown error")
            raw_response = schema.get("raw_response", "")
            # Include raw_fields even on error for debugging
            return FormSchemaResponse(
                status="error",
                client_name=client_name,
                field_count=0,
                fields=[],
                raw_fields=schema.get("pdf_fields_raw", {}),
                error=f"{error_msg}. Raw response: {raw_response[:500] if raw_response else 'empty'}"
            )
        
        # Create config directory and save initial config
        import yaml
        config_dir = os.path.join(settings.configs_dir, client_name)
        os.makedirs(config_dir, exist_ok=True)
        
        # Normalize field_name in case model returns list
        def normalize_field_name(field_name):
            if isinstance(field_name, list):
                return "_".join(str(f) for f in field_name)
            return str(field_name)
        
        # Normalize fields in schema before saving
        normalized_fields = []
        for f in schema.get("fields", []):
            normalized_f = dict(f)  # Copy the field
            normalized_f["field_name"] = normalize_field_name(f.get("field_name", "unknown"))
            normalized_fields.append(normalized_f)
        
        # Build initial config from discovered schema
        initial_config = {
            "client_name": client_name,
            "form_title": schema.get("form_title", "Unknown Form"),
            "form_language": schema.get("form_language", "unknown"),
            "supported_languages": ["en", "de"],
            "target_currency": "EUR",
            "fields": normalized_fields,
            "pdf_fields_raw": list(schema.get("pdf_fields_raw", {}).keys()),
        }
        
        config_path = os.path.join(config_dir, "config.yaml")
        with open(config_path, "w") as f:
            yaml.dump(initial_config, f, default_flow_style=False, allow_unicode=True)
        
        return FormSchemaResponse(
            status="success",
            client_name=client_name,
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

@router.get("/clients")
async def list_clients():
    """List all configured clients."""
    clients = []
    configs_path = settings.configs_dir
    
    if os.path.exists(configs_path):
        for entry in os.listdir(configs_path):
            client_path = os.path.join(configs_path, entry)
            if os.path.isdir(client_path):
                config_file = os.path.join(client_path, "config.yaml")
                clients.append({
                    "name": entry,
                    "configured": os.path.exists(config_file),
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
