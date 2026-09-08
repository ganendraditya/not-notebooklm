import re
import json
import logging
from typing import List, Optional
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole, LLM

from utils.text_processing import extract_json_from_llm

logger = logging.getLogger("uvicorn.error")

async def plan_academic_search(
    query: str, 
    history: Optional[List[LlamaChatMessage]] = None, 
    llm: Optional[LLM] = None
) -> dict:
    """
    Stage 1: LLM-Powered Academic Query Planner (Consensus.app / Elicit / Perplexity style)
    Uses the AI model to understand conversational intent, context, multi-lingual requirements, and exact quantities.
    """
    clean_text = re.sub(
        r'\b(cariin|carikan|cari|search|find|tentang|about|paper|jurnal|artikel|sumber|sources|buah|biji|referensi|makalah|dong|ya|tolong|minta|lagi|bos|bro|nih|deh|aja|sih|buat|ke|max|maksimal|tahun|terakhir|ke\s*belakang|jangan|lebih|dari|itu|gw|gua|gue|aku|saya|lu|lo|kamu)\b',
        ' ',
        query,
        flags=re.I
    )
    clean_text = re.sub(r'\d+', ' ', clean_text)
    clean_text = ' '.join(clean_text.split()).strip()

    id_indicators = [
        "cari", "cariin", "carikan", "tolong", "tentang", "jurnal", "makalah", "terbaru", 
        "tahun", "terakhir", "dong", "deh", "nih", "gw", "gua", "gue", "bisa", "buat", "kalo", "yg", "yang"
    ]
    is_mostly_id = any(re.search(rf'\b{re.escape(w)}\b', query, re.I) for w in id_indicators)
    default_lang = "mixed" if is_mostly_id else "en"

    default_languages: List[str] = []
    lang_pref_match = re.search(r'\[Filter Preferences:[^\]]*\blanguages:\s*([^,\]]+(?:,\s*[^,\]]+)*)', query, re.I)
    if lang_pref_match:
        raw_lang_str = lang_pref_match.group(1).split("discipline:")[0].split("year:")[0].split("min citations:")[0].strip()
        raw_langs = [l.strip().lower() for l in raw_lang_str.split(",") if l.strip()]
        default_languages = [l for l in raw_langs if l != "all" and len(l) <= 10]

    default_plan = {
        "en_query": clean_text if len(clean_text) >= 3 else query.strip(),
        "id_query": clean_text if len(clean_text) >= 3 else query.strip(),
        "native_query": clean_text if len(clean_text) >= 3 else query.strip(),
        "target_count": 12,
        "languages": default_languages,
        "language_preference": default_lang,
        "open_access_only": False,
        "scopus_quartiles": [],
        "sinta_tiers": [],
        "exclude_preprints": False
    }
    
    user_requested_count = None
    default_min_year = None
    if any(k in query.lower() for k in ["5 tahun", "lima tahun", "terbaru", "recent"]):
        default_min_year = 2020
    year_match = re.search(r'\b(201\d|202\d)\b', query)
    if year_match and not default_min_year:
        default_min_year = int(year_match.group(1))

    num_match = re.search(r'(\d+)\s*(?:paper|jurnal|artikel|sumber|sources|buah|biji|referensi|makalah|lagi)', query, re.I)
    if num_match:
        try:
            p_num = int(num_match.group(1))
            user_requested_count = p_num
            default_plan["target_count"] = min(max(p_num, 1), 100)
            if p_num > 100:
                default_plan["user_requested_count"] = p_num
        except Exception:
            pass

    if any(k in query.lower() for k in ["open access", "open-access", "oa only", "open access only", "free pdf", "gratis", "free full text"]):
        default_plan["open_access_only"] = True

    q_matches = re.findall(r'\b[qQ]([1-4])\b', query)
    if q_matches:
        default_plan["scopus_quartiles"] = list(set([f"Q{q}" for q in q_matches]))

    sinta_matches = re.findall(r'\bsinta\s*([1-6])\b', query, re.I)
    if sinta_matches:
        default_plan["sinta_tiers"] = list(set([f"S{s}" for s in sinta_matches]))

    if any(k in query.lower() for k in ["exclude preprint", "tanpa preprint", "bukan preprint", "exclude preprints"]):
        default_plan["exclude_preprints"] = True

    default_min_citations = 0
    cit_match = re.search(r'(?:minimum|min|tersitasi\s*minimal|sitasi\s*minimal|cit(?:ed|ations)?\s*(?:>=|min|minimal)?)\s*[:=]?\s*(\d+)', query, re.I)
    if cit_match:
        try:
            default_min_citations = int(cit_match.group(1))
        except Exception:
            pass

    if default_min_year:
        default_plan["min_year"] = default_min_year
    if default_min_citations > 0:
        default_plan["min_citations"] = default_min_citations

    if llm is None:
        return default_plan

    try:
        context_str = ""
        if history:
            hist_snippets = []
            for m in history:
                role_name = getattr(m, 'role', '')
                if role_name == MessageRole.USER or role_name == 'user':
                    hist_snippets.append(f"User: {m.content}")
                elif role_name == MessageRole.ASSISTANT or role_name == 'assistant':
                    clean_c = m.content.split('<!-- SOURCES_DATA')[0].strip()
                    hist_snippets.append(f"Assistant: {clean_c}")
            if hist_snippets:
                context_str = "\nPrevious Full Conversation History:\n" + "\n\n".join(hist_snippets) + "\n\n"

        prompt = (
            "You are an AI Academic Query Planner for a research search engine (like Consensus.app, Elicit, Perplexity).\n"
            "Your job: Analyze the user's prompt, any attached '[Filter Preferences: ...]' tags, and conversation context to extract clean, high-precision academic search parameters in JSON.\n\n"
            f"{context_str}"
            "Current User Request:\n"
            f"\"{query}\"\n\n"
            "Rules for extraction:\n"
            "1. CONTEXT & TOPIC RESOLUTION (CRITICAL):\n"
            "   - If the user's request refers to previous topics or previous requests (e.g. 'rekomendasiin biar bisa diimport', 'topik tadi'): You MUST examine 'Previous Conversation Context' to identify the specific research domain and retain it!\n"
            "   - Indonesian slang: 'gw' / 'gua' / 'gue' = 'I / me'. NEVER interpret 'gw' as 'GW' or 'Gigawatt'!\n"
            "2. 'en_query': Pure English academic search term for global scholarly databases.\n"
            "3. 'native_query': Academic search term translated into the target language(s).\n"
            "4. 'languages': Array of 2-letter ISO 639-1 language codes (e.g. [\"ja\"], [\"zh\"], [\"id\"], [\"en\"]).\n"
            "   - Priority 1: If '[Filter Preferences: ... languages: ja, zh]' is explicitly present in the query, strictly use those codes!\n"
            "   - Priority 2: If the user wrote their prompt in Japanese, Chinese, etc., add its code.\n"
            "   - Priority 3: Leave as empty [] if global English.\n"
            "5. 'target_count': Integer representing how many papers to search for.\n"
            "   - If specified (e.g. 10, 30, 50), set it exactly.\n"
            "   - If NOT specified, set to a natural relevant size between 8 and 15.\n"
            "6. 'open_access_only': Boolean true if free PDF requested, else false.\n"
            "7. 'scopus_quartiles': Array of strings like [\"Q1\"], [\"Q1\", \"Q2\"], or empty [].\n"
            "8. 'sinta_tiers': Array of strings like [\"S1\", \"S2\"], or empty [].\n"
            "9. 'exclude_preprints': Boolean true if preprints should be excluded, else false.\n"
            "10. 'user_requested_count': Exact integer if user specified a number (e.g. 30, 50), otherwise null.\n"
            "11. 'min_year': Integer representing minimum publication year, otherwise null.\n"
            "12. 'min_citations': Integer representing minimum citations count threshold, otherwise 0.\n"
            "13. Return ONLY a valid JSON object without any markdown code fences or conversational text.\n\n"
            "Example Output:\n"
            "{\n"
            "  \"en_query\": \"psychology clinical therapy\",\n"
            "  \"native_query\": \"心理学 臨床療法\",\n"
            "  \"languages\": [\"ja\"],\n"
            "  \"target_count\": 12,\n"
            "  \"open_access_only\": true,\n"
            "  \"scopus_quartiles\": [],\n"
            "  \"sinta_tiers\": [],\n"
            "  \"exclude_preprints\": false,\n"
            "  \"user_requested_count\": null,\n"
            "  \"min_year\": 2021,\n"
            "  \"min_citations\": 0\n"
            "}"
        )
        
        resp = await llm.acomplete(prompt)
        raw_text = extract_json_from_llm(resp.text)
        parsed = json.loads(raw_text)

        if isinstance(parsed, dict):
            en_q = str(parsed.get("en_query", "")).strip() or default_plan["en_query"]
            cnt = int(parsed.get("target_count", default_plan["target_count"]))
            req_cnt = parsed.get("user_requested_count")
            if req_cnt is not None:
                try:
                    req_cnt = int(req_cnt)
                except Exception:
                    req_cnt = None
            if user_requested_count and user_requested_count > 100:
                req_cnt = user_requested_count
            cnt = min(max(cnt, 1), 100)
            
            m_year = parsed.get("min_year") or default_min_year
            if m_year is not None:
                try:
                    m_year = int(m_year)
                except Exception:
                    m_year = None
                    
            m_cit = parsed.get("min_citations")
            if m_cit is not None:
                try:
                    m_cit = int(m_cit)
                except Exception:
                    m_cit = default_min_citations
            else:
                m_cit = default_min_citations
                    
            native_q = str(parsed.get("native_query", "")).strip() or str(parsed.get("id_query", "")).strip() or default_plan["native_query"]
            parsed_langs = parsed.get("languages")
            target_langs: List[str] = []

            if isinstance(parsed_langs, list):
                target_langs = [str(l).strip().lower() for l in parsed_langs if str(l).strip() and str(l).strip().lower() != "all"]
            elif isinstance(parsed_langs, str) and parsed_langs.strip():
                target_langs = [l.strip().lower() for l in parsed_langs.split(",") if l.strip() and l.strip().lower() != "all"]

            if default_languages:
                target_langs = default_languages

            lang = str(parsed.get("language_preference", default_plan["language_preference"])).lower()
            if not target_langs and lang in ["id", "en", "mixed"]:
                if lang == "id": target_langs = ["id"]
                elif lang == "en": target_langs = ["en"]

            oa_only = bool(parsed.get("open_access_only", default_plan["open_access_only"])) or default_plan["open_access_only"]
            scopus_q = parsed.get("scopus_quartiles") or default_plan["scopus_quartiles"]
            sinta_t = parsed.get("sinta_tiers") or default_plan["sinta_tiers"]
            ex_prep = bool(parsed.get("exclude_preprints", default_plan["exclude_preprints"])) or default_plan["exclude_preprints"]
            
            return {
                "en_query": en_q,
                "id_query": native_q,
                "native_query": native_q,
                "languages": target_langs,
                "target_count": cnt,
                "open_access_only": oa_only,
                "scopus_quartiles": scopus_q,
                "sinta_tiers": sinta_t,
                "exclude_preprints": ex_prep,
                "user_requested_count": req_cnt,
                "min_year": m_year,
                "min_citations": m_cit,
                "language_preference": lang
            }
    except Exception as e:
        logger.debug(f"[AI Query Planner Warning]: {e} -> using robust fallback")

    return default_plan
