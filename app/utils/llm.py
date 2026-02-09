"""
app/utils/llm.py
────────────────
LLM utility functions - connection checking, health status, model info.
"""

from __future__ import annotations
import httpx
import logging
from typing import Dict, Any, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Raised when cannot connect to Ollama."""
    pass


class ModelNotFoundError(Exception):
    """Raised when the configured model is not available."""
    pass


async def check_ollama_health() -> Dict[str, Any]:
    """
    Check if Ollama is running and the configured model is available.
    
    Returns:
        {
            "connected": bool,
            "model_available": bool,
            "model": str,
            "available_models": list[str],
            "error": str | None
        }
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            
            # Extract model names (without version tags)
            available_models = [
                m.get("name", "").split(":")[0] 
                for m in data.get("models", [])
            ]
            
            # Check if our configured model is available
            configured_model = settings.ollama.model
            model_available = (
                configured_model in available_models or
                any(configured_model in m for m in available_models)
            )
            
            return {
                "connected": True,
                "model_available": model_available,
                "model": configured_model,
                "available_models": available_models,
                "ollama_url": settings.ollama.base_url,
                "error": None if model_available else f"Model '{configured_model}' not found. Run: ollama pull {configured_model}"
            }
            
    except httpx.ConnectError:
        return {
            "connected": False,
            "model_available": False,
            "model": settings.ollama.model,
            "available_models": [],
            "ollama_url": settings.ollama.base_url,
            "error": f"Cannot connect to Ollama at {settings.ollama.base_url}. Run: ollama serve"
        }
    except Exception as e:
        return {
            "connected": False,
            "model_available": False,
            "model": settings.ollama.model,
            "available_models": [],
            "ollama_url": settings.ollama.base_url,
            "error": str(e)
        }


def check_ollama_health_sync() -> Dict[str, Any]:
    """Synchronous version of check_ollama_health."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{settings.ollama.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            
            available_models = [
                m.get("name", "").split(":")[0] 
                for m in data.get("models", [])
            ]
            
            configured_model = settings.ollama.model
            model_available = (
                configured_model in available_models or
                any(configured_model in m for m in available_models)
            )
            
            return {
                "connected": True,
                "model_available": model_available,
                "model": configured_model,
                "available_models": available_models,
                "ollama_url": settings.ollama.base_url,
                "error": None if model_available else f"Model '{configured_model}' not found"
            }
            
    except httpx.ConnectError:
        return {
            "connected": False,
            "model_available": False,
            "model": settings.ollama.model,
            "available_models": [],
            "ollama_url": settings.ollama.base_url,
            "error": f"Cannot connect to Ollama at {settings.ollama.base_url}"
        }
    except Exception as e:
        return {
            "connected": False,
            "model_available": False,
            "model": settings.ollama.model,
            "available_models": [],
            "ollama_url": settings.ollama.base_url,
            "error": str(e)
        }


def get_model_info() -> Dict[str, Any]:
    """Get information about the currently configured model."""
    return {
        "model": settings.ollama.model,
        "base_url": settings.ollama.base_url,
        "api_generate_url": f"{settings.ollama.base_url}/api/generate",
    }


def list_recommended_models() -> List[Dict[str, Any]]:
    """Get list of recommended models with their characteristics."""
    return [
        {
            "name": "mistral",
            "size": "4.1GB",
            "ram_required": "8GB",
            "speed": "fast",
            "quality": "good",
            "description": "Default. Best balance of speed and quality.",
            "command": "ollama pull mistral"
        },
        {
            "name": "llama3",
            "size": "4.7GB", 
            "ram_required": "8GB",
            "speed": "medium",
            "quality": "excellent",
            "description": "Newest LLaMA. Best quality for drafts.",
            "command": "ollama pull llama3"
        },
        {
            "name": "llama2",
            "size": "3.8GB",
            "ram_required": "8GB", 
            "speed": "fast",
            "quality": "good",
            "description": "Proven and reliable.",
            "command": "ollama pull llama2"
        },
        {
            "name": "phi3",
            "size": "2.2GB",
            "ram_required": "4GB",
            "speed": "very fast",
            "quality": "fair",
            "description": "Smallest. Good for testing on low-end machines.",
            "command": "ollama pull phi3"
        },
        {
            "name": "gemma",
            "size": "5.0GB",
            "ram_required": "8GB",
            "speed": "medium",
            "quality": "good",
            "description": "Google's model. Good alternative.",
            "command": "ollama pull gemma"
        },
        {
            "name": "mixtral",
            "size": "26GB",
            "ram_required": "32GB",
            "speed": "slow",
            "quality": "excellent",
            "description": "Best quality. Needs powerful machine.",
            "command": "ollama pull mixtral"
        },
    ]
