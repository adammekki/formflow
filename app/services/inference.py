"""
FormFlow - Inference Client

Unified client for communicating with inference providers (Ollama/vLLM).
Handles both text and vision model requests with streaming support.
"""

import base64
import httpx
import json
from pathlib import Path
from typing import Optional, AsyncGenerator
from app.config import get_settings

class InferenceClient:
    """Unified client for Ollama/vLLM inference"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.inference_base_url
        self.model = self.settings.inference_model
        self.timeout = httpx.Timeout(600.0, connect=30.0)  # 10 min timeout
    
    async def check_health(self) -> dict:
        """Check if inference server is healthy"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Check server is up
                response = await client.head(f"{self.base_url}")
                if response.status_code != 200:
                    return {"healthy": False, "error": "Server not responding"}
                
                # Check model is available
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    if any(self.model in name for name in model_names):
                        return {"healthy": True, "error": None}
                    return {"healthy": False, "error": f"Model {self.model} not found"}
                
                return {"healthy": False, "error": "Could not list models"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def chat_with_vision(
        self, 
        prompt: str, 
        images: list[bytes],
        system_prompt: Optional[str] = None
    ) -> dict:
        """Send a chat request with images to the vision model"""
        
        # Encode images to base64
        encoded_images = [base64.b64encode(img).decode('utf-8') for img in images]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({
            "role": "user",
            "content": prompt,
            "images": encoded_images
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 16384
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Inference request timed out after 10 minutes")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Inference request failed: {e.response.text}")
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> dict:
        """Send a text-only chat request"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 32768
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Inference request timed out after 10 minutes")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Inference request failed: {e.response.text}")


# Singleton instance
_client: Optional[InferenceClient] = None

def get_inference_client() -> InferenceClient:
    global _client
    if _client is None:
        _client = InferenceClient()
    return _client
