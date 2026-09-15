"""
Semantic Intent Classifier for RAG workflows.
Classifies user queries semantically via LLM into:
- REMOVE_SOURCES
- SEARCH_NEW
- ANALYZE_WORKSPACE
- GENERAL_CHAT
"""

import logging
from typing import Optional
from llama_index.core.llms import LLM

logger = logging.getLogger("uvicorn.error")


async def classify_user_intent(user_query: str, has_docs: bool, doc_count: int, llm: LLM) -> str:
    """Uses LLM semantic classification to accurately determine user intent without brittle regex heuristics."""
    system_intent_prompt = f"""You are the Master Intent Classifier for NotbookLM research workspace.
Current Workspace Status: {'Contains ' + str(doc_count) + ' imported documents' if has_docs else 'No documents imported yet'}.

Analyze the user's latest prompt carefully and determine their true intention. Choose strictly ONE of the following 4 categories:

1. 'REMOVE_SOURCES':
   - ONLY when the user is giving an EXPLICIT, DIRECT COMMAND to delete or remove documents from their sources (e.g. 'tolong hapus 12 paper tadi', 'hapusin paper yang ga relevan', 'delete paper A, B, C', 'buang dokumen yang tidak cocok').
   - DO NOT choose this if the user is merely asking a question or seeking evaluation (e.g. 'apakah ada yang ga relevan?', 'ada berapa paper yang tidak cocok?').

2. 'SEARCH_NEW':
   - When the user is asking to find, discover, search, fetch, or recommend NEW academic papers or literature from the internet (e.g. 'cariin 50 paper tentang rainfall', 'find papers about machine learning', 'tambah 20 paper lagi', 'rekomendasiin paper terkini').
   - DO NOT choose this if the user is asking about the documents already inside their workspace (e.g. 'ada berapa paper di sources?', 'apakah di dokumen saya ada paper Indo?').

3. 'ANALYZE_WORKSPACE':
   - When the user is asking questions about, crosschecking, synthesizing, summarizing, comparing, or listing the documents ALREADY inside their workspace (e.g. 'ada berapa paper indo di sources?', 'analisis perbandingan metode dari dokumen ini', 'buat ringkasan bab 1', 'apakah ada dokumen yang tidak relevan di sources saya?').

4. 'GENERAL_CHAT':
   - For greetings, casual questions, thanking, testing, system explanations, or general knowledge questions.

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
