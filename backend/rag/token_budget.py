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


# In-memory registry for dynamically discovered model context windows (via API metadata or Error 400 auto-healing)
DISCOVERED_CONTEXT_WINDOWS: Dict[str, int] = {}


def record_discovered_context_window(model_name: str, context_window: int):
    """Registers a dynamically discovered context window for a model name."""
    if model_name and context_window > 0:
        DISCOVERED_CONTEXT_WINDOWS[model_name.strip().lower()] = context_window
        logger.info(f"[TokenBudget] Dynamically registered context window for '{model_name}': {context_window} tokens.")


def extract_context_window_from_error(error_message: str) -> Optional[int]:
    """
    Extracts the exact model context window limit from provider error messages.
    Supports OpenAI, Groq, Anthropic, vLLM, Ollama, and HuggingFace error patterns.
    """
    if not error_message:
        return None

    patterns = [
        # "This model's maximum context length is 16384 tokens. However, your messages resulted in..."
        re.compile(r"maximum context length is (\d+) tokens", re.I),
        # "context length of 8192 tokens exceeded"
        re.compile(r"context length of (\d+) tokens", re.I),
        # "maximum prompt length is 4096"
        re.compile(r"maximum prompt length is (\d+)", re.I),
        # "max_position_embeddings is 32768"
        re.compile(r"max_position_embeddings\s*(?:is|=)\s*(\d+)", re.I),
        # "context window of (\d+) tokens"
        re.compile(r"context window (?:is|of)?\s*(\d+)", re.I),
        # "model context limit: 8192"
        re.compile(r"model(?:'s)?\s*context\s*limit\s*(?:is|:)?\s*(\d+)", re.I),
        # "cannot exceed (\d+) tokens"
        re.compile(r"cannot exceed (\d+) tokens", re.I),
        # "requested X tokens, but maximum is Y"
        re.compile(r"(?:maximum|limit|max)\s*(?:is|:)?\s*(\d+)\s*tokens?", re.I),
    ]

    for p in patterns:
        m = p.search(error_message)
        if m:
            try:
                val = int(m.group(1))
                if val >= 1024:  # reasonable context window minimum
                    return val
            except (ValueError, TypeError):
                continue
    return None


async def adiscover_model_context_window(
    model_name: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[int]:
    """
    Proactively discovers model context window from server metadata endpoints.
    - Ollama: POST /api/show -> model_info.context_length
    - OpenRouter: GET /api/v1/models -> context_length
    """
    if not model_name:
        return None

    b_url = (base_url or os.getenv("LLM_BASE_URL") or "").strip().rstrip("/")
    if not b_url:
        return None

    # Check Ollama endpoint
    if "11434" in b_url or b_url.endswith("/v1"):
        try:
            import httpx
            ollama_url = b_url.replace("/v1", "") + "/api/show"
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(ollama_url, json={"name": model_name})
                if res.status_code == 200:
                    data = res.json()
                    info = data.get("model_info", {})
                    for k, v in info.items():
                        if "context_length" in k and isinstance(v, int) and v > 0:
                            record_discovered_context_window(model_name, v)
                            return v
        except Exception:
            pass

    # Check OpenRouter endpoint
    if "openrouter.ai" in b_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.5) as client:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                res = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    for m in data.get("data", []):
                        if m.get("id") == model_name or m.get("name") == model_name:
                            ctx = m.get("context_length")
                            if isinstance(ctx, int) and ctx > 0:
                                record_discovered_context_window(model_name, ctx)
                                return ctx
        except Exception:
            pass

    return None


