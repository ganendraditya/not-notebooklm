"""
Token Budgeting, Context Window Registry, and Priority Waterfall Manager.

References & Empirical Foundations:
- Liu et al. (Stanford, TACL 2024): 'Lost in the Middle: How Language Models Use Long Contexts'
  (U-shaped curve, compact high-precision RAG chunks preferred over bloated contexts).
- LlamaIndex 'PromptHelper' & LangChain 'ConversationSummaryBufferMemory' architecture.
- Karpukhin et al. (EMNLP 2020): Dense Passage Retrieval bounds.
"""

import os
import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
import inspect

from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

logger = logging.getLogger("uvicorn.error")

# Cached tiktoken encodings
_ENCODING_CACHE: Dict[str, Any] = {}

# Known model context windows (in tokens)
KNOWN_MODEL_CONTEXT_WINDOWS: List[Tuple[re.Pattern, int]] = [
    # Gemini (1M to 2M tokens)
    (re.compile(r"gemini-(?:1\.5|2\.0|pro|flash)", re.I), 1_000_000),
    (re.compile(r"gemini", re.I), 1_000_000),
    
    # Claude 3 & 3.5 (200k tokens)
    (re.compile(r"claude-3(?:-5)?-(?:sonnet|haiku|opus)", re.I), 200_000),
    (re.compile(r"claude-3", re.I), 200_000),
    (re.compile(r"claude-2", re.I), 100_000),
    
    # OpenAI GPT-4o, GPT-4-turbo, o1, o3 (128k to 200k tokens)
    (re.compile(r"o[13](?:-mini)?", re.I), 200_000),
    (re.compile(r"gpt-4o(?:-mini)?", re.I), 128_000),
    (re.compile(r"gpt-4-turbo", re.I), 128_000),
    (re.compile(r"gpt-4-(?:32k)", re.I), 32_768),
    (re.compile(r"gpt-4", re.I), 8_192),
    (re.compile(r"gpt-3\.5-turbo-16k", re.I), 16_385),
    (re.compile(r"gpt-3\.5-turbo", re.I), 16_385),
    
    # Meta Llama Family
    (re.compile(r"llama-3\.[123]", re.I), 128_000),
    (re.compile(r"llama-3-(?:8b|70b)", re.I), 8_192),
    (re.compile(r"llama-?3", re.I), 8_192),
    (re.compile(r"llama-?2", re.I), 4_096),
    
    # Qwen Family
    (re.compile(r"qwen-?2\.5", re.I), 128_000),
    (re.compile(r"qwen-?2", re.I), 32_768),
    (re.compile(r"qwen", re.I), 32_768),
    
    # Mistral Family
    (re.compile(r"mistral-large", re.I), 128_000),
    (re.compile(r"mistral-(?:small|nemo|medium)", re.I), 32_768),
    (re.compile(r"mixtral-(?:8x7b|8x22b)", re.I), 32_768),
    (re.compile(r"mistral", re.I), 32_768),
    
    # DeepSeek Family
    (re.compile(r"deepseek-(?:chat|coder|v3|r1)", re.I), 64_000),
    (re.compile(r"deepseek", re.I), 64_000),
]

# Default conservative fallback context window when model name is unlisted or custom
DEFAULT_CONTEXT_WINDOW: int = 32_768
CONSERVATIVE_MIN_WINDOW: int = 8_192

# High-density RAG boundaries based on Stanford "Lost in the Middle"
TARGET_RAG_TOKENS_LARGE: int = 6_000
TARGET_RAG_TOKENS_MEDIUM: int = 4_000
TARGET_RAG_TOKENS_SMALL: int = 2_200

# Guaranteed generation reserve
DEFAULT_OUTPUT_RESERVE: int = 4_096
MIN_OUTPUT_RESERVE: int = 2_048
SAFETY_PADDING_TOKENS: int = 150


