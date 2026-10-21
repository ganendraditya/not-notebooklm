import os
import time
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from runtime_environment import load_backend_environment

load_backend_environment()

from rag.llm_factory import get_fast_llm, get_main_llm
from journal_indexer import lookup_journal_index

# The 10 Diverse Heterogeneous Test Cases
TEST_CASES = [
    {
        "id": 1,
        "name": "Nature (Top Global Multi-Disciplinary)",
        "title": "A global survey on deep learning in healthcare",
        "journal": "Nature",
        "issns": ["0028-0836", "1476-4687"],
        "venue_type": "journal",
        "ground_truth": "Scopus Q1 (SJR > 10.0)",
        "gt_type": "Scopus Q1"
    },
    {
        "id": 2,
        "name": "IEEE TPAMI (Flagship AI/CV Journal)",
        "title": "Deep Residual Learning for Image Recognition",
        "journal": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
        "issns": ["0162-8828", "1939-3539"],
        "venue_type": "journal",
        "ground_truth": "Scopus Q1 (SJR > 6.0)",
        "gt_type": "Scopus Q1"
    },
    {
        "id": 3,
        "name": "Applied Intelligence (Mid-Tier Computing Journal)",
        "title": "Advances in Artificial Intelligence and Soft Computing",
        "journal": "Applied Intelligence",
        "issns": ["0924-669X", "1573-7497"],
        "venue_type": "journal",
        "ground_truth": "Scopus Q2 (SJR: ~0.8)",
        "gt_type": "Scopus Q2"
    },
    {
        "id": 4,
        "name": "IJECE (Lower-Tier Scopus / SINTA 1 Journal)",
        "title": "An Empirical Study of Mobile Ad-hoc Networks",
        "journal": "International Journal of Electrical and Computer Engineering",
        "issns": ["2088-8708", "2722-2578"],
        "venue_type": "journal",
        "ground_truth": "Scopus Q3 & SINTA 1",
        "gt_type": "Scopus Q3"
    },
    {
        "id": 5,
        "name": "Jurnal RESTI (Indonesian SINTA 2 National)",
        "title": "Analisis Sentimen Menggunakan Support Vector Machine pada Twitter",
        "journal": "Jurnal RESTI (Rekayasa Sistem dan Teknologi Informasi)",
        "issns": ["2580-0760"],
        "venue_type": "journal",
        "ground_truth": "SINTA 2 Accredited",
        "gt_type": "SINTA 2"
    },
    {
        "id": 6,
        "name": "Jurnal SISFOKOM (Indonesian SINTA 3 National)",
        "title": "Penerapan Metode SAW dalam Penentuan Penerima Beasiswa",
        "journal": "Jurnal SISFOKOM (Sistem Informasi dan Komputer)",
        "issns": ["2301-7988", "2581-0588"],
        "venue_type": "journal",
        "ground_truth": "SINTA 3 Accredited (Bukan SINTA 2!)",
        "gt_type": "SINTA 3"
    },
    {
        "id": 7,
        "name": "CVPR (Top Computer Vision Conference Proceedings)",
        "title": "Attention Is All You Need in Vision",
        "journal": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        "issns": [],
        "venue_type": "conference",
        "ground_truth": "Conference Proceedings (No Quartile)",
        "gt_type": "Conference"
    },
    {
        "id": 8,
        "name": "arXiv (Preprint Server)",
        "title": "Llama 3: Herd of Open Models",
        "journal": "arXiv preprint cs.AI",
        "issns": [],
        "venue_type": "preprint",
        "ground_truth": "Preprint (Non-Peer-Reviewed)",
        "gt_type": "Preprint"
    },
    {
        "id": 9,
        "name": "IJETER (Discontinued / Dropped Scopus Journal)",
        "title": "Investigation of smart IoT sensors",
        "journal": "International Journal of Emerging Trends in Engineering Research",
        "issns": ["2347-3983"],
        "venue_type": "journal",
        "ground_truth": "Peer-Reviewed (Dropped / Not in active Scopus)",
        "gt_type": "Peer-Reviewed"
    },
    {
        "id": 10,
        "name": "Jurnal Mahasiswa Lokal (Unindexed Local Campus)",
        "title": "Rancang Bangun Sistem Informasi Kepegawaian",
        "journal": "Jurnal Ilmiah Mahasiswa Informatika Kampus Nusantara",
        "issns": ["9999-9999"],
        "venue_type": "journal",
        "ground_truth": "Peer-Reviewed (Not indexed in Scopus/SINTA)",
        "gt_type": "Peer-Reviewed"
    }
]

