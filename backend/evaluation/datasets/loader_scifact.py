"""
AllenAI SciFact Dataset Loader & Processor
Loads official claims and corpus from AllenAI SciFact (EMNLP 2020)
Generates curated 10-case fact-checking benchmark with balanced SUPPORT and CONTRADICT labels.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any

DATASETS_DIR = Path(__file__).resolve().parent
SCIFACT_RAW_DIR = DATASETS_DIR / "scifact" / "data"
PAPERS_DIR = DATASETS_DIR / "qasper_papers"


def build_scifact_benchmark(num_support: int = 5, num_contradict: int = 5) -> List[Dict[str, Any]]:
    """Curates balanced SciFact claims and writes paper abstracts to text files."""
    corpus_path = SCIFACT_RAW_DIR / "corpus.jsonl"
    claims_path = SCIFACT_RAW_DIR / "claims_dev.jsonl"

    if not corpus_path.exists() or not claims_path.exists():
        raise FileNotFoundError(f"SciFact raw data not found under {SCIFACT_RAW_DIR}")

    corpus: Dict[str, Any] = {}
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            corpus[str(d["doc_id"])] = d

    support_cases: List[Dict[str, Any]] = []
    contradict_cases: List[Dict[str, Any]] = []

    with open(claims_path, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if not c.get("evidence"):
                continue

            doc_id_str = list(c["evidence"].keys())[0]
            evidence_entries = c["evidence"][doc_id_str]
            if not evidence_entries:
                continue

            ev = evidence_entries[0]
            label = ev.get("label", "")
            if str(doc_id_str) not in corpus:
                continue

            doc_info = corpus[str(doc_id_str)]
            abstract_sentences = doc_info.get("abstract", [])
            evidence_text_list = [
                abstract_sentences[idx]
                for idx in ev.get("sentences", [])
                if idx < len(abstract_sentences)
            ]
            evidence_str = " ".join(evidence_text_list)

            # Write physical paper file if not already present
            paper_fname = f"scifact_{doc_id_str}.txt"
            paper_fpath = PAPERS_DIR / paper_fname
            if not paper_fpath.exists():
                with open(paper_fpath, "w", encoding="utf-8") as pf:
                    pf.write(f"# {doc_info['title']}\n\n")
                    pf.write("## Abstract\n\n")
                    pf.write(" ".join(abstract_sentences) + "\n")

            verdict_text = "SUPPORTS" if label == "SUPPORT" else "CONTRADICTS"
            gt_text = (
                f"The literature {verdict_text} this claim. "
                f"Evidence: {evidence_str}"
            )

            case_item = {
                "id": f"SCIFACT-{c['id']:04d}",
                "category": "scientific_fact_checking",
                "title": doc_info["title"],
                "query": f"Evaluate the following scientific claim based on the literature: \"{c['claim']}\"",
                "raw_claim": c["claim"],
                "claim_label": label,
                "chat_id": "fa005a59-540e-405d-8029-b7c2002b4fd4",
                "target_documents": [paper_fname],
                "ground_truth": gt_text,
                "key_entities": [verdict_text] + evidence_text_list[:2]
            }

            if label == "SUPPORT" and len(support_cases) < num_support:
                support_cases.append(case_item)
            elif label == "CONTRADICT" and len(contradict_cases) < num_contradict:
                contradict_cases.append(case_item)

            if len(support_cases) >= num_support and len(contradict_cases) >= num_contradict:
                break

    all_cases = support_cases + contradict_cases
    out_file = DATASETS_DIR / "international_scifact.json"
    with open(out_file, "w", encoding="utf-8") as out:
        json.dump(all_cases, out, indent=2, ensure_ascii=False)

    print(f"[SciFact Loader] Generated {len(all_cases)} curated fact-checking cases -> {out_file.name}")
    return all_cases


if __name__ == "__main__":
    cases = build_scifact_benchmark(5, 5)
    for c in cases:
        print(f"[{c['id']}] ({c['claim_label']}) {c['query'][:75]}...")
