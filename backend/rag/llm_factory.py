import os
import asyncio
import inspect
import logging
from typing import Optional, List, Callable, Any
from dotenv import load_dotenv

from llama_index.llms.gemini import Gemini
from llama_index.llms.groq import Groq
from llama_index.llms.openai_like import OpenAILike

load_dotenv()
logger = logging.getLogger("uvicorn.error")

_CACHED_MAIN_LLM = None
_CACHED_FAST_LLM = None
_CACHED_CONFIG_HASH = None


def _get_env_config_signature():
    """Generates a snapshot of active LLM environment variables to detect config changes."""
    return (
        os.getenv("LLM_PROVIDER", ""),
        os.getenv("LLM_BASE_URL", ""),
        os.getenv("LLM_API_KEY", ""),
        os.getenv("LLM_MODEL", ""),
        os.getenv("LLM_FAST_MODEL", ""),
        os.getenv("LLM_FALLBACK_MODEL", ""),
        os.getenv("OPENAI_BASE_URL", ""),
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("OPENAI_MODEL", ""),
        os.getenv("NINEROUTER_BASE_URL", ""),
        os.getenv("NINEROUTER_API_KEY", ""),
        os.getenv("NINEROUTER_MODEL", ""),
        os.getenv("NINEROUTER_FAST_MODEL", ""),
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("GEMINI_MODEL", ""),
        os.getenv("GROQ_API_KEY", ""),
    )


