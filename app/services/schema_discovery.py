"""
FormFlow - Form Schema Discovery Agent

Analyzes PDF form templates to discover and understand form fields.
Uses pymupdf for field extraction and vision model for semantic understanding.
"""

import os
import json
import io
import logging
import uuid
from typing import Any
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_bytes
import io
from app.services.inference import get_inference_client
from app.services.pdf_form import read_form_fields

# Set up logging
logger = logging.getLogger(__name__)


def decode_pdf_field_name(name: str) -> str:
    """Decode PDF field names that may be UTF-16 encoded.
    
    Some PDFs store field names as UTF-16-BE with BOM (þÿ prefix).
    This decodes them back to readable strings.
    """
    # Check for UTF-16 BOM pattern: þÿ followed by null-separated chars
    if name.startswith('þÿ') or name.startswith('\xfe\xff'):
        try:
            # Remove BOM and decode: \x00P\x00r\x00i\x00v -> "Priv"
            # The pattern is: þÿ + \x00<char>\x00<char>...
            cleaned = name[2:]  # Remove BOM
            # Extract every other character (skip nulls)
            decoded = cleaned.replace('\x00', '')
            if decoded:
                return decoded
        except Exception:
            pass
    return name


def clean_pdf_fields(fields: dict) -> dict:
    """Clean PDF field names by decoding UTF-16 and normalizing."""
    cleaned = {}
    for key, value in fields.items():
        clean_key = decode_pdf_field_name(key)
        cleaned[clean_key] = value
    return cleaned


def extract_json_from_response(content: str) -> str:
    """Extract JSON from model response, handling markdown code blocks."""
    # Strip markdown code blocks if present
    content = content.strip()
    if content.startswith('```json'):
        content = content[7:]  # Remove ```json
    elif content.startswith('```'):
        content = content[3:]  # Remove ```
    
    if content.endswith('```'):
        content = content[:-3]  # Remove trailing ```
    
    return content.strip()


def resize_image_for_inference(image_bytes: bytes, max_size: int = 1024) -> bytes:
    """Resize image to reduce token count while preserving readability"""
    img = Image.open(io.BytesIO(image_bytes))
    
    # Calculate new size maintaining aspect ratio
    ratio = min(max_size / img.width, max_size / img.height)
    if ratio < 1:
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to RGB if necessary (for JPEG)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return buffer.getvalue()


def pdf_to_images(pdf_bytes: bytes, max_size: int = 1024) -> list[bytes]:
    """Convert PDF pages to resized images"""
    images = convert_from_bytes(pdf_bytes)
    result = []
    
    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        resized = resize_image_for_inference(buffer.getvalue(), max_size)
        result.append(resized)
    
    return result


class FormSchemaDiscoveryAgent:
    """Agent for discovering form schemas from PDF templates"""
    
    def __init__(self):
        self.inference_client = get_inference_client()
    
    async def discover_schema(
        self,
        form_pdf_bytes: bytes,
        client_name: str = "pending"
    ) -> dict:
        """
        Analyze a PDF form template and discover its schema.
        
        1. Extract field names using pymupdf
        2. Convert PDF to images
        3. Use vision model to understand field semantics
        4. Return structured schema
        """
        
        # Step 1: Extract PDF form fields
        # pymupdf reads fields from a path, so stage the upload briefly under a
        # unique name (several uploads can be in flight at once)
        temp_path = Path(f"/tmp/{uuid.uuid4().hex}_form.pdf")
        temp_path.write_bytes(form_pdf_bytes)
        
        try:
            raw_fields = read_form_fields(str(temp_path))
            pdf_fields = clean_pdf_fields(raw_fields)
            logger.info(f"Extracted {len(pdf_fields)} PDF fields via pymupdf")
        except Exception as e:
            logger.warning(f"Failed to extract PDF fields: {e}")
            pdf_fields = {}
        finally:
            temp_path.unlink(missing_ok=True)
        
        # A scan or flattened PDF has no form fields, so there is nothing the
        # vision model could map extracted values onto.
        if not pdf_fields:
            return {
                "error": "This PDF has no fillable form fields. Please upload the blank form, not a scan.",
                "pdf_fields_raw": {},
            }
        
        # Step 2: Convert PDF to images for vision analysis
        form_images = pdf_to_images(form_pdf_bytes, max_size=1024)
        logger.info(f"Converted PDF to {len(form_images)} images for vision analysis")
        
        # Step 3: Use vision model to analyze the form
        system_prompt = """You are a form analysis expert. Analyze PDF forms and understand field meanings.
Respond with valid JSON only. Do NOT wrap in markdown code blocks. No ``` markers."""

        analysis_prompt = f"""Analyze this form image and the PDF field names below.

PDF Field Names Found:
{json.dumps(list(pdf_fields.keys()), indent=2, ensure_ascii=False)}

For EACH field, provide:
- data_type: text|date|number|currency|checkbox|email|phone
- description: Short human-readable description of the field
- field_name: Original PDF field name
- required: true/false
- semantic_name: Clear English name or normalized label

Respond with this JSON structure:
{{
  "institution_name": "University or organisation this form belongs to, in its own language",
  "form_title": "Form title",
  "form_language": "German/English/etc",
  "fields": [
        {{"data_type": "text", "description": "Field description", "field_name": "original_name", "required": false, "semantic_name": "english_name"}}
  ]
}}"""

        try:
            logger.info(f"Sending {len(form_images[:2])} images to vision model for analysis...")
            response = await self.inference_client.chat_with_vision(
                prompt=analysis_prompt,
                images=form_images[:2],  # Send first 2 pages
                system_prompt=system_prompt
            )
            logger.info(f"Vision model responded. Response keys: {response.keys() if response else 'None'}")
            
            # Extract the response content
            content = response.get("message", {}).get("content", "")
            logger.info(f"Response content length: {len(content)} chars")
            if len(content) < 500:
                logger.info(f"Full response content: {content}")
            else:
                logger.info(f"Response preview: {content[:500]}...")
            
            # Try to parse as JSON
            try:
                # Clean markdown code blocks and find JSON
                cleaned_content = extract_json_from_response(content)
                json_start = cleaned_content.find('{')
                json_end = cleaned_content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    schema = json.loads(cleaned_content[json_start:json_end])
                    logger.info(f"Successfully parsed JSON with {len(schema.get('fields', []))} fields")
                else:
                    logger.warning(f"No JSON found in response. Content: {cleaned_content[:200]}")
                    schema = {"error": "No JSON found in response", "raw_response": content}
            except json.JSONDecodeError as je:
                logger.error(f"JSON parse error: {je}. Content: {cleaned_content[:200]}")
                schema = {"error": "Invalid JSON in response", "raw_response": content}
            
            # Add the raw PDF fields for reference
            schema["pdf_fields_raw"] = pdf_fields
            
            # The institution name is what the user confirms; fall back to the
            # form title when the model does not supply one.
            schema["institution_name"] = (
                schema.get("institution_name")
                or schema.get("form_title")
                or "Unknown institution"
            )
            
            return schema
            
        except Exception as e:
            logger.exception(f"Vision inference failed: {e}")
            return {
                "error": str(e),
                "pdf_fields_raw": pdf_fields
            }

