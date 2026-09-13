import os
import asyncio
import inspect
import logging
from typing import Optional, List, Callable, Any
from dotenv import load_dotenv

from llama_index.llms.openai_like import OpenAILike

load_dotenv()
logger = logging.getLogger("uvicorn.error")

_CACHED_MAIN_LLM = None
_CACHED_FAST_LLM = None
_CACHED_CONFIG_HASH = None


def _get_env_config_signature():
    """Generates a snapshot of active LLM environment variables to detect config changes."""
    return (
        os.getenv("LLM_BASE_URL", "") or os.getenv("NINEROUTER_BASE_URL", ""),
        os.getenv("LLM_API_KEY", "") or os.getenv("NINEROUTER_API_KEY", ""),
        os.getenv("LLM_MODEL", "") or os.getenv("NINEROUTER_MODEL", ""),
        os.getenv("LLM_FAST_MODEL", "") or os.getenv("NINEROUTER_FAST_MODEL", ""),
        os.getenv("LLM_FALLBACK_MODEL", "") or os.getenv("NINEROUTER_FALLBACK_MODEL", ""),
    )


def _get_gateway_credentials():
    """
    Resolves OpenAI-compatible LLM gateway credentials.
    Standardized vendor-neutral variables:
    - LLM_BASE_URL: OpenAI-compatible API endpoint URL
    - LLM_API_KEY: Secret API key / bearer token
    - LLM_MODEL: Primary model for heavy reasoning & document synthesis
    - LLM_FAST_MODEL: (Optional) Lightweight model for rapid micro-tasks (defaults to LLM_MODEL)
    - LLM_FALLBACK_MODEL: (Optional) Safety fallback model if primary fails
    Also supports backward-compatible NINEROUTER_* configuration variables.
    """
    api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()
    base_url = (
        os.getenv("LLM_BASE_URL", "").strip()
        or os.getenv("NINEROUTER_BASE_URL", "").strip()
        or "http://localhost:20128/v1"
    )
    model = (
        os.getenv("LLM_MODEL", "").strip()
        or os.getenv("NINEROUTER_MODEL", "").strip()
        or "gpt-4o"
    )

    # If fast_model is not explicitly set, gracefully default to main model (supports 1-model setups)
    fast_model = (
        os.getenv("LLM_FAST_MODEL", "").strip()
        or os.getenv("NINEROUTER_FAST_MODEL", "").strip()
        or model
    )
    fallback_model = (
        os.getenv("LLM_FALLBACK_MODEL", "").strip()
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
    Powers reasoning-heavy tasks: multi-document synthesis, literature review, grounded citations.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_MAIN_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_MAIN_LLM

    base_url, api_key, model, fast_model, fallback_model, has_gateway = _get_gateway_credentials()

    _CACHED_MAIN_LLM = None
    if has_gateway:
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
            logger.warning(f"[LLM Factory] Failed to initialize Primary LLM ({model}): {e}")

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_MAIN_LLM


def get_fast_llm(force_refresh: bool = False):
    """
    Returns the Fast / Lite LLM.
    Powers rapid micro-tasks: intent triage, query planning, paper relevance judging, auto title generation.
    If LLM_FAST_MODEL is identical to LLM_MODEL or not configured, reuses the Primary LLM instance.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_FAST_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_FAST_LLM

    base_url, api_key, model, fast_model, fallback_model, has_gateway = _get_gateway_credentials()

    # Re-use main instance directly if models are identical
    if fast_model == model:
        _CACHED_FAST_LLM = get_main_llm(force_refresh=force_refresh)
        _CACHED_CONFIG_HASH = current_sig
        return _CACHED_FAST_LLM

    _CACHED_FAST_LLM = None
    if has_gateway:
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
            logger.warning(f"[LLM Factory] Failed to initialize Fast LLM ({fast_model}): {e}")

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
    """
    Builds prioritized list of candidate LLMs:
    1. Primary LLM (LLM_MODEL)
    2. Fallback LLM (LLM_FALLBACK_MODEL, if configured and distinct)
    3. Fast LLM (LLM_FAST_MODEL, if distinct from Primary)
    """
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

    base_url, api_key, model, fast_model, fallback_model, has_gateway = _get_gateway_credentials()
    if has_gateway and fallback_model and fallback_model != model:
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
            add_candidate(fb_inst, f"Fallback Model ({fallback_model})")
        except Exception as e:
            logger.debug(f"[LLM Factory] Fallback model init error: {e}")

    if fast_instance and fast_instance != main_instance:
        label = getattr(fast_instance, "model", "default")
        add_candidate(fast_instance, f"Fast Lite ({label})")

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
            in_hidden_metadata = False
            async for chunk in response_stream:
                token = chunk.delta or ""
                if token:
                    full_content += token
                    if in_hidden_metadata:
                        continue
                    if re.search(r'<!--\s*(?:CITATION_MAP|SOURCES_DATA)', full_content, re.IGNORECASE):
                        in_hidden_metadata = True
                        continue
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
        import re
        visible_content = re.sub(r'<!--\s*(?:CITATION_MAP|SOURCES_DATA)[\s\S]*?(?:-->|$)', '', full_content).strip()
        res = on_delta(visible_content)
        if inspect.isawaitable(res):
            await res
    return full_content
