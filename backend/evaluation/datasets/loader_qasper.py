"""
Loader for the official AllenAI QASPER (Question Answering on Scientific Papers) dataset.
Extracts representative research paper QA pairs and converts full papers into markdown.
"""

import os
import re
import json
import urllib.request
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger("qasper_loader")

DATASETS_DIR = Path(__file__).resolve().parent
QASPER_PAPERS_DIR = DATASETS_DIR / "qasper_papers"
QASPER_PAPERS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_BENCHMARK_FILE = DATASETS_DIR / "international_qasper.json"

# Selected high-quality paper IDs from QASPER validation split
TARGET_PAPER_IDS = [
    "1801.05147",  # Adversarial Learning for Chinese NER from Crowd Annotations (Fact + Unanswerable)
    "1909.00512",  # Geometry of BERT, ELMo, and GPT-2 Embeddings (Representations & Math)
    "1909.02027",  # Intent Classification & Out-of-Scope Prediction (Classifiers & Benchmarks)
    "1805.08241",  # Sparse and Constrained Attention for NMT (Attention Mechanisms)
]


def format_full_paper_markdown(row: Dict[str, Any]) -> str:
    """Converts QASPER full_text structured dict into clean academic Markdown."""
    lines = []
    lines.append(f"# {row.get('title', 'Academic Paper')}\n")
    lines.append("## Abstract\n")
    lines.append(row.get("abstract", "").strip() + "\n")

    full_text = row.get("full_text", {})
    section_names = full_text.get("section_name", [])
    paragraphs_list = full_text.get("paragraphs", [])

    for sec_name, paras in zip(section_names, paragraphs_list):
        clean_sec = re.sub(r'^:::+\s*', '', sec_name.strip())
        clean_sec = re.sub(r':::', ' - ', clean_sec)
        lines.append(f"## {clean_sec}\n")
        for p in paras:
            p_clean = p.strip()
            if p_clean:
                lines.append(p_clean + "\n")

    return "\n".join(lines)


def fetch_and_build_qasper_benchmark(max_samples: int = 8) -> Path:
    """Fetches official rows from Hugging Face dataset server and builds the benchmark JSON."""
    logger.info("Fetching validation split from AllenAI QASPER...")
    api_url = "https://datasets-server.huggingface.co/rows?dataset=allenai/qasper&config=qasper&split=validation&offset=0&limit=30"
    
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        rows = data.get("rows", [])

    benchmark_cases = []
    saved_papers = {}

    for r in rows:
        row = r["row"]
        pid = row.get("id")
        if pid not in TARGET_PAPER_IDS:
            continue

        title = row.get("title", "")
        # Save paper text to markdown file
        paper_filename = f"qasper_{pid}.txt"
        paper_path = QASPER_PAPERS_DIR / paper_filename
        
        md_text = format_full_paper_markdown(row)
        with open(paper_path, "w", encoding="utf-8") as pf:
            pf.write(md_text)
        saved_papers[pid] = paper_filename

        qas = row.get("qas", {})
        questions = qas.get("question", [])
        answers_list = qas.get("answers", [])

        for q_idx, (q, ans_obj) in enumerate(zip(questions, answers_list)):
            answers = ans_obj.get("answer", [])
            if not answers:
                continue
            
            first_ans = answers[0]
            is_unanswerable = bool(first_ans.get("unanswerable", False))
            
            # Extract ground truth text
            gt_text = ""
            if is_unanswerable:
                gt_text = "This information is not mentioned or provided in the paper."
            elif first_ans.get("free_form_answer"):
                gt_text = first_ans["free_form_answer"].strip()
            elif first_ans.get("extractive_spans"):
                gt_text = ", ".join(first_ans["extractive_spans"]).strip()
            elif first_ans.get("yes_no") is not None:
                gt_text = "Yes" if first_ans["yes_no"] else "No"
            
            evidence_sentences = first_ans.get("evidence", []) or first_ans.get("highlighted_evidence", [])
            clean_evidence = [e.strip() for e in evidence_sentences if e.strip()]

            if not gt_text:
                continue

            case_id = f"QASPER-{pid.replace('.', '_')}-{q_idx+1:02d}"
            category = "negative_unanswerable" if is_unanswerable else "single_fact"

            benchmark_cases.append({
                "id": case_id,
                "dataset": "allenai/qasper",
                "paper_id": pid,
                "paper_title": title,
                "category": category,
                "query": q.strip(),
                "target_documents": [paper_filename],
                "ground_truth": gt_text,
                "evidence_spans": clean_evidence,
                "unanswerable": is_unanswerable
            })

            if len(benchmark_cases) >= max_samples:
                break
        
        if len(benchmark_cases) >= max_samples:
            break

    with open(OUTPUT_BENCHMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_cases, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(benchmark_cases)} official QASPER benchmark cases to: {OUTPUT_BENCHMARK_FILE}")
    print(f"✓ Saved {len(saved_papers)} paper text files to: {QASPER_PAPERS_DIR}")
    return OUTPUT_BENCHMARK_FILE


if __name__ == "__main__":
    fetch_and_build_qasper_benchmark()
