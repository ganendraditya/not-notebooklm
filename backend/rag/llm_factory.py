import inspect
import json
import logging
import os
import re
from typing import Any, Callable, Dict, Optional
from dotenv import load_dotenv

from llama_index.llms.openai_like import OpenAILike

try:
    from llama_index.llms.anthropic import Anthropic as LlamaAnthropic
except ImportError:
    LlamaAnthropic = None

load_dotenv()
logger = logging.getLogger("uvicorn.error")

_CACHED_MAIN_LLM = None
_CACHED_FAST_LLM = None
_CACHED_FALLBACK_LLM = None
_CACHED_CONFIG_HASH = None
_CACHED_SESSION_LLMS = {}


def _get_env_config_signature():
    """Generates a snapshot of active LLM environment variables to detect config changes."""
    return (
        os.getenv("LLM_BASE_URL", "") or os.getenv("NINEROUTER_BASE_URL", ""),
        os.getenv("LLM_API_KEY", "") or os.getenv("NINEROUTER_API_KEY", ""),
        os.getenv("LLM_MODEL", "") or os.getenv("NINEROUTER_MODEL", ""),
        os.getenv("LLM_FAST_MODEL", "") or os.getenv("NINEROUTER_FAST_MODEL", ""),
        os.getenv("LLM_FALLBACK_MODEL", "") or os.getenv("NINEROUTER_FALLBACK_MODEL", ""),
        os.getenv("LLM_TEMPERATURE", ""),
        os.getenv("LLM_PROFILES_JSON", ""),
        os.getenv("LLM_PRIMARY_PROFILE_ID", ""),
        os.getenv("LLM_FAST_PROFILE_ID", ""),
        os.getenv("LLM_FALLBACK_PROFILE_ID", ""),
    )