def _get_gateway_credentials():
    """
    Resolves universal OpenAI-compatible gateway credentials.
    Supports LLM_*, OPENAI_*, and legacy NINEROUTER_* environment variable aliases.
    """
    api_key = (
        os.getenv("LLM_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("NINEROUTER_API_KEY", "").strip()
    )
    base_url = (
        os.getenv("LLM_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("NINEROUTER_BASE_URL", "").strip()
        or "http://localhost:20128/v1"
    )
    model = (
        os.getenv("LLM_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or os.getenv("NINEROUTER_MODEL", "").strip()
        or "gpt-4o"
    )
    fast_model = (
        os.getenv("LLM_FAST_MODEL", "").strip()
        or os.getenv("OPENAI_FAST_MODEL", "").strip()
        or os.getenv("NINEROUTER_FAST_MODEL", "").strip()
        or "gpt-4o-mini"
    )
    fallback_model = (
        os.getenv("LLM_FALLBACK_MODEL", "").strip()
        or os.getenv("OPENAI_FALLBACK_MODEL", "").strip()
        or os.getenv("NINEROUTER_FALLBACK_MODEL", "").strip()
    )
    has_gateway = bool(api_key and not api_key.startswith("your_") and api_key != "dummy_key")
    return base_url, api_key, model, fast_model, fallback_model, has_gateway


def clear_llm_cache():
    """Clears cached LLM instances, forcing fresh recreation on next query."""
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    _CACHED_MAIN_LLM = None
    _CACHED_FAST_LLM = None
    _CACHED_CONFIG_HASH = None


def get_main_llm(force_refresh: bool = False):
    """
    Returns the Primary / Heavy LLM.
    Priority:
    1. If LLM_PROVIDER is 'gemini' or Gateway not configured: Direct Gemini.
    2. Universal OpenAI-Compatible Gateway (OpenAI, OpenRouter, Ollama, vLLM, LMStudio, etc.).
    3. Direct Gemini Fallback.
    4. Direct Groq Fallback.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_MAIN_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_MAIN_LLM

    provider = os.getenv("LLM_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    has_gemini = bool(gemini_key and not gemini_key.startswith("your_"))

    base_url, api_key, model, fast_model, fallback_model, has_gateway = _get_gateway_credentials()

    groq_key = os.getenv("GROQ_API_KEY")
    has_groq = bool(groq_key and not groq_key.startswith("your_"))

    _CACHED_MAIN_LLM = None

    # Priority 1: Gemini if explicitly selected or if gateway not configured
    if (provider == "gemini" or not has_gateway) and has_gemini:
        try:
            _CACHED_MAIN_LLM = Gemini(
                model=os.getenv("GEMINI_MODEL", "models/gemini-3.7-flash"),
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Gemini init failed: {e}")

    # Priority 2: Universal Gateway (OpenAI-compatible)
    if _CACHED_MAIN_LLM is None and has_gateway:
        try:
            _CACHED_MAIN_LLM = OpenAILike(
                api_base=base_url,
                api_key=api_key,
                model=model,
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=8192,
                timeout=120.0
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Universal Gateway init failed: {e}")

    # Priority 3: Groq fallback
    if _CACHED_MAIN_LLM is None and has_groq:
        try:
            _CACHED_MAIN_LLM = Groq(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                api_key=groq_key,
                max_tokens=8192
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Groq init failed: {e}")

    # Final fallback if provider was not gemini but gemini is available
    if _CACHED_MAIN_LLM is None and has_gemini:
        try:
            _CACHED_MAIN_LLM = Gemini(
                model=os.getenv("GEMINI_MODEL", "models/gemini-3.7-flash"),
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Final Gemini fallback failed: {e}")

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_MAIN_LLM


def get_fast_llm(force_refresh: bool = False):
    """
    Returns the Fast / Lite LLM.
    Used for rapid micro-tasks: intent classification, query planning, paper judging, title generation, and rubric checks.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_FAST_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_FAST_LLM

    provider = os.getenv("LLM_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    has_gemini = bool(gemini_key and not gemini_key.startswith("your_"))

    base_url, api_key, model, fast_model, fallback_model, has_gateway = _get_gateway_credentials()

    groq_key = os.getenv("GROQ_API_KEY")
    has_groq = bool(groq_key and not groq_key.startswith("your_"))

    _CACHED_FAST_LLM = None

    if (provider == "gemini" or not has_gateway) and has_gemini:
        try:
            _CACHED_FAST_LLM = Gemini(
                model=os.getenv("GEMINI_FAST_MODEL", "models/gemini-3.5-flash-lite"),
                api_key=gemini_key,
                max_tokens=4096
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Fast Gemini init failed: {e}")

    if _CACHED_FAST_LLM is None and has_gateway:
        try:
            _CACHED_FAST_LLM = OpenAILike(
                api_base=base_url,
                api_key=api_key,
                model=fast_model,
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=4096,
                timeout=45.0
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Fast Universal Gateway init failed: {e}")

    if _CACHED_FAST_LLM is None and has_groq:
        try:
            _CACHED_FAST_LLM = Groq(
                model=os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant"),
                api_key=groq_key,
                max_tokens=4096
            )
        except Exception as e:
            logger.warning(f"[LLM Factory] Fast Groq init failed: {e}")

    if _CACHED_FAST_LLM is None:
        _CACHED_FAST_LLM = get_main_llm(force_refresh=force_refresh)

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_FAST_LLM


def get_llm_factory(provider_override: Optional[str] = None, force_refresh: bool = False):
    """Singleton helper returning (main_llm, fast_llm)."""
    return get_main_llm(force_refresh=force_refresh), get_fast_llm(force_refresh=force_refresh)


def create_llm_instances(force_refresh: bool = False):
    """Backward compatibility helper returning (main_llm, fast_llm, None, None)."""
    main_llm, fast_llm = get_llm_factory(force_refresh=force_refresh)
    return main_llm, fast_llm, None, None


def get_candidate_llm_chain():
    """Builds prioritized list of candidate LLMs (Main Synthesizer with cascading fallback)."""
    candidate_llms = []
    seen = set()

    def add_candidate(inst, label):
        if inst and id(inst) not in seen:
            candidate_llms.append((inst, label))
            seen.add(id(inst))

    main_instance = get_main_llm()
    fast_instance = get_fast_llm()

    if main_instance:
        label = getattr(main_instance, "model", "default")
        add_candidate(main_instance, f"Primary Synthesizer ({label})")

    # Universal Gateway Fallback Candidate
    base_url, api_key, model, fast_model, fallback_model, has_gateway = _get_gateway_credentials()
    if has_gateway and fallback_model:
        try:
            fb_inst = OpenAILike(
                api_base=base_url,
                api_key=api_key,
                model=fallback_model,
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=8192,
                timeout=120.0
            )
            add_candidate(fb_inst, f"Gateway Fallback ({fallback_model})")
        except Exception as e:
            logger.debug(f"[LLM Factory] Gateway Fallback init error: {e}")

    if fast_instance and fast_instance != main_instance:
        label = getattr(fast_instance, "model", "default")
        add_candidate(fast_instance, f"Fast Lite ({label})")

    # Direct Gemini fallback
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-3.7-flash")
            g_inst = Gemini(model=gemini_model, api_key=gemini_key, max_tokens=8192)
            add_candidate(g_inst, f"Direct Gemini Fallback ({gemini_model})")
        except Exception as e:
            logger.debug(f"[LLM Factory] Gemini Fallback init error: {e}")

    # Direct Groq fallback
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and not groq_key.startswith("your_"):
        try:
            gq_inst = Groq(model="llama-3.3-70b-versatile", api_key=groq_key)
            add_candidate(gq_inst, "Direct Groq Fallback")
        except Exception as e:
            logger.debug(f"[LLM Factory] Groq Fallback init error: {e}")

    return candidate_llms


async def astream_llm_response(
    target_llm: Any,
    chat_msgs: list,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """
    Executes an LLM chat request with progressive token streaming if on_delta is provided.
    Falls back gracefully to standard achat if astream_chat fails or is unsupported.
    """
    if on_delta and hasattr(target_llm, "astream_chat"):
        try:
            response_stream = await target_llm.astream_chat(chat_msgs)
            full_content = ""
            async for chunk in response_stream:
                token = chunk.delta or ""
                if token:
                    full_content += token
                    res = on_delta(token)
                    if inspect.isawaitable(res):
                        await res
            if full_content:
                return full_content
        except Exception as e:
            logger.warning(f"[LLM Factory] astream_chat error ({e}), falling back to achat")

    resp = await target_llm.achat(chat_msgs)
    full_content = resp.message.content or ""
    if on_delta and full_content:
        res = on_delta(full_content)
        if inspect.isawaitable(res):
            await res
    return full_content