def get_model_context_window(model_name: Optional[str] = None) -> int:
    """
    Resolves the maximum context window for a given model.
    Checks:
    1. LLM_CONTEXT_WINDOW environment variable override.
    2. DISCOVERED_CONTEXT_WINDOWS (dynamic API discovery & auto-healing cache).
    3. KNOWN_MODEL_CONTEXT_WINDOWS (regex pattern matching).
    4. DEFAULT_CONTEXT_WINDOW (safe fallback).
    """
    env_override = os.getenv("LLM_CONTEXT_WINDOW", "").strip()
    if env_override.isdigit():
        val = int(env_override)
        if val > 0:
            return val

    name_to_check = (model_name or os.getenv("LLM_MODEL") or os.getenv("NINEROUTER_MODEL") or "").strip()
    if not name_to_check:
        return DEFAULT_CONTEXT_WINDOW

    norm_name = name_to_check.lower()
    if norm_name in DISCOVERED_CONTEXT_WINDOWS:
        return DISCOVERED_CONTEXT_WINDOWS[norm_name]

    # 3. Check explicit name suffix tags (e.g. -128k, _64k, -32k, -1m, _2m)
    suffix_m = re.search(r"[-_](\d+)[mM]\b", name_to_check)
    if suffix_m:
        val = int(suffix_m.group(1)) * 1_000_000
        if val > 0:
            return val

    suffix_k = re.search(r"[-_](\d+)[kK]\b", name_to_check)
    if suffix_k:
        val = int(suffix_k.group(1)) * 1024
        if val >= 1024:
            return val

    # 4. Known pattern matching
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


QUESTION_WORDS = {
    'what', 'which', 'how', 'why', 'who', 'where', 'when',
    'is', 'are', 'can', 'could', 'would', 'do', 'does', 'did',
    'explain', 'detail', 'summarize', 'review', 'describe', 'evaluate', 'analyze'
}

NON_DIRECTIVE_PREFIX_WORDS = {
    'inquiry', 'question', 'query', 'prompt', 'turn', 'topic', 'q', 'user', 'response'
}

DIRECTIVE_TAG_KEYWORDS = {
    'constraint', 'rule', 'directive', 'parameter', 'premise', 'policy', 'venue', 'tool',
    'threshold', 'ethics', 'compute', 'data', 'optimizer', 'licensing', 'random', 'hardware',
    'calibration', 'collaborator', 'quantization', 'checkpoint', 'warmup', 'peak', 'target',
    'pooling', 'cache', 'ttl', 'benchmark', 'primary', 'max', 'temperature', 'server', 'model',
    'condition', 'empirical', 'baseline', 'privacy', 'cohort', 'inclusion', 'exclusion',
    'superseding', 'dependency', 'setting', 'note', 'spec', 'requirement', 'device'
}

DIRECTIVE_SEMANTIC_PATTERNS = [
    re.compile(r'\b(?:strictly\s+(?:requires?|disallows?|prohibits?|forbids?|enforces?|mandates?|wants?|must|restrict|ban)|must\s+strictly|strictly\s+never)\b', re.IGNORECASE),
    re.compile(r'\b(?:never\s+(?:use|recommend|suggest|include|evaluate|attribute|link)|do\s+not\s+(?:use|include|suggest|attribute|allow|recommend))\b', re.IGNORECASE),
    re.compile(r'\b(?:don\'?t\s+(?:recommend|use|suggest|include|allow|propose|attribute|even\s+think))\b', re.IGNORECASE),
    re.compile(r'\b(?:only\s+use|use\s+only|exclusively\s+(?:use|for|target|require|restricted)|targeted\s+exclusively)\b', re.IGNORECASE),
    re.compile(r'\b(?:(?:my|our)\s+(?:[a-z0-9_\-]+\s+){0,3}(?:advisor|professor|boss|lab|team|cluster|server|device|protocol|policy|department)\s+(?:strictly\s+)?(?:requires?|mandates?|wants?|insists?|has|possesses|caps?|limits?|specifies|uses?|employs?|follows?))\b', re.IGNORECASE),
    re.compile(r'\b(?:IRB\s*(?:protocol|#|[0-9])|ethics\s+protocol)\b', re.IGNORECASE),
    re.compile(r'\b(?:fix(?:ed)?\s+(?:the\s+)?(?:random\s+seed|batch\s+size|learning\s+rate)|seed\s+(?:is\s+)?fixed\s+at)\b', re.IGNORECASE),
    re.compile(r'\b(?:runtime\s+is\s+capped|budget\s+is\s+capped|capped\s+at|hard-capped)\b', re.IGNORECASE),
    re.compile(r'\bunder\s+our\s+(?:[a-z0-9.]+\s+){0,3}(?:policy|protocol|regimen|standard|guideline|rule)\b', re.IGNORECASE),
    re.compile(r'\b(?:supersed(?:ing|ed)|supersedes)\b', re.IGNORECASE),
    re.compile(r'\b(?:must\s+be\s+excluded|must\s+be\s+included|strictly\s+forbid|disallow\s+all)\b', re.IGNORECASE),
    re.compile(r'\b(?:must\s+(?:resample|extract|initialize|follow|cite|achieve|reside|use))\b', re.IGNORECASE),
    re.compile(r'\b(?:pembimbing\s+(?:gw|saya)|wajib\s+(?:pakai|gunakan)|jangan\s+(?:pernah|rekomendasi|pake)|catat\s+ya|ingat\s+ya)\b', re.IGNORECASE),
    re.compile(r'\b(?:remember\s+that\s+our|keep\s+in\s+mind\s+that\s+we|please\s+note\s+that\s+(?:our|we|all|my))\b', re.IGNORECASE),
]


