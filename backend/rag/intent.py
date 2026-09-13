"""
Semantic Intent Classifier and Heuristic Filters for RAG workflows.
Classifies user queries into:
- REMOVE_SOURCES
- SEARCH_NEW
- ANALYZE_WORKSPACE
- GENERAL_CHAT
"""

import re
import logging
from typing import List, Optional
from llama_index.core.llms import LLM

logger = logging.getLogger("uvicorn.error")

GREETINGS_EXACT = {
    "halo", "hai", "hi", "hello", "hey", "hei", "pagi", "siang", "sore", "malam",
    "good morning", "good afternoon", "good evening", "good night",
    "terima kasih", "makasih", "thanks", "thank you", "siapa kamu", "who are you",
    "bisa apa", "kamu siapa", "what can you do", "tes", "test", "ping", "bisa bantu apa",
    "woi", "oy", "p", "bro", "bos", "min", "apa kabar", "how are you", "how are you doing",
    "hows it going", "how is it going", "sup", "whats up",
    "gimana kabarnya", "kabar apa", "sehat", "apa kabarmu", "apa kabarmu bro",
    "piye kabare", "piye kabare mas", "piye kabare mbak", "sugeng enjang", "sugeng siang", "sugeng sonten", "sugeng dalu", "matur nuwun",
    "hola", "buenos dias", "buenas tardes", "buenas noches", "como estas", "que tal", "hola como estas", "gracias",
    "안녕하세요", "안녕", "어떻게 지내세요", "어떻게 지내", "반갑습니다", "고마워", "감사합니다", "테스트",
    "konnichiwa", "arigato", "ohayo", "ohayou", "ohayou gozaimasu", "kombanwa"
}


def is_simple_conversational(text: str) -> bool:
    """Checks if text is a simple greeting or acknowledgment."""
    t = re.sub(r'[^\w\s]', '', text.lower()).strip()
    tokens = t.split()
    if len(tokens) == 0 or len(tokens) > 6:
        return False
        
    t_clean = t.replace("¿", "").replace("?", "").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
    
    if t in GREETINGS_EXACT or t_clean in GREETINGS_EXACT:
        return True
        
    clean_prefix = re.sub(r'^(halo|hai|hi|hello|hey|hei|woi|oy|p|bro|bos|min|assalamualaikum|mas|mbak|pak|bu|hola)\s+', '', t_clean).strip()
    clean_suffix = re.sub(r'\s+(mas|mbak|pak|bu|bro|bos|min|ya|dong|gan|rek)$', '', t_clean).strip()
    clean_both = re.sub(r'\s+(mas|mbak|pak|bu|bro|bos|min|ya|dong|gan|rek)$', '', clean_prefix).strip()
    
    return clean_prefix in GREETINGS_EXACT or clean_suffix in GREETINGS_EXACT or clean_both in GREETINGS_EXACT


def is_technical_discussion(text: str) -> bool:
    """Identifies queries asking about NotbookLM system internals, RAG, databases, or embeddings."""
    t = text.lower().strip()
    tech_triggers = [
        "pake rag", "pakai rag", "sistem rag", "cara kerja", "arsitektur",
        "database apa", "vector database", "database vektor", "gimana sistemnya",
        "gimana cara kerja", "masuk ke database", "disimpan di mana", "data disimpan",
        "bisa fetch apa", "bisa akses apa", "paywall", "open access kah", "cara lo dapet",
        "dapetin papernya gimana", "punya database sendiri", "apakah ada database",
        "gimana lu", "gimana lo", "bagaimana kamu", "apakah kamu", "kenapa kamu"
    ]
    return any(tr in t for tr in tech_triggers)


def is_sources_meta_query(text: str) -> bool:
    """Identifies metadata questions regarding loaded sources."""
    t = text.lower().strip()
    if any(dt in t for dt in ["hapus", "hapusin", "remove", "delete", "bersihkan", "buang", "drop"]):
        return False
    meta_phrases = [
        "berapa dokumen", "berapa file", "berapa banyak dokumen", "berapa jumlah dokumen",
        "berapa total dokumen", "jumlah dokumen", "daftar dokumen", "ada berapa dokumen",
        "ada dokumen apa", "dokumen apa saja", "list dokumen", "sebutkan dokumen",
        "dokumen yang diupload", "dokumen yang diimpor", "berapa source", "jumlah source",
        "berapa referensi", "daftar referensi", "ada referensi apa", "berapa doang", "berapa yang",
        "yang mana saja", "relevan berapa", "yang cocok berapa"
    ]
    return any(p in t for p in meta_phrases)


async def classify_user_intent(user_query: str, has_docs: bool, doc_count: int, llm: LLM) -> str:
    """Uses fast regex heuristics and target LLM to semantically classify user intent."""
    # Fast-path heuristics: instant zero-latency resolution
    if is_simple_conversational(user_query) or is_technical_discussion(user_query):
        return "GENERAL_CHAT"
    if is_sources_meta_query(user_query) and has_docs:
        return "ANALYZE_WORKSPACE"

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