def get_tokenizer(model_name: Optional[str] = None):
    """Retrieves or caches a tiktoken encoding appropriate for the model."""
    encoding_key = "cl100k_base"
    if model_name:
        m_lower = model_name.lower()
        if "gpt-4o" in m_lower or "o1" in m_lower or "o3" in m_lower:
            encoding_key = "o200k_base"
            
    if encoding_key in _ENCODING_CACHE:
        return _ENCODING_CACHE[encoding_key]
        
    try:
        import tiktoken
        try:
            enc = tiktoken.get_encoding(encoding_key)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        _ENCODING_CACHE[encoding_key] = enc
        return enc
    except Exception as e:
        logger.warning(f"[TokenBudget] tiktoken unavailable or failed to load encoding ({e}); using character fallback.")
        return None


def count_tokens(text: Optional[str], model_name: Optional[str] = None) -> int:
    """Accurately counts tokens in text using tiktoken with robust character fallback."""
    if not text:
        return 0
    enc = get_tokenizer(model_name)
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Fallback: average 1 token ~= 4 characters in English, ~2.5 chars in Indonesian/code
    return max(1, int(len(text) / 3.5))


def count_messages_tokens(messages: List[Any], model_name: Optional[str] = None) -> int:
    """Counts tokens across structured chat messages (LlamaChatMessage or dicts)."""
    if not messages:
        return 0
    total = 0
    for msg in messages:
        content = ""
        if hasattr(msg, "content"):
            content = str(msg.content or "")
        elif isinstance(msg, dict):
            content = str(msg.get("content") or "")
        # Add 4 tokens per message for standard chat formatting wrappers (<|start|>, role, etc.)
        total += count_tokens(content, model_name=model_name) + 4
    return total + 3  # Conversation wrapper priming tokens


def get_model_context_window(model_name: Optional[str] = None) -> int:
    """
    Resolves the maximum context window for a given model.
    Honors LLM_CONTEXT_WINDOW environment variable if explicitly configured.
    """
    env_override = os.getenv("LLM_CONTEXT_WINDOW", "").strip()
    if env_override.isdigit():
        val = int(env_override)
        if val > 0:
            return val

    name_to_check = (model_name or os.getenv("LLM_MODEL") or os.getenv("NINEROUTER_MODEL") or "").strip()
    if not name_to_check:
        return DEFAULT_CONTEXT_WINDOW

    for pattern, window in KNOWN_MODEL_CONTEXT_WINDOWS:
        if pattern.search(name_to_check):
            return window

    return DEFAULT_CONTEXT_WINDOW


@dataclass
class TokenBudget:
    """Priority-based token allocation breakdown."""
    max_context: int
    reserved_output: int
    system_prompt_tokens: int
    query_tokens: int
    safety_padding: int
    max_rag_tokens: int
    max_history_tokens: int
    available_pool: int

    @property
    def total_prompt_budget(self) -> int:
        """Total allowed input prompt tokens before output generation begins."""
        return self.max_context - self.reserved_output - self.safety_padding