def is_directive_statement(line: str) -> bool:
    """
    High-Entropy Directive Detection:
    Detects whether a line represents an explicit operational directive, constraint, or premise,
    supporting formal tags ('CONSTRAINT: ...'), mixed/lower tags ('hardware setting: ...'),
    and colloquial natural language phrasing ('eh bro, pembimbing gw wantinya pake korpus multiun').
    """
    line_clean = line.strip()
    if len(line_clean) < 8:
        return False

    words = line_clean.split()
    first_w = re.sub(r'[^a-zA-Z]', '', words[0]).lower()

    # If it starts with question word and ends with '?', treat as inquiry
    if first_w in QUESTION_WORDS and line_clean.endswith('?'):
        return False

    # Tag prefix check
    if ':' in line_clean[:50]:
        prefix = line_clean.split(':', 1)[0].strip()
        body = line_clean.split(':', 1)[1].strip()
        p_words = [re.sub(r'[^a-zA-Z0-9]', '', w).lower() for w in prefix.split()]
        body_first_w = re.sub(r'[^a-zA-Z]', '', body.split()[0]).lower() if body.split() else ''

        if any(w in NON_DIRECTIVE_PREFIX_WORDS for w in p_words):
            return False

        if body_first_w in QUESTION_WORDS and not any(w in DIRECTIVE_TAG_KEYWORDS for w in p_words):
            return False

        if any(w in DIRECTIVE_TAG_KEYWORDS for w in p_words):
            return True

        letters = [c for c in prefix if c.isalpha()]
        if letters:
            upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if upper_ratio >= 0.50 and len(letters) >= 3 and body_first_w not in QUESTION_WORDS:
                return True

    # Check semantic patterns across diverse natural phrasing
    for pat in DIRECTIVE_SEMANTIC_PATTERNS:
        if pat.search(line_clean):
            return True

    return False


def extract_pinned_directives(
    messages: List[LlamaChatMessage],
    max_directives: int = 20
) -> List[str]:
    """
    Tier 1 Pinned Working Memory:
    Extracts explicit operational directives, constraints, and research invariants
    from conversation turns so they are never lost during history compaction.
    """
    directives: List[str] = []
    seen: set = set()

    for m in messages:
        content = str(getattr(m, "content", "") or "").strip()
        if not content or content.startswith("[Context Summary") or content.startswith("[Active Workspace"):
            continue

        for line in content.split("\n"):
            line = line.strip()
            if is_directive_statement(line):
                norm = line.lower()
                if norm not in seen:
                    seen.add(norm)
                    directives.append(line)
                    if len(directives) >= max_directives:
                        break
        if len(directives) >= max_directives:
            break

    return directives