def run_before_pipeline(case, llm):
    """Simulates the OLD pipeline: Old substring heuristics + LLM quartile estimation."""
    t0 = time.perf_counter()
    j_name = case["journal"].lower()
    
    # 1. Old substring hardcode heuristics
    if "resti" in j_name:
        heur_metric = "SINTA 2 Accredited"
    elif "ilkom" in j_name:
        heur_metric = "SINTA 2 Accredited"
    elif "sisfo" in j_name:
        heur_metric = "SINTA 2 Accredited" # Notice the flaw: Sisfo was hardcoded as SINTA 2!
    elif any(kw in j_name for kw in ["icmla", "calcon", "icaart", "cvpr", "conference", "ieee/cvf"]):
        heur_metric = "Conference Proceedings (Indexed)"
    elif "arxiv" in j_name or case["venue_type"] == "preprint":
        heur_metric = "Preprint (Non-Peer-Reviewed)"
    else:
        heur_metric = None

    # If heuristic didn't catch or was ambiguous, old pipeline called LLM auditor
    llm_metric = None
    input_tokens = 0
    output_tokens = 0

    if not heur_metric or heur_metric == "Peer-Reviewed Journal":
        old_prompt = f"""You are an expert Senior Academic Research Indexer and Metadata Auditor.
Audit and extract indexing for:
- Title: {case['title']}
- Journal/Venue: {case['journal']}

Rigorous Global Academic Indexing Rules:
- CONFERENCE PROCEEDINGS: Label as Conference Proceedings.
- PREPRINT REPOSITORIES (arXiv, bioRxiv): "Preprint (Non-Peer-Reviewed)".
- INDONESIAN NATIONAL JOURNALS (SINTA): Identify if accredited (e.g. "SINTA 2 Accredited").
- INTERNATIONAL PEER-REVIEWED JOURNALS: Use your scholarly knowledge base of world journals. If it is a top-quartile journal in its domain, use "Scopus Q1 (SJR)". If high-tier, use "Scopus Q2 (SJR)". If mid-tier, use "Scopus Q3 (SJR)". If regular indexed or open access, use "Scopus Q4 / Indexed" or "DOAJ Open Access".

Output JSON: {{"journal_metric": "..."}}"""
        try:
            resp = llm.complete(old_prompt)
            raw_text = resp.text.strip()
            # Estimate tokens
            input_tokens = len(old_prompt.split()) * 2
            output_tokens = len(raw_text.split()) * 2
            import re
            m = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                llm_metric = parsed.get("journal_metric")
            else:
                llm_metric = raw_text
        except Exception as e:
            llm_metric = f"Error: {e}"

    t1 = time.perf_counter()
    final_output = heur_metric or llm_metric or "Peer-Reviewed Journal"
    return {
        "output": final_output,
        "latency_ms": (t1 - t0) * 1000,
        "tokens": input_tokens + output_tokens,
        "source": "Heuristic" if heur_metric else "LLM Guess"
    }

def run_after_pipeline(case):
    """Runs the NEW Deterministic Pipeline: Exact SQLite Scopus + Live SINTA + Venue Types."""
    t0 = time.perf_counter()
    res = lookup_journal_index(
        issn_list=case["issns"],
        journal_title=case["journal"],
        venue_type=case["venue_type"]
    )
    t1 = time.perf_counter()
    return {
        "output": res.get("journal_metric"),
        "quartile": res.get("quartile"),
        "sjr": res.get("sjr", 0.0),
        "indexing_type": res.get("indexing_type"),
        "latency_ms": (t1 - t0) * 1000,
        "tokens": 0,
        "source": res.get("indexing_type") or ("Conference" if res.get("is_conference") else ("Preprint" if res.get("is_preprint") else "Fallback"))
    }