def allocate_token_budget(
    model_name: Optional[str] = None,
    system_prompt: str = "",
    user_query: str = "",
    reserved_output: Optional[int] = None,
    safety_padding: int = SAFETY_PADDING_TOKENS,
) -> TokenBudget:
    """
    Executes the Priority-Based Token Waterfall:
    1. Tier 1 (Non-Negotiable): Output buffer, system instructions, user query, padding.
    2. Tier 2 (High-Density RAG): Sized specifically to prevent Stanford 'Lost in the Middle'.
    3. Tier 3 (History): Remaining headroom assigned for conversation turns.
    """
    max_context = get_model_context_window(model_name)

    # 1. Output Reserve (Guaranteed generation space)
    if reserved_output is not None and reserved_output > 0:
        actual_output_reserve = reserved_output
    else:
        if max_context <= CONSERVATIVE_MIN_WINDOW:
            actual_output_reserve = MIN_OUTPUT_RESERVE  # 2048 for 8k models
        else:
            actual_output_reserve = DEFAULT_OUTPUT_RESERVE  # 4096

    # 2. System prompt and query
    sys_tokens = count_tokens(system_prompt, model_name=model_name)
    query_tokens = count_tokens(user_query, model_name=model_name)

    # 3. Available dynamic pool
    tier1_reserved = actual_output_reserve + sys_tokens + query_tokens + safety_padding
    available_pool = max(0, max_context - tier1_reserved)

    # 4. RAG Allocation (Tier 2) based on Stanford "Lost in the Middle" bounds
    if max_context <= CONSERVATIVE_MIN_WINDOW:
        # 8k model: keep RAG compact
        rag_target = min(TARGET_RAG_TOKENS_SMALL, int(available_pool * 0.55))
    elif max_context <= 32_768:
        # 32k model: optimal dense retrieval
        rag_target = min(TARGET_RAG_TOKENS_MEDIUM, int(available_pool * 0.40))
    else:
        # 64k - 1M+ model: cap RAG at high-density bounds (4k - 6k) to maintain sharp attention
        rag_target = TARGET_RAG_TOKENS_LARGE

    actual_rag_tokens = min(rag_target, available_pool)

    # 5. History Allocation (Tier 3)
    remaining_for_history = max(0, available_pool - actual_rag_tokens)
    
    # Cap history so prompt isn't needlessly filled if history isn't needed
    if max_context <= CONSERVATIVE_MIN_WINDOW:
        actual_history_tokens = min(2_500, remaining_for_history)
    elif max_context <= 32_768:
        actual_history_tokens = min(12_000, remaining_for_history)
    else:
        actual_history_tokens = min(40_000, remaining_for_history)

    return TokenBudget(
        max_context=max_context,
        reserved_output=actual_output_reserve,
        system_prompt_tokens=sys_tokens,
        query_tokens=query_tokens,
        safety_padding=safety_padding,
        max_rag_tokens=actual_rag_tokens,
        max_history_tokens=actual_history_tokens,
        available_pool=available_pool,
    )


def pack_text_into_token_budget(
    text: str,
    budget_tokens: int,
    model_name: Optional[str] = None,
    truncate_from: str = "end"
) -> str:
    """
    Packs a text block into the exact token budget without partial sentence cuts if possible.
    If text fits completely within budget, returns as-is.
    """
    if not text or budget_tokens <= 0:
        return ""
        
    actual_tokens = count_tokens(text, model_name=model_name)
    if actual_tokens <= budget_tokens:
        return text

    enc = get_tokenizer(model_name)
    if enc is not None:
        try:
            tokens = enc.encode(text, disallowed_special=())
            if truncate_from == "end":
                sliced = tokens[:budget_tokens]
            else:
                sliced = tokens[-budget_tokens:]
            decoded = enc.decode(sliced)
            
            # Clean up potential split sentence boundary
            if truncate_from == "end":
                last_period = max(decoded.rfind(".\n"), decoded.rfind(". "), decoded.rfind("?\n"), decoded.rfind("!\n"))
                if last_period > len(decoded) * 0.75:
                    decoded = decoded[:last_period + 1]
            return decoded
        except Exception:
            pass

    # Character fallback (approx 3.5 chars/token)
    char_limit = int(budget_tokens * 3.5)
    if truncate_from == "end":
        return text[:char_limit]
    return text[-char_limit:]


def extract_concise_history_digest(messages: List[LlamaChatMessage]) -> str:
    """Extracts a concise extractive digest of messages for deterministic fallback summary."""
    user_topics = []
    for m in messages:
        if hasattr(m, "role") and m.role == MessageRole.USER:
            txt = str(m.content or "").strip().split("\n")[0]
            if txt and len(txt) > 5 and not txt.startswith("[Context"):
                user_topics.append(txt[:80])
    if user_topics:
        # Keep up to 4 most distinct early topic queries
        return "Earlier discussion topics covered: " + "; ".join(user_topics[:4]) + "."
    return "Earlier dialogue covered preliminary research inquiries and introductory context."


