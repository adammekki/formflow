"""
FormFlow - Extraction Router

Endpoints for document extraction and form filling.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import tempfile
import shutil

from app.config import settings
from app.services.naming import safe_filename, unique_filename
from app.services.pipeline import FormFillingPipeline


router = APIRouter(prefix="/extract")


# In-memory session storage for verification workflow
verification_sessions: dict = {}


class BoundingBox(BaseModel):
    """Bounding box coordinates for explainability."""
    page: int
    x: float
    y: float
    width: float
    height: float


class ExtractedField(BaseModel):
    """An extracted field with explainability metadata."""
    field_name: str
    value: str
    source_document: str
    bounding_box: Optional[BoundingBox] = None
    confidence: float
    reasoning: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Response model for extraction endpoint."""
    status: str
    session_id: str
    message: str
    extracted_fields: list[ExtractedField]
    errors: Optional[list[str]] = None


class VerifyRequest(BaseModel):
    """Request model for submitting verified/corrected data."""
    session_id: str
    verified_fields: dict[str, str]
    kept_fields: Optional[list[str]] = None


class FillResponse(BaseModel):
    """Response model for form filling."""
    status: str
    message: str
    download_url: Optional[str] = None
    errors: Optional[list[str]] = None


@router.post("/process", response_model=ExtractionResponse)
async def extract_from_receipts(
    client_name: str = Form(..., description="Client configuration to use"),
    receipts: list[UploadFile] = File(..., description="Receipt documents (PDF or images)"),
):
    """
    Extract data from uploaded receipts using client-specific configuration.
    
    This endpoint:
    1. Loads the client's extraction prompt from config
    2. Processes all uploaded receipts through the vision model
    3. Returns extracted fields with bounding boxes for explainability
    4. Creates a verification session for user review
    """
    # Validate client exists
    config_path = os.path.join(settings.configs_dir, client_name, "config.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Client '{client_name}' not configured")
    
    # Create session
    session_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"formflow_{session_id}_")
    
    errors = []
    saved_receipts = []
    taken_names: set[str] = set()
    
    try:
        # Save uploaded receipts under their original names so extracted values
        # can cite a document the traveller recognises.
        for receipt in receipts:
            ext = os.path.splitext(receipt.filename)[1].lower()
            if ext not in [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
                errors.append(f"Unsupported file type: {receipt.filename}")
                continue
            
            filename = unique_filename(safe_filename(receipt.filename), taken_names)
            taken_names.add(filename)
            receipt_path = os.path.join(temp_dir, filename)
            contents = await receipt.read()
            with open(receipt_path, "wb") as f:
                f.write(contents)
            saved_receipts.append(receipt_path)
        
        if not saved_receipts:
            raise HTTPException(status_code=400, detail="No valid receipts uploaded")
        
        # Run extraction pipeline
        pipeline = FormFillingPipeline(client_name)
        extraction_result = await pipeline.extract(saved_receipts)
        
        # Store session for verification
        verification_sessions[session_id] = {
            "temp_dir": temp_dir,
            "client_name": client_name,
            "extracted_data": extraction_result["fields"],
            "receipt_paths": saved_receipts,
        }
        
        return ExtractionResponse(
            status="success",
            session_id=session_id,
            message="Data extracted successfully. Please verify before filling form.",
            extracted_fields=[ExtractedField(**f) for f in extraction_result["fields"]],
            errors=errors if errors else None,
        )
        
    except Exception as e:
        # Cleanup on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/verify", response_model=FillResponse)
async def submit_verified_data(request: VerifyRequest):
    """
    Submit verified/corrected data and generate the filled PDF.
    
    This endpoint:
    1. Retrieves the extraction session
    2. Applies user corrections
    3. Fills the PDF form
    4. Stores feedback for future model improvement
    5. Returns download URL for the filled form
    """
    session_id = request.session_id
    
    if session_id not in verification_sessions:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session = verification_sessions[session_id]
    
    try:
        # Run form filling with verified data
        pipeline = FormFillingPipeline(session["client_name"])
        result = await pipeline.fill_form(
            extracted_data=session["extracted_data"],
            verified_data=request.verified_fields,
            kept_fields=request.kept_fields,
        )
        
        # Store feedback for training (original vs corrected)
        await pipeline.store_feedback(
            session_id=session_id,
            original=session["extracted_data"],
            corrected=request.verified_fields,
            receipt_paths=session["receipt_paths"],
        )
        
        # Cleanup session
        shutil.rmtree(session["temp_dir"], ignore_errors=True)
        del verification_sessions[session_id]
        
        return FillResponse(
            status="success",
            message="Form filled successfully",
            download_url=f"/api/extract/download/{session['client_name']}/{result['filename']}",
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Form filling failed: {str(e)}")

@router.get("/download/{client_name}/{filename}")
async def download_filled_form(client_name: str, filename: str):
    """Download a generated filled form PDF."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    output_path = os.path.join(
        settings.templates_dir,
        client_name,
        "output",
        filename,
    )

    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=filename,
    )

@router.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """Get the status of an extraction session."""
    if session_id not in verification_sessions:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session = verification_sessions[session_id]
    return {
        "session_id": session_id,
        "client_name": session["client_name"],
        "field_count": len(session["extracted_data"]),
    }
