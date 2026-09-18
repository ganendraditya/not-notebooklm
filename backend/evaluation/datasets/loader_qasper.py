"""
Loader for the official AllenAI QASPER (Question Answering on Scientific Papers) dataset.
Extracts exactly 25 Validation cases + 25 Test cases (50 total) across diverse arXiv papers with full text.
"""

import os
import re
import json
import shutil
import urllib.request
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger("qasper_loader")

DATASETS_DIR = Path(__file__).resolve().parent
QASPER_PAPERS_DIR = DATASETS_DIR / "qasper_papers"
QASPER_PAPERS_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_DIR = DATASETS_DIR.parent.parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_COMBINED_FILE = DATASETS_DIR / "international_qasper.json"
OUTPUT_VAL_FILE = DATASETS_DIR / "international_qasper_val.json"
OUTPUT_TEST_FILE = DATASETS_DIR / "international_qasper_test.json"


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


def fetch_split_cases(split_name: str, target_count: int = 25) -> List[Dict[str, Any]]:
    """Fetches and extracts exact target_count cases from the given QASPER split."""
    print(f"Fetching {split_name} split from AllenAI QASPER...")
    api_url = f"https://datasets-server.huggingface.co/rows?dataset=allenai/qasper&config=qasper&split={split_name}&offset=0&limit=30"
    
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        rows = data.get("rows", [])

    benchmark_cases = []

    for r in rows:
        row = r["row"]
        pid = row.get("id")
        title = row.get("title", "")
        paper_filename = f"qasper_{pid}.txt"
        paper_path = QASPER_PAPERS_DIR / paper_filename
        
        # Save paper text to markdown file if not already saved
        if not paper_path.exists():
            md_text = format_full_paper_markdown(row)
            with open(paper_path, "w", encoding="utf-8") as pf:
                pf.write(md_text)

        # Ensure present in uploads directory
        upload_dest = UPLOADS_DIR / paper_filename
        if not upload_dest.exists() and paper_path.exists():
            shutil.copyfile(paper_path, upload_dest)

        qas = row.get("qas", {})
        questions = qas.get("question", [])
        answers_list = qas.get("answers", [])

        for q_idx, (q, ans_obj) in enumerate(zip(questions, answers_list)):
            answers = ans_obj.get("answer", [])
            if not answers:
                continue
            
            first_ans = answers[0]
            is_unanswerable = bool(first_ans.get("unanswerable", False))
            
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

            case_id = f"QASPER-{split_name.upper()[:3]}-{pid.replace('.', '_')}-{q_idx+1:02d}"
            category = "negative_unanswerable" if is_unanswerable else "single_fact"

            benchmark_cases.append({
                "id": case_id,
                "dataset": "allenai/qasper",
                "split": split_name,
                "paper_id": pid,
                "paper_title": title,
                "category": category,
                "query": q.strip(),
                "target_documents": [paper_filename],
                "ground_truth": gt_text,
                "evidence_spans": clean_evidence,
                "unanswerable": is_unanswerable
            })

            if len(benchmark_cases) >= target_count:
                break
        
        if len(benchmark_cases) >= target_count:
            break

    return benchmark_cases[:target_count]


def main():
    val_cases = fetch_split_cases("validation", target_count=25)
    test_cases = fetch_split_cases("test", target_count=25)

    with open(OUTPUT_VAL_FILE, "w", encoding="utf-8") as f:
        json.dump(val_cases, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_TEST_FILE, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2, ensure_ascii=False)

    combined_cases = val_cases + test_cases
    with open(OUTPUT_COMBINED_FILE, "w", encoding="utf-8") as f:
        json.dump(combined_cases, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved 25 validation cases to: {OUTPUT_VAL_FILE}")
    print(f"✓ Saved 25 test cases to: {OUTPUT_TEST_FILE}")
    print(f"✓ Saved 50 total combined cases to: {OUTPUT_COMBINED_FILE}")


if __name__ == "__main__":
    main()