def compact_chat_history(
    messages: List[LlamaChatMessage],
    max_history_tokens: int,
    model_name: Optional[str] = None,
    summary_text: Optional[str] = None
) -> List[LlamaChatMessage]:
    """
    Synchronous Smart History Compaction Protocol:
    1. Checks if message tokens exceed max_history_tokens. If not, returns unchanged.
    2. Identifies partition point to retain recent conversation turns.
    3. Evicted older turns are NEVER dropped naively; they are synthesized into a rolling summary bridge.
    4. Prepends the rolling summary bridge as a System message before retained turns.
    5. Strictly verifies and enforces total token sum <= max_history_tokens.
    """
    if not messages or max_history_tokens <= 0:
        return []

    current_tokens = count_messages_tokens(messages, model_name=model_name)
    if current_tokens <= max_history_tokens:
        return messages

    # Estimate bridge message token cost (~40-60 tokens)
    bridge_reserve = min(60, max(25, int(max_history_tokens * 0.25)))
    target_recent_budget = max(20, max_history_tokens - bridge_reserve)

    retained_messages = []
    accumulated_recent = 0
    cutoff_idx = len(messages)

    for idx in range(len(messages) - 1, -1, -1):
        m = messages[idx]
        m_tokens = count_tokens(str(m.content or ""), model_name=model_name) + 4
        if accumulated_recent + m_tokens > target_recent_budget and len(retained_messages) >= 1:
            cutoff_idx = idx + 1
            break
        retained_messages.insert(0, m)
        accumulated_recent += m_tokens
        cutoff_idx = idx

    evicted_messages = messages[:cutoff_idx]
    if not evicted_messages:
        return retained_messages

    active_summary = summary_text or extract_concise_history_digest(evicted_messages)
    bridge_message = LlamaChatMessage(
        role=MessageRole.SYSTEM,
        content=f"[Context Summary of Earlier Conversation: {active_summary}]"
    )

    result = [bridge_message] + retained_messages
    # Strictly enforce total token budget constraint
    while len(result) > 2 and count_messages_tokens(result, model_name=model_name) > max_history_tokens:
        result.pop(1)

    return result


async def acompact_chat_history(
    messages: List[LlamaChatMessage],
    max_history_tokens: int,
    model_name: Optional[str] = None,
    summarizer_func: Optional[Callable[[str], Any]] = None
) -> List[LlamaChatMessage]:
    """
    Asynchronous Smart History Compaction Protocol with optional LLM summary generation.
    """
    if not messages or max_history_tokens <= 0:
        return []

    current_tokens = count_messages_tokens(messages, model_name=model_name)
    if current_tokens <= max_history_tokens:
        return messages

    bridge_reserve = min(60, max(25, int(max_history_tokens * 0.25)))
    target_recent_budget = max(20, max_history_tokens - bridge_reserve)

    retained_messages = []
    accumulated_recent = 0
    cutoff_idx = len(messages)

    for idx in range(len(messages) - 1, -1, -1):
        m = messages[idx]
        m_tokens = count_tokens(str(m.content or ""), model_name=model_name) + 4
        if accumulated_recent + m_tokens > target_recent_budget and len(retained_messages) >= 1:
            cutoff_idx = idx + 1
            break
        retained_messages.insert(0, m)
        accumulated_recent += m_tokens
        cutoff_idx = idx

    evicted_messages = messages[:cutoff_idx]
    summary_text = None
    if summarizer_func is not None and evicted_messages:
        try:
            evicted_text = "\n".join([f"{m.role.value if hasattr(m.role, 'value') else m.role}: {m.content}" for m in evicted_messages])
            res = summarizer_func(evicted_text)
            if inspect.isawaitable(res):
                res = await res
            if res and isinstance(res, str) and len(res.strip()) > 10:
                summary_text = res.strip()
        except Exception as e:
            logger.debug(f"[Compaction Summary Warning]: {e}")

    return compact_chat_history(
        messages=messages,
        max_history_tokens=max_history_tokens,
        model_name=model_name,
        summary_text=summary_text
    )
