import os
import re
import json
from typing import List, Optional
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole, LLM
import logging
from utils.text_processing import (
    clean_academic_abstract,
    is_valid_abstract_content,
    is_ai_synthesized_overview
)

logger = logging.getLogger("uvicorn.error")

async def plan_academic_search(query: str, history: Optional[List[LlamaChatMessage]] = None, llm: Optional[LLM] = None) -> dict:
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
            "  \"native_query\": \"????????? ???????????????\",\n"
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
        raw_text = resp.text.strip()
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text, flags=re.I)
        raw_text = re.sub(r'\s*```$', '', raw_text)
        
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            en_q = str(parsed.get("en_query", "")).strip() or default_plan["en_query"]
            id_q = str(parsed.get("id_query", "")).strip() or default_plan["id_query"]
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
            
            print(f"[AI Query Planner] en_query='{en_q}' | native_query='{native_q}' | languages={target_langs} | count={cnt} | oa={oa_only} | scopus={scopus_q} | sinta={sinta_t} | min_year={m_year} | min_citations={m_cit}")
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
        print(f"[AI Query Planner Warning]: {e} -> using robust fallback")

    return default_plan

async def judge_and_filter_papers_with_llm(
    query: str,
    candidates: List[dict],
    target_count: int,
    llm: Optional[LLM] = None
) -> List[dict]:
    """
    Stage 3.5: Multi-Criteria Academic Rubric Judge & Relevance Auditor.
    Evaluates candidate papers retrieved from registries across 3 strict rubrics:
    1. Core Domain Match (prevents keyword-overlap false positives)
    2. Problem Statement & Methodology Alignment
    3. Academic Substance (discards general blog/noise/unrelated fields)
    """
    if not candidates:
        return []
    
    if llm is None:
        return candidates[:target_count]

    try:
        eval_items = []
        for idx, c in enumerate(candidates):
            title = c.get("title", "").strip()
            snippet = c.get("snippet", "").strip()[:400]
            venue = c.get("venue", "").strip()
            year = c.get("year", "")
            eval_items.append(f"[{idx}] Title: {title} ({year})\nVenue: {venue}\nAbstract/Snippet: {snippet}")

        eval_context = "\n\n".join(eval_items)

        judge_prompt = (
            "You are a Senior Academic Peer Reviewer and Scientific Literature Selection Judge.\n"
            "Your objective: Strictly evaluate each retrieved research candidate against the user's research query using a multi-criteria rubric.\n\n"
            f"User Research Query:\n\"{query}\"\n\n"
            f"Candidate Papers to Audit:\n{eval_context}\n\n"
            "ACADEMIC EVALUATION RUBRIC:\n"
            "1. CORE DOMAIN ALIGNMENT:\n"
            "   - Accept papers that directly investigate the specific target domain.\n"
            "   - Strictly reject keyword coincidence (e.g. if query is 'AI in road crack detection', REJECT medical crack, dental crack, building wall crack, train rail track).\n"
            "2. METHODOLOGICAL & PROBLEM MATCH:\n"
            "   - The paper must address the research questions or methods requested (e.g. classification, prediction, empirical experiment, survey).\n"
            "3. RANKING:\n"
            "   - Rank accepted papers from highest scientific relevance to lowest.\n\n"
            "OUTPUT FORMAT:\n"
            "Return ONLY a JSON list of integer indices of accepted papers in ranked order (best matches first).\n"
            f"Select up to {target_count} best papers.\n"
            "Example format: [2, 0, 4, 1]"
        )

        resp = await llm.acomplete(judge_prompt)
        raw_out = resp.text.strip()
        raw_out = re.sub(r'^```(?:json)?\s*', '', raw_out, flags=re.I)
        raw_out = re.sub(r'\s*```$', '', raw_out)

        valid_indices = json.loads(raw_out)
        if isinstance(valid_indices, list):
            filtered_papers = []
            for idx in valid_indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates):
                    filtered_papers.append(candidates[idx])
            
            if filtered_papers:
                print(f"[AI Judge Auditor] Multi-criteria rubric filtered {len(candidates)} candidates down to {len(filtered_papers)} verified papers.")
                return filtered_papers[:target_count]
    except Exception as e:
        print(f"[AI Judge Auditor Warning]: {e} -> fallback to candidates")

    return candidates[:target_count]

