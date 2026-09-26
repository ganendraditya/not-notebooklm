"""
Semantic Intent Classifier for RAG workflows.
Classifies user queries semantically via LLM into:
- REMOVE_SOURCES
- SEARCH_NEW
- ANALYZE_WORKSPACE
- GENERAL_CHAT
"""

import logging
from typing import Optional, Any
from llama_index.core.llms import LLM

logger = logging.getLogger("uvicorn.error")


def format_micro_dialogue_trace(
    chat_history: Optional[Any] = None,
    max_turns: int = 2,
    max_chars: int = 150
) -> str:
    """
    Extracts an ultra-lean sliding window trace of the last k turns (<200 tokens total)
    to enable fast-LLM anaphora and intent resolution without context window bloating.
    """
    if not chat_history:
        return ""

    cleaned_messages = []
    for item in chat_history:
        role = ""
        content = ""
        if isinstance(item, dict):
            raw_role = str(item.get("role", "")).lower()
            role = "User" if raw_role == "user" else "Assistant"
            content = str(item.get("content", ""))
        elif hasattr(item, "role") and hasattr(item, "content"):
            raw_role = str(item.role).lower()
            role = "User" if "user" in raw_role else "Assistant"
            content = str(item.content)
        else:
            continue

        # Strip internal structured metadata markers
        if "<!-- SOURCES_DATA" in content:
            content = content.split("<!-- SOURCES_DATA")[0].strip()
        if "<!-- CITATION_MAP" in content:
            content = content.split("<!-- CITATION_MAP")[0].strip()
        if "<!-- SOURCES_ACTION" in content:
            content = content.split("<!-- SOURCES_ACTION")[0].strip()

        content = content.strip()
        if content:
            # Flatten consecutive newlines and extra spaces
            content = " ".join(content.split())
            if len(content) > max_chars:
                content = content[:max_chars].rstrip() + "..."
            cleaned_messages.append(f"{role}: {content}")

    if not cleaned_messages:
        return ""

    # Each full turn is up to 2 messages (User + Assistant). max_turns = 2 => up to 4 messages.
    slice_count = max_turns * 2
    recent_tail = cleaned_messages[-slice_count:]
    return "\n".join(recent_tail)


async def classify_user_intent(
    user_query: str, 
    has_docs: bool, 
    doc_count: int, 
    llm: LLM,
    chat_history: Optional[Any] = None
) -> str:
    """Uses LLM semantic classification with micro-dialogue context to accurately determine user intent."""
    dialogue_trace = format_micro_dialogue_trace(chat_history, max_turns=2, max_chars=150)
    context_block = ""
    if dialogue_trace:
        context_block = f"\nRecent Dialogue Context (Last turns):\n{dialogue_trace}\n"

    system_intent_prompt = f"""You are the Master Intent Classifier for NotbookLM research workspace.
Current Workspace Status: {'Contains ' + str(doc_count) + ' imported documents' if has_docs else 'No documents imported yet'}.{context_block}
Analyze the user's latest prompt carefully in the context of the recent dialogue and determine their true intention. Choose strictly ONE of the following 4 categories:

1. 'REMOVE_SOURCES':
   - ONLY when the user is giving an EXPLICIT, DIRECT COMMAND to delete or remove documents from their sources (e.g. 'delete paper A, B, C', 'remove irrelevant papers', 'discard loaded documents').
   - DO NOT choose this if the user is merely asking a question or criticizing/evaluating documents (e.g. 'are any papers irrelevant?', 'this paper is wrong').

2. 'SEARCH_NEW':
   - When the user is asking to find, discover, search, fetch, or recommend NEW academic papers or literature from external registries or the internet (e.g. 'find papers about machine learning', 'search 10 more papers', 'recommend recent publications').
   - DO NOT choose this if the user is asking about or analyzing documents ALREADY inside their workspace.

3. 'ANALYZE_WORKSPACE':
   - When the user is asking questions about, crosschecking, synthesizing, summarizing, comparing, or listing documents ALREADY inside their workspace.
   - CONTEXTUAL FOLLOW-UP & ANAPHORA (CRITICAL): If the user's latest query is an implicit follow-up, continuation, or pronoun reference related to an ongoing document discussion shown in Recent Dialogue Context (e.g. 'Why did that happen?', 'What about their limitations?', 'Explain point number 2', 'Compare them again', 'Continue', 'Lalu bagaimana dengan limitasinya?'), choose 'ANALYZE_WORKSPACE'. Do NOT misclassify as GENERAL_CHAT.

4. 'GENERAL_CHAT':
   - For standalone greetings, casual small talk, thanking, system explanations, or general knowledge questions completely unrelated to the workspace documents or ongoing document discussion.

User Prompt: "{user_query}"

Respond with ONLY the exact category name (REMOVE_SOURCES, SEARCH_NEW, ANALYZE_WORKSPACE, or GENERAL_CHAT) without quotes or explanations."""
    try:
        resp = await llm.acomplete(system_intent_prompt)
        raw_intent = resp.text.strip().upper().replace("'", "").replace('"', "").replace("`", "")
        for valid in ["REMOVE_SOURCES", "SEARCH_NEW", "ANALYZE_WORKSPACE", "GENERAL_CHAT"]:
            if valid in raw_intent:
                if not has_docs and valid in ("ANALYZE_WORKSPACE", "REMOVE_SOURCES"):
                    return "GENERAL_CHAT"
                return valid
    except Exception as e:
        logger.debug(f"[Intent Classifier Error]: {e}")

    if has_docs:
        return "ANALYZE_WORKSPACE"
    return "GENERAL_CHAT"
