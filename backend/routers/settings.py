import os
import re
from fastapi import APIRouter
from dotenv import load_dotenv, set_key

import rag

router = APIRouter(tags=["settings"])

@router.get("/llm/models")
def get_llm_models():
    """Returns available LLM providers and models configured in .env."""
    load_dotenv(override=True)
    current_provider = os.getenv("LLM_PROVIDER", "freellmapi").lower()
    
    models_list = [
        {
            "id": "freellmapi",
            "name": "Local LLM Proxy (100% Free / Unlimited)",
            "provider": "freellmapi",
            "model_name": os.getenv("FREELLMAPI_MODEL", "gpt-oss-120b"),
            "description": "Fast local proxy gateway (gpt-oss-120b, claude-sonnet-4-6, qwen-2.5-coder)",
            "active": current_provider == "freellmapi"
        },
        {
            "id": "9router",
            "name": "9Router High-End AI (Fast & Stable)",
            "provider": "9router",
            "model_name": os.getenv("NINEROUTER_MODEL", "ag/claude-sonnet-4-6"),
            "description": "Premium multi-model router via 9Router proxy gateway",
            "active": current_provider == "9router"
        },
        {
            "id": "gemini",
            "name": "Google Gemini 2.5 Flash",
            "provider": "gemini",
            "model_name": "gemini-flash-latest",
            "description": "Fast official Gemini Flash API",
            "active": current_provider == "gemini"
        },
        {
            "id": "groq",
            "name": "Groq Qwen 2.5 32B (Ultra Fast)",
            "provider": "groq",
            "model_name": "qwen/qwen-2.5-32b",
            "description": "High-speed Groq LPUs for rapid response generation",
            "active": current_provider == "groq"
        }
    ]
    
    return {
        "current_provider": current_provider,
        "models": models_list
    }

@router.post("/llm/select")
def select_llm_model(payload: dict):
    """Dynamically switches active LLM provider and model across the application."""
    provider = payload.get("provider")
    model_name = payload.get("model_name")
    
    if not provider:
        return {"status": "error", "message": "Provider is required"}
        
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    
    try:
        set_key(env_path, "LLM_PROVIDER", provider)
        if provider == "freellmapi" and model_name:
            set_key(env_path, "FREELLMAPI_MODEL", model_name)
        elif provider == "9router" and model_name:
            set_key(env_path, "NINEROUTER_MODEL", model_name)
            
        load_dotenv(env_path, override=True)
        rag.ninerouter_llm, rag.freellm_llm, rag.gemini_llm, rag.groq_llm = rag.create_llm_instances()
        
        return {
            "status": "success",
            "message": f"Successfully switched to {provider} ({model_name or 'default'})",
            "current_provider": provider,
            "model_name": model_name
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