def extract_concise_history_digest(messages: List[LlamaChatMessage]) -> str:
    """
    Tier 2 Structured Topic Digest:
    Extracts conceptual research topics from evicted turns while leaving
    explicit operational constraints to Tier 1 Pinned Directives.
    """
    topics = []
    for m in messages:
        if hasattr(m, "role") and m.role == MessageRole.USER:
            txt = str(m.content or "").strip().split("\n")[0]
            if txt and len(txt) > 5 and not txt.startswith("[Context") and not txt.startswith("[Active Workspace"):
                # Skip lines that are explicit directives (handled by Tier 1)
                if is_directive_statement(txt):
                    continue
                # Clean analytical question topics
                clean_q = re.sub(r'^(?:what|which|how|why|is|are|can|do|does)\s+(?:is|are|the|about)?\s*', '', txt, re.I)
                clean_q = re.sub(r'[\?\.\!]', '', clean_q).strip()
                words = [w for w in clean_q.split() if len(w) > 3][:5]
                if words:
                    topics.append(" ".join(words))
    if topics:
        deduped = list(dict.fromkeys(topics))[:4]
        return "Earlier discussion covered: " + "; ".join(deduped) + "."
    return "Earlier dialogue covered preliminary research inquiries and introductory context."


def _format_compaction_bridge(directives: List[str], summary_text: str) -> str:
    """Combines Tier 1 Pinned Directives and Tier 2 Structured Digest into the system bridge message."""
    parts = []
    if directives:
        directives_block = "\n".join(f"- {d}" for d in directives)
        parts.append(f"[Active Workspace Directives & Constraints (Retained from Earlier Turns):\n{directives_block}]")
    parts.append(f"[Context Summary of Earlier Conversation: {summary_text}]")
    return "\n\n".join(parts)


def compact_chat_history(
    messages: List[LlamaChatMessage],
    max_history_tokens: int,
    model_name: Optional[str] = None,
    summary_text: Optional[str] = None
) -> List[LlamaChatMessage]:
    """
    Multi-Tier Smart History Compaction Protocol:
    1. Checks if message tokens exceed max_history_tokens. If not, returns unchanged.
    2. Identifies partition point to retain recent conversation turns.
    3. Evicted older turns are partitioned into Tier 1 (Pinned Directives) and Tier 2 (Topic Digest).
    4. Prepends the rolling multi-tier bridge as a System message before retained turns.
    5. Dynamically rescues any directives from turns trimmed to satisfy max_history_tokens.
    """
    if not messages or max_history_tokens <= 0:
        return []

    current_tokens = count_messages_tokens(messages, model_name=model_name)
    if current_tokens <= max_history_tokens:
        return messages

    # Dynamically reserve budget for bridge message (~40-300 tokens)
    bridge_reserve = min(300, max(40, int(max_history_tokens * 0.25)))
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

    # Tier 1 & Tier 2 Synthesis
    directives = extract_pinned_directives(evicted_messages)
    seen_directives = set(d.lower() for d in directives)
    active_summary = summary_text or extract_concise_history_digest(evicted_messages)

    bridge_content = _format_compaction_bridge(directives, active_summary)
    bridge_message = LlamaChatMessage(
        role=MessageRole.SYSTEM,
        content=bridge_content
    )

    result = [bridge_message] + retained_messages
    # Strictly enforce total token budget constraint while rescuing any evicted directives
    while len(result) > 2 and count_messages_tokens(result, model_name=model_name) > max_history_tokens:
        popped = result.pop(1)
        new_dirs = extract_pinned_directives([popped])
        updated_dirs = False
        for nd in new_dirs:
            if nd.lower() not in seen_directives:
                directives.append(nd)
                seen_directives.add(nd.lower())
                updated_dirs = True
        if updated_dirs:
            result[0].content = _format_compaction_bridge(directives, active_summary)

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
