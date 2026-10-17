"""
FormFlow - Form Filling Pipeline

Sequential pipeline orchestrator that coordinates:
1. Loading client configuration
2. Extracting data from receipts
3. Mapping extracted values to form fields
4. Filling the PDF form
5. Storing feedback for learning
"""

import os
import asyncio
import json
import logging
import yaml
from datetime import datetime
from typing import Any
from app.config import settings
from app.services.inference import InferenceClient
from app.services.pdf_form import fill_form_fields


logger = logging.getLogger(__name__)


class FormFillingPipeline:
    """
    Sequential pipeline for form filling.
    
    Orchestrates the complete flow from receipt upload to filled PDF.
    """
    
    def __init__(self, client_name: str):
        """
        Initialize pipeline for a specific client.
        
        Args:
            client_name: Name of the client configuration to use
        """
        self.client_name = client_name
        self.config = self._load_config()
        self.inference = InferenceClient()
    
    def _load_config(self) -> dict[str, Any]:
        """Load client configuration from YAML file."""
        config_path = os.path.join(
            settings.configs_dir,
            self.client_name,
            "config.yaml"
        )
        
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration not found for client: {self.client_name}")
        
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    
    def _load_extraction_prompt(self) -> str:
        """Load the saved extraction prompt for this client."""
        prompt_path = os.path.join(
            settings.configs_dir,
            self.client_name,
            "extraction_prompt.txt"
        )
        
        if not os.path.exists(prompt_path):
            # Fallback to generating a basic prompt from config
            return self._generate_basic_prompt()
        
        with open(prompt_path, "r") as f:
            return f.read()
    
    def _generate_basic_prompt(self) -> str:
        """Generate a basic extraction prompt from config."""
        fields = self.config.get("fields", [])
        languages = self.config.get("supported_languages", ["en"])

        fields_list = []
        for field in fields:
            field_name = field["field_name"]
            semantic_name = field.get("semantic_name", "")
            description = field.get("description", "")
            data_type = field.get("data_type", "text")
            required = str(bool(field.get("required", False))).lower()

            fields_list.append(
                f"  - data_type: {json.dumps(data_type)}\n"
                f"    description: {json.dumps(description)}\n"
                f"    field_name: {json.dumps(field_name)}\n"
                f"    required: {required}\n"
                f"    semantic_name: {json.dumps(semantic_name)}"
            )
        
        fields_desc = "\n".join(fields_list)
        
        return f"""You are extracting data from receipt/travel documents to fill a form.
Documents may be in: {', '.join(languages)}

FIELDS TO EXTRACT:
{fields_desc}

INSTRUCTIONS:
- Look at ALL uploaded documents/images carefully
- For each field, extract the actual value you find in the documents
- If a value is found, you MUST include it in the "value" property
- If a value is not found in any document, set value to "" and confidence to 0
- Use the exact field_name from the list above
- Use semantic_name as the human-readable meaning when it helps disambiguate fields
- Note which document each value came from

Respond with this exact JSON structure (no markdown, no code blocks):
{{
  "fields": [
    {{
      "field_name": "exact_field_name_from_list",
      "value": "the actual extracted value here",
      "source_document": "name of the document it came from",
      "confidence": number ranging from 0-1 indicating confidence in the extraction,
      "reasoning": "brief explanation"
    }}
  ]
}}

Only include fields where you found relevant information (confidence > 0). Do NOT wrap in markdown code blocks.
"""
    
    def _resize_image(self, image_bytes: bytes, max_size: int = 1024) -> bytes:
        """Resize image to reduce token count while preserving readability."""
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        ratio = min(max_size / img.width, max_size / img.height)
        if ratio < 1:
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        return buffer.getvalue()

    def _mock_fields(self) -> list[dict]:
        """Canned values shaped like real extraction output, for previewing the UI."""
        fields = []
        for index, field in enumerate(self.config.get("fields", [])):
            name = field.get("field_name", "unknown")
            label = field.get("semantic_name") or name

            # A deliberate spread so the review screen shows every state it has:
            # confident, unsure, and found-nothing.
            if index % 7 == 3:
                value, confidence = "", 0.2
            elif index % 3 == 1:
                value, confidence = f"Sample {label}", 0.45
            else:
                value, confidence = f"Sample {label}", 0.95

            fields.append({
                "field_name": name,
                "semantic_name": field.get("semantic_name"),
                "value": value,
                "source_document": "sample-receipt.pdf",
                "bounding_box": None,
                "confidence": confidence,
                "reasoning": "dummy value (MOCK_EXTRACTION)",
            })
        return fields

    async def extract(self, receipt_paths: list[str]) -> dict[str, Any]:
        """
        Extract data from receipt documents.
        
        Sends all documents together so the model can cross-reference
        (e.g., outbound flight + return flight on separate receipts).
        Documents are labeled by name so the model knows which is which.
        
        Args:
            receipt_paths: Paths to receipt files (PDFs or images)
            
        Returns:
            Extraction result with fields and metadata
        """
        import io
        import logging
        logger = logging.getLogger(__name__)

        if settings.mock_extraction:
            logger.warning(
                "MOCK_EXTRACTION is on: returning dummy values after %.1fs, "
                "the vision model is NOT called",
                settings.mock_extraction_seconds,
            )
            await asyncio.sleep(settings.mock_extraction_seconds)
            return {"fields": self._mock_fields()}

        # Load extraction prompt
        prompt = self._load_extraction_prompt()
        
        # Convert all documents to images, tracking names
        all_images = []
        doc_listing = []
        image_index = 1
        
        for path in receipt_paths:
            doc_name = os.path.basename(path)
            if path.lower().endswith(".pdf"):
                from pdf2image import convert_from_path
                pdf_images = convert_from_path(path)
                start_idx = image_index
                for img in pdf_images:
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85)
                    all_images.append(self._resize_image(buffer.getvalue()))
                    image_index += 1
                end_idx = image_index - 1
                if start_idx == end_idx:
                    doc_listing.append(f"- Image {start_idx}: \"{doc_name}\"")
                else:
                    doc_listing.append(f"- Images {start_idx}-{end_idx}: \"{doc_name}\" ({end_idx - start_idx + 1} pages)")
            else:
                with open(path, "rb") as f:
                    all_images.append(self._resize_image(f.read()))
                doc_listing.append(f"- Image {image_index}: \"{doc_name}\"")
                image_index += 1
        
        doc_list_str = "\n".join(doc_listing)
        
        full_prompt = f"""You are given {len(all_images)} document images. These documents are related to the same trip/expense and may depend on each other for context (e.g., outbound and return flights on separate receipts).

DOCUMENTS PROVIDED:
{doc_list_str}

IMPORTANT: Look at ALL documents together to build a complete picture. Information from one document may complement another.

{prompt}"""
        
        logger.info(f"Sending {len(all_images)} images from {len(receipt_paths)} documents to vision model")
        
        response = await self.inference.chat_with_vision(
            prompt=full_prompt,
            images=all_images,
            system_prompt="You are an expert at extracting structured data from receipts and travel documents. Cross-reference all provided documents to extract the most complete and accurate information.",
        )
        
        content = response.get("message", {}).get("content", "")
        logger.info(f"Got extraction response: {len(content)} chars")
        
        fields = self._parse_extraction_response(content, "multiple documents")
        
        return {"fields": fields}

    def _parse_extraction_response(self, content: str, fallback_source: str = "unknown") -> list[dict]:
        """Parse extraction response from the model into a list of field dicts."""
        
        try:
            cleaned = content.strip()
            # Strip markdown code blocks
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # Find JSON in response
            json_start = cleaned.find('{')
            json_arr_start = cleaned.find('[')
            if json_arr_start >= 0 and (json_start < 0 or json_arr_start < json_start):
                json_end = cleaned.rfind(']') + 1
                extracted = json.loads(cleaned[json_arr_start:json_end])
            elif json_start >= 0:
                json_end = cleaned.rfind('}') + 1
                extracted = json.loads(cleaned[json_start:json_end])
            else:
                extracted = json.loads(cleaned)
        except json.JSONDecodeError as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to parse extraction response: {e}. Content: {content[:300]}")
            return []
        
        # Normalize to list of field dicts
        fields = []
        items = extracted
        
        if isinstance(extracted, dict):
            items = extracted.get("fields", extracted)
        
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    fields.append({
                        "field_name": item.get("field_name", "unknown"),
                        "value": str(item.get("value", "")) if item.get("value") is not None else "",
                        "source_document": item.get("source_document", fallback_source),
                        "bounding_box": item.get("bounding_box"),
                        "confidence": item.get("confidence", 0.5),
                        "reasoning": item.get("reasoning"),
                    })
        elif isinstance(items, dict):
            for field_name, data in items.items():
                if isinstance(data, dict):
                    fields.append({
                        "field_name": field_name,
                        "value": str(data.get("value", "")) if data.get("value") is not None else "",
                        "source_document": data.get("source_document", fallback_source),
                        "bounding_box": data.get("bounding_box"),
                        "confidence": data.get("confidence", 0.5),
                        "reasoning": data.get("reasoning"),
                    })
                else:
                    fields.append({
                        "field_name": field_name,
                        "value": str(data) if data else "",
                        "source_document": fallback_source,
                        "bounding_box": None,
                        "confidence": 0.5,
                        "reasoning": None,
                    })
        
        # Filter out fields with no value and no confidence
        fields = [f for f in fields if f["value"] or f["confidence"] > 0]

        # Carry the form's plain-language label, so the review screen can show
        # "Personnel number" instead of the raw PDF name "UHD".
        semantic_names = {
            field.get("field_name"): field.get("semantic_name")
            for field in self.config.get("fields", [])
        }
        for field in fields:
            field["semantic_name"] = semantic_names.get(field["field_name"])

        return fields
    
    async def fill_form(
        self,
        extracted_data: list[dict],
        verified_data: dict[str, str],
        kept_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Fill the PDF form with verified data.
        
        Args:
            extracted_data: Original extracted field data
            verified_data: User-verified/corrected field values
            kept_fields: When given, only these fields are filled. None keeps
                the previous behaviour of filling every extracted field.
            
        Returns:
            Result with path to filled PDF
        """
        # Load template path from config
        template_path = os.path.join(
            settings.templates_dir,
            self.client_name,
            "form_template.pdf"
        )
        
        if not os.path.exists(template_path):
            raise ValueError(f"Form template not found: {template_path}")
        
        # Merge extracted with verified (verified takes priority)
        form_data = {}
        
        # First, add extracted values
        for field in extracted_data:
            field_name = field["field_name"]
            form_data[field_name] = field.get("value", "")
        
        # Then, override with verified values
        for field_name, value in verified_data.items():
            form_data[field_name] = value
        
        # The traveller ticks the fields they need; anything unticked is dropped
        if kept_fields is not None:
            kept = set(kept_fields)
            form_data = {name: value for name, value in form_data.items() if name in kept}
        
        # Generate output path
        output_dir = os.path.join(settings.templates_dir, self.client_name, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"filled_form_{timestamp}.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        # Fill the PDF
        unmatched_fields = fill_form_fields(template_path, output_path, form_data)

        # A config whose field names no longer exist on the form would otherwise
        # produce a silently blank result.
        if unmatched_fields:
            logger.warning(
                "Filled %s: %d value(s) matched no field on the form: %s",
                self.client_name,
                len(unmatched_fields),
                ", ".join(unmatched_fields[:10]),
            )

        return {
            "filename": output_filename,
            "path": output_path,
            "unmatched_fields": unmatched_fields,
        }
    
    async def store_feedback(
        self,
        session_id: str,
        original: list[dict],
        corrected: dict[str, str],
        receipt_paths: list[str],
    ) -> None:
        """
        Store feedback for future model improvement.
        
        Captures corrections made by users during verification
        as training data for fine-tuning.
        
        Args:
            session_id: Unique session identifier
            original: Original extracted data
            corrected: User-corrected field values
            receipt_paths: Paths to the source receipts
        """
        feedback_dir = os.path.join(settings.feedback_dir, self.client_name)
        os.makedirs(feedback_dir, exist_ok=True)
        
        timestamp = datetime.now().isoformat()
        
        # Calculate which fields were corrected
        corrections = []
        for field in original:
            field_name = field["field_name"]
            original_value = field.get("value", "")
            corrected_value = corrected.get(field_name, original_value)
            
            if original_value != corrected_value:
                corrections.append({
                    "field_name": field_name,
                    "original_value": original_value,
                    "corrected_value": corrected_value,
                    "was_corrected": True,
                })
            else:
                corrections.append({
                    "field_name": field_name,
                    "value": original_value,
                    "was_corrected": False,
                })
        
        feedback_entry = {
            "session_id": session_id,
            "timestamp": timestamp,
            "client_name": self.client_name,
            "receipt_count": len(receipt_paths),
            "corrections": corrections,
            "correction_count": sum(1 for c in corrections if c.get("was_corrected")),
        }
        
        # Save feedback
        feedback_path = os.path.join(feedback_dir, f"{session_id}.json")
        with open(feedback_path, "w") as f:
            json.dump(feedback_entry, f, indent=2, ensure_ascii=False)