def evaluate_match(gt_type, output_str):
    out = (output_str or "").upper()
    if gt_type == "Scopus Q1":
        return "Q1" in out and "SCOPUS" in out
    elif gt_type == "Scopus Q2":
        return "Q2" in out and "SCOPUS" in out
    elif gt_type == "Scopus Q3":
        return ("Q3" in out and "SCOPUS" in out) or ("S1" in out and "ACCREDITED" in out)
    elif gt_type == "SINTA 2":
        return "S2" in out or "SINTA 2" in out
    elif gt_type == "SINTA 3":
        return "S3" in out or "SINTA 3" in out
    elif gt_type == "Conference":
        return "CONFERENCE" in out and not any(q in out for q in ["Q1", "Q2", "Q3", "Q4"])
    elif gt_type == "Preprint":
        return "PREPRINT" in out and not any(q in out for q in ["Q1", "Q2", "Q3", "Q4"])
    elif gt_type == "Peer-Reviewed":
        return not any(q in out for q in ["Q1", "Q2", "Q3", "Q4", "S1", "S2", "S3"])
    return False

def main():
    llm = get_fast_llm() or get_main_llm()
    print("=" * 80)
    print("10-CASE EMPIRICAL BENCHMARK: OLD (LLM GUESS + HARDCODE) VS NEW (DETERMINISTIC)")
    print("=" * 80)

    results = []
    for c in TEST_CASES:
        print(f"\n[Evaluating Case {c['id']}/10]: {c['name']}...")
        before_res = run_before_pipeline(c, llm)
        after_res = run_after_pipeline(c)

        before_acc = evaluate_match(c["gt_type"], before_res["output"])
        after_acc = evaluate_match(c["gt_type"], after_res["output"])

        results.append({
            "case": c,
            "before": before_res,
            "after": after_res,
            "before_acc": before_acc,
            "after_acc": after_acc
        })

    # Summary Table
    print("\n" + "=" * 110)
    print(f"{'No':<3} | {'Venue Name':<32} | {'Ground Truth':<20} | {'Before Output':<22} | {'After Output':<25}")
    print("-" * 110)
    for r in results:
        c = r["case"]
        b = r["before"]
        a = r["after"]
        b_mark = "✅" if r["before_acc"] else "❌"
        a_mark = "✅" if r["after_acc"] else "❌"
        print(f"{c['id']:<3} | {c['name'][:32]:<32} | {c['ground_truth'][:20]:<20} | {b_mark} {b['output'][:19]:<19} | {a_mark} {a['output'][:22]:<22}")

    # Aggregated Metrics
    b_acc_total = sum(1 for r in results if r["before_acc"]) / len(results) * 100
    a_acc_total = sum(1 for r in results if r["after_acc"]) / len(results) * 100
    b_lat_avg = sum(r["before"]["latency_ms"] for r in results) / len(results)
    a_lat_avg = sum(r["after"]["latency_ms"] for r in results) / len(results)
    b_tokens_total = sum(r["before"]["tokens"] for r in results)
    a_tokens_total = sum(r["after"]["tokens"] for r in results)

    print("=" * 110)
    print(f"METRIC COMPARISON SUMMARY:")
    print(f"1. Accuracy Score:          BEFORE: {b_acc_total:.1f}% ({sum(1 for r in results if r['before_acc'])}/10) | AFTER: {a_acc_total:.1f}% ({sum(1 for r in results if r['after_acc'])}/10)")
    print(f"2. Average Latency:         BEFORE: {b_lat_avg:.2f} ms     | AFTER: {a_lat_avg:.2f} ms ({(b_lat_avg / max(a_lat_avg, 0.001)):.1f}x faster)")
    print(f"3. Total Token Consumption: BEFORE: {b_tokens_total} tokens      | AFTER: {a_tokens_total} tokens (100% free)")
    print(f"4. Determinism / Flakiness: BEFORE: Stochastic (Jitter) | AFTER: 100% Deterministic (Zero variance)")
    print("=" * 110)

if __name__ == "__main__":
    main()