def _get_profile_by_id(profile_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolves specific gateway profile from LLM_PROFILES_JSON or synthesizes default profile."""
    raw_json = os.getenv("LLM_PROFILES_JSON", "").strip()
    if raw_json:
        try:
            profiles = json.loads(raw_json)
            if isinstance(profiles, list):
                for p in profiles:
                    if p.get("id") == profile_id:
                        return p
        except Exception as e:
            logger.warning(f"[LLM Factory] Error parsing LLM_PROFILES_JSON for profile {profile_id}: {e}")

    default_base_url = (
        os.getenv("LLM_BASE_URL", "").strip()
        or os.getenv("NINEROUTER_BASE_URL", "").strip()
        or "http://localhost:20128/v1"
    )
    default_api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()
    return {
        "id": "default",
        "name": "Default Gateway",
        "base_url": default_base_url,
        "api_key": default_api_key,
    }


def _resolve_tier_credentials(tier: str = "primary"):
    """
    Resolves OpenAI-compatible gateway credentials for a specific tier (primary, fast, fallback).
    Enables per-tier profile routing while maintaining 100% backwards compatibility with global LLM_BASE_URL.
    """
    profile_id_env = {
        "primary": "LLM_PRIMARY_PROFILE_ID",
        "fast": "LLM_FAST_PROFILE_ID",
        "fallback": "LLM_FALLBACK_PROFILE_ID",
    }.get(tier, "LLM_PRIMARY_PROFILE_ID")

    target_pid = os.getenv(profile_id_env, "default").strip() or "default"
    profile = _get_profile_by_id(target_pid) or _get_profile_by_id("default")

    base_url = profile.get("base_url", "").strip() if profile else ""
    if not base_url:
        base_url = (
            os.getenv("LLM_BASE_URL", "").strip()
            or os.getenv("NINEROUTER_BASE_URL", "").strip()
            or "http://localhost:20128/v1"
        )

    api_key = profile.get("api_key", "").strip() if profile else ""
    if not api_key:
        api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()

    model = (
        os.getenv("LLM_MODEL", "").strip()
        or os.getenv("NINEROUTER_MODEL", "").strip()
        or "gpt-4o"
    )
    fast_model = (
        os.getenv("LLM_FAST_MODEL", "").strip()
        or os.getenv("NINEROUTER_FAST_MODEL", "").strip()
        or model
    )
    fallback_model = (
        os.getenv("LLM_FALLBACK_MODEL", "").strip()
        or os.getenv("NINEROUTER_FALLBACK_MODEL", "").strip()
    )

    protocol = profile.get("protocol", "").strip().lower() if profile else ""
    if not protocol:
        # Auto-detect Anthropic protocol from URL or key prefix
        if "anthropic.com" in base_url.lower() or api_key.startswith("sk-ant-"):
            protocol = "anthropic"
        else:
            protocol = "openai"

    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1").strip())
    except (ValueError, TypeError):
        temperature = 0.1

    has_gateway = bool(api_key and not api_key.startswith("your_") and api_key != "dummy_key")
    return base_url, api_key, model, fast_model, fallback_model, temperature, has_gateway, protocol


def _get_gateway_credentials():
    """
    Resolves OpenAI-compatible LLM gateway credentials.
    Standardized vendor-neutral variables:
    - LLM_BASE_URL: OpenAI-compatible API endpoint URL
    - LLM_API_KEY: Secret API key / bearer token
    - LLM_MODEL: Primary model for heavy reasoning & document synthesis
    - LLM_FAST_MODEL: (Optional) Lightweight model for rapid micro-tasks (defaults to LLM_MODEL)
    - LLM_FALLBACK_MODEL: (Optional) Safety fallback model if primary fails
    - LLM_TEMPERATURE: Sampling temperature (defaults to 0.1 for natural generation, 0.0 for evaluation)
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

    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1").strip())
    except (ValueError, TypeError):
        temperature = 0.1

    has_gateway = bool(api_key and not api_key.startswith("your_") and api_key != "dummy_key")
    return base_url, api_key, model, fast_model, fallback_model, temperature, has_gateway


def clear_llm_cache():
    """Clears cached LLM instances, forcing fresh recreation on next query."""
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_FALLBACK_LLM, _CACHED_CONFIG_HASH, _CACHED_SESSION_LLMS
    _CACHED_MAIN_LLM = None
    _CACHED_FAST_LLM = None
    _CACHED_FALLBACK_LLM = None
    _CACHED_CONFIG_HASH = None
    _CACHED_SESSION_LLMS.clear()


def _create_llm_instance(
    protocol: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: float
) -> Optional[Any]:
    """
    Factory helper to instantiate either an OpenAI-compatible or direct Anthropic Claude LLM client.
    Handles protocol routing, token ceilings, and timeout contracts.
    """
    if protocol == "anthropic":
        if LlamaAnthropic is not None:
            try:
                # Direct Native Anthropic protocol
                return LlamaAnthropic(
                    model=model,
                    api_key=api_key,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
            except Exception as e:
                logger.warning(f"[LLM Factory] Failed to initialize native Anthropic LLM ({model}): {e}")
        else:
            logger.warning("[LLM Factory] llama-index-llms-anthropic not installed. Falling back to OpenAILike.")

    # Default: OpenAI-compatible protocol (OpenAI, DeepSeek, Grok, Ollama, 9Router, etc.)
    try:
        return OpenAILike(
            api_base=base_url,
            api_key=api_key,
            model=model,
            is_chat_model=True,
            is_function_calling_model=True,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as e:
        logger.warning(f"[LLM Factory] Failed to initialize OpenAILike LLM ({model}): {e}")
        return None


def get_main_llm(force_refresh: bool = False):
    """
    Returns the Primary / Heavy LLM.
    Powers reasoning-heavy tasks: multi-document synthesis, literature review, grounded citations.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_MAIN_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_MAIN_LLM

    base_url, api_key, model, fast_model, fallback_model, temperature, has_gateway, protocol = _resolve_tier_credentials("primary")

    _CACHED_MAIN_LLM = None
    if has_gateway:
        _CACHED_MAIN_LLM = _create_llm_instance(
            protocol=protocol,
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=16384,
            timeout=120.0,
        )

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_MAIN_LLM


def get_fast_llm(force_refresh: bool = False):
    """
    Returns the Fast / Lite LLM.
    Powers rapid micro-tasks: intent triage, query planning, paper relevance judging, auto title generation.
    Always creates an isolated fast agent instance with lean parameters (max_tokens=4096, timeout=45.0s).
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_FAST_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_FAST_LLM

    base_url, api_key, model, fast_model, fallback_model, temperature, has_gateway, protocol = _resolve_tier_credentials("fast")

    # Default to main model string if fast_model is empty, while maintaining isolated client profile
    target_fast_model = fast_model or model

    _CACHED_FAST_LLM = None
    if has_gateway and target_fast_model:
        _CACHED_FAST_LLM = _create_llm_instance(
            protocol=protocol,
            base_url=base_url,
            api_key=api_key,
            model=target_fast_model,
            temperature=temperature,
            max_tokens=4096,
            timeout=45.0,
        )

    if _CACHED_FAST_LLM is None:
        _CACHED_FAST_LLM = get_main_llm(force_refresh=force_refresh)

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_FAST_LLM


def get_fallback_llm(force_refresh: bool = False):
    """
    Returns the Fallback LLM instance (singleton, lazily created).
    Used as a safety net when both Primary and Fast models fail at runtime (rate limit, quota exhaustion).
    Validates configuration signature to prevent serving stale instances upon admin settings update.
    """
    global _CACHED_FALLBACK_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_FALLBACK_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_FALLBACK_LLM

    base_url, api_key, model, fast_model, fallback_model, temperature, has_gateway, protocol = _resolve_tier_credentials("fallback")
    if not has_gateway or not fallback_model:
        return None

    _CACHED_FALLBACK_LLM = _create_llm_instance(
        protocol=protocol,
        base_url=base_url,
        api_key=api_key,
        model=fallback_model,
        temperature=temperature,
        max_tokens=16384,
        timeout=120.0,
    )

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_FALLBACK_LLM


async def acall_fast_with_fallback(call_fn, *args, **kwargs):
    """
    Executes a fast LLM call with automatic cascade to fallback model on runtime errors.

    Usage:
        result = await acall_fast_with_fallback(
            lambda llm: llm.acomplete(prompt)
        )

    Cascade order: Fast LLM -> Fallback LLM -> raise original error.
    The callable `call_fn` receives a single LLM instance argument.
    """
    fast_inst = get_fast_llm()
    if fast_inst:
        try:
            return await call_fn(fast_inst)
        except Exception as fast_err:
            fast_model_name = getattr(fast_inst, "model", "fast")
            logger.warning(f"[LLM Fast Cascade] {fast_model_name} failed: {fast_err}")

            fb_inst = get_fallback_llm()
            if fb_inst and fb_inst is not fast_inst:
                fb_model_name = getattr(fb_inst, "model", "fallback")
                logger.info(f"[LLM Fast Cascade] -> Cascading fast task to {fb_model_name}...")
                try:
                    return await call_fn(fb_inst)
                except Exception as fb_err:
                    logger.warning(f"[LLM Fast Cascade] Fallback {fb_model_name} also failed: {fb_err}")
                    raise fast_err  # Raise original error for clearer diagnostics

            raise  # No fallback available, re-raise fast error

    raise RuntimeError("No LLM instance available for fast task")


def get_llm_factory(provider_override: Optional[str] = None, force_refresh: bool = False):
    """Singleton helper returning (main_llm, fast_llm)."""
    return get_main_llm(force_refresh=force_refresh), get_fast_llm(force_refresh=force_refresh)


def create_llm_instances(force_refresh: bool = False):
    """Backward compatibility helper returning (main_llm, fast_llm, None, None)."""
    main_llm, fast_llm = get_llm_factory(force_refresh=force_refresh)
    return main_llm, fast_llm, None, None


def get_custom_session_llm(model: str, profile_id: Optional[str] = None) -> Optional[Any]:
    """
    Instantiates or returns cached LLM for a specific session-bound model override.
    Resolves credentials from the specified profile_id or falls back to primary credentials.
    """
    global _CACHED_SESSION_LLMS
    if not model or not model.strip():
        return None

    target_model = model.strip()
    target_pid = (profile_id or "").strip() or os.getenv("LLM_PRIMARY_PROFILE_ID", "default").strip() or "default"
    profile = _get_profile_by_id(target_pid) or _get_profile_by_id("default")

    base_url = (profile.get("base_url", "").strip() if profile else "")
    if not base_url:
        base_url = (
            os.getenv("LLM_BASE_URL", "").strip()
            or os.getenv("NINEROUTER_BASE_URL", "").strip()
            or "http://localhost:20128/v1"
        )

    api_key = (profile.get("api_key", "").strip() if profile else "")
    if not api_key:
        api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()

    protocol = (profile.get("protocol", "").strip().lower() if profile else "")
    if not protocol:
        if "anthropic.com" in base_url.lower() or api_key.startswith("sk-ant-"):
            protocol = "anthropic"
        else:
            protocol = "openai"

    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1").strip())
    except (ValueError, TypeError):
        temperature = 0.1

    current_sig = _get_env_config_signature()
    global _CACHED_CONFIG_HASH, _CACHED_SESSION_LLMS
    if _CACHED_CONFIG_HASH != current_sig:
        _CACHED_SESSION_LLMS.clear()
        _CACHED_CONFIG_HASH = current_sig

    cache_key = (protocol, base_url, api_key, target_model, temperature)
    if cache_key in _CACHED_SESSION_LLMS:
        return _CACHED_SESSION_LLMS[cache_key]

    inst = _create_llm_instance(
        protocol=protocol,
        base_url=base_url,
        api_key=api_key,
        model=target_model,
        temperature=temperature,
        max_tokens=16384,
        timeout=120.0,
    )
    if inst:
        _CACHED_SESSION_LLMS[cache_key] = inst
    return inst


def get_candidate_llm_chain(
    model_override: Optional[str] = None,
    profile_id_override: Optional[str] = None
):
    """
    Builds prioritized list of candidate LLMs:
    1. Session Model (if model_override is provided)
    2. Primary LLM (LLM_MODEL)
    3. Fallback LLM (LLM_FALLBACK_MODEL, if configured and distinct)
    4. Fast LLM (LLM_FAST_MODEL, if distinct from Primary)
    """
    candidate_llms = []
    seen = set()

    def add_candidate(inst, label):
        if inst and id(inst) not in seen:
            candidate_llms.append((inst, label))
            seen.add(id(inst))

    if model_override and model_override.strip():
        session_inst = get_custom_session_llm(model=model_override, profile_id=profile_id_override)
        if session_inst:
            add_candidate(session_inst, f"Session Model ({model_override.strip()})")

    main_instance = get_main_llm()
    fast_instance = get_fast_llm()

    if main_instance:
        label = getattr(main_instance, "model", "default")
        add_candidate(main_instance, f"Primary Synthesizer ({label})")

    fb_inst = get_fallback_llm()
    if fb_inst:
        fb_label = getattr(fb_inst, "model", "fallback")
        add_candidate(fb_inst, f"Fallback Model ({fb_label})")

    if fast_instance:
        main_model_name = getattr(main_instance, "model", None)
        fast_model_name = getattr(fast_instance, "model", None)
        # Only add fast instance to fallback chain if it uses a distinct underlying model
        if fast_model_name and main_model_name and fast_model_name != main_model_name:
            add_candidate(fast_instance, f"Fast Lite ({fast_model_name})")

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
                    prev_len = len(full_content)
                    full_content += token
                    if in_hidden_metadata:
                        continue
                    m = re.search(r'<!--\s*(?:CITATION_MAP|SOURCES_DATA)', full_content, re.IGNORECASE)
                    if m:
                        in_hidden_metadata = True
                        comment_start = m.start()
                        if comment_start > prev_len:
                            visible_portion = full_content[prev_len:comment_start]
                            if visible_portion:
                                res = on_delta(visible_portion)
                                if inspect.isawaitable(res):
                                    await res
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
        visible_content = re.sub(r'<!--\s*(?:CITATION_MAP|SOURCES_DATA)[\s\S]*?(?:-->|$)', '', full_content).strip()
        res = on_delta(visible_content)
        if inspect.isawaitable(res):
            await res
    return full_content