def audit_paper_metadata_with_ai(
    paper_title: str,
    raw_authors: List[str],
    raw_journal: str,
    raw_year: str,
    raw_doi: str,
    raw_citations: int,
    raw_abstract_or_html: str,
    is_oa: bool = False
) -> dict:
    """
    AI Research Auditor & Quality Judge:
    Uses Gemini / active LLM to audit candidate metadata, extract the true abstract,
    filter out garbage category names, and determine Scopus/SINTA quartile and quality_tier.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("models/gemini-flash-latest")
            
            prompt = f"""
You are an expert Senior Academic Research Indexer and Metadata Auditor (like Scopus, Web of Science, Consensus.app, and SINTA).

Audit and extract the most authentic, precise academic metadata for this scientific paper:
- Candidate Title: {paper_title}
- Candidate Authors: {raw_authors}
- Candidate Venue/Journal: {raw_journal}
- Publication Year: {raw_year}
- DOI: {raw_doi}
- Citations: {raw_citations}
- Raw Page Content / Snippet / Abstract text:
{raw_abstract_or_html[:2500]}

Rigorous Global Academic Indexing Rules:
1. TITLE: Exact official title.
2. AUTHORS: List of real author names (clean full names only).
3. YEAR: 4-digit publication year.
4. JOURNAL: Exact journal, conference proceedings, or preprint server name.
5. INDEXING & REPUTATION (journal_metric):
   - CONFERENCE PROCEEDINGS (Any IEEE, ACM, Springer, or international conference/symposium/workshop): MUST be labeled as Conference Proceedings (e.g. "IEEE Conference Proceedings", "ACM Conference Proceedings", "Conference Proceedings (Indexed)"). Conferences DO NOT have Q1/Q2/Q3/Q4.
   - PREPRINT REPOSITORIES (arXiv, SportRxiv, bioRxiv, medRxiv, SSRN, Research Square, OSF, RePEc): "Preprint (Non-Peer-Reviewed)".
   - INDONESIAN NATIONAL JOURNALS (SINTA): Identify if accredited (e.g. "SINTA 2 Accredited" or "SINTA Accredited").
   - INTERNATIONAL PEER-REVIEWED JOURNALS: Use your scholarly knowledge base of world journals. If it is a top-quartile journal in its domain, use "Scopus Q1 (SJR)". If high-tier, use "Scopus Q2 (SJR)". If mid-tier, use "Scopus Q3 (SJR)". If regular indexed or open access, use "Scopus Q4 / Indexed" or "DOAJ Open Access".
6. ABSTRACT:
   - Extract authentic original abstract paragraph written by the authors.
   - REJECT any subject taxonomy categories (like "Social and Behavioral Sciences", "Medicine", "Engineering"), cookie disclaimers, or license notices.
   - If genuine authentic abstract found: set abstract_type = "official".
   - If strictly paywalled or missing and you synthesize a summary: set abstract_type = "ai_summary".

Output ONLY valid JSON matching:
{{
  "title": "...",
  "authors": ["..."],
  "year": "...",
  "journal": "...",
  "journal_metric": "...",
  "abstract": "...",
  "abstract_type": "official" or "ai_summary"
}}
"""
            res = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": 5}
            )
            if res.text:
                parsed = json.loads(res.text)
                if parsed.get("abstract"):
                    if is_ai_synthesized_overview(parsed.get("abstract")):
                        parsed["abstract_type"] = "ai_summary"
                    elif is_valid_abstract_content(parsed.get("abstract")):
                        if not parsed.get("abstract_type"):
                            parsed["abstract_type"] = "official"
                    return parsed
        except Exception as e:
            logger.debug(f"[AI Auditor] Audit failed for '{paper_title}': {e}")

    j_low = (raw_journal or "").lower()
    if any(p in j_low for p in ["sportrxiv", "arxiv", "biorxiv", "medrxiv", "ssrn", "osf", "repec", "research square", "preprint"]):
        metric = "Preprint (Non-Peer-Reviewed)"
    elif any(c in j_low for c in ["conference", "proceedings", "symposium", "workshop", "congress"]):
        metric = "Conference Proceedings (Indexed)"
    elif any(s in j_low for s in ["sinta", "garuda"]):
        metric = "SINTA Accredited"
    elif is_oa:
        metric = "Open Access Journal"
    else:
        metric = "Peer-Reviewed Publication"

    return {
        "title": paper_title,
        "authors": raw_authors,
        "year": raw_year,
        "journal": raw_journal or "Peer-reviewed Publication",
        "journal_metric": metric,
        "abstract": clean_academic_abstract(raw_abstract_or_html),
        "abstract_type": "official" if is_valid_abstract_content(raw_abstract_or_html) else "ai_summary"
    }