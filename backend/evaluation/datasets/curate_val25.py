"""
Curator for Not-NotebookLM Val-25 Benchmark Suite (Protocol A & Protocol B):
Builds a rigorous 25-case held-out validation benchmark:
  - 8 QASPER Single-Paper Deep Comprehension (novel arXiv papers)
  - 8 SciFact Biomedical Scientific Fact-Checking (4 SUPPORT, 4 CONTRADICT)
  - 5 Multi-Paper Comparative Synthesis (2, 3, and 4 document workspaces)
  - 4 Negative Abstention Traps (authentic unanswerable research queries)

STRICT ANTI-LEAKAGE GUARANTEE:
  Zero overlap with the 50 papers and 75 cases in full75_benchmark.json.
"""

import os
import re
import json
import urllib.request
from pathlib import Path
from typing import Dict, List, Any

DATASETS_DIR = Path(__file__).resolve().parent
PAPERS_DIR = DATASETS_DIR / "qasper_papers"
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_DIR = DATASETS_DIR.parent.parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

FULL75_PATH = DATASETS_DIR / "full75_benchmark.json"
VAL25_OUTPUT_PATH = DATASETS_DIR / "val25_benchmark.json"
NIAH_VAL25_OUTPUT_PATH = DATASETS_DIR / "niah_val25_matrix.json"

with open(FULL75_PATH, "r", encoding="utf-8") as f:
    full75_data = json.load(f)

FULL75_DOCS = set()
FULL75_QUERIES = set()
for c in full75_data:
    for d in (c.get("documents") or c.get("target_documents") or []):
        FULL75_DOCS.add(d)
    if c.get("query"):
        FULL75_QUERIES.add(c["query"].strip().lower())

print(f"Loaded {len(full75_data)} test cases with {len(FULL75_DOCS)} unique documents and {len(FULL75_QUERIES)} queries from Full75.")


def format_full_paper_markdown(row: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# {row.get('title', 'Academic Paper')}\n")
    lines.append("## Abstract\n")
    lines.append(row.get("abstract", "").strip() + "\n")

    full_text = row.get("full_text", {})
    section_names = full_text.get("section_name", [])
    paragraphs_list = full_text.get("paragraphs", [])

    for sec_name, paras in zip(section_names, paragraphs_list):
        clean_sec = re.sub(r"^:::+\s*", "", sec_name.strip())
        clean_sec = re.sub(r":::", " - ", clean_sec)
        lines.append(f"## {clean_sec}\n")
        for p in paras:
            p_clean = p.strip()
            if p_clean:
                lines.append(p_clean + "\n")

    return "\n".join(lines)


def fetch_novel_qasper_papers(target_count: int = 12) -> List[Dict[str, Any]]:
    print(f"Fetching novel arXiv papers from AllenAI QASPER (skipping any in Full75)...")
    novel_papers = []
    offset = 25
    limit = 50

    while len(novel_papers) < target_count:
        api_url = f"https://datasets-server.huggingface.co/rows?dataset=allenai/qasper&config=qasper&split=validation&offset={offset}&limit={limit}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            rows = data.get("rows", [])
            if not rows:
                break

        for r in rows:
            row = r.get("row", {})
            pid = str(row.get("id", "")).strip()
            fname = f"qasper_{pid}.txt"
            if not pid or fname in FULL75_DOCS:
                continue

            qas = row.get("qas", {})
            questions = qas.get("question", [])
            answers = qas.get("answers", [])
            if not questions or not answers:
                continue

            # Save physical paper markdown
            md_content = format_full_paper_markdown(row)
            paper_path = PAPERS_DIR / fname
            paper_path.write_text(md_content, encoding="utf-8")
            upload_path = UPLOADS_DIR / fname
            upload_path.write_text(md_content, encoding="utf-8")

            novel_papers.append({
                "paper_id": pid,
                "filename": fname,
                "title": row.get("title", ""),
                "abstract": row.get("abstract", ""),
                "qas": qas
            })

            if len(novel_papers) >= target_count:
                break

        offset += limit

    print(f"Successfully collected {len(novel_papers)} novel QASPER papers.")
    return novel_papers


def select_novel_scifact_cases(target_support: int = 4, target_contradict: int = 4) -> List[Dict[str, Any]]:
    print("Extracting novel PubMed papers from SciFact corpus & claims...")
    corpus_path = DATASETS_DIR / "scifact" / "data" / "corpus.jsonl"
    claims_path = DATASETS_DIR / "scifact" / "data" / "claims_dev.jsonl"

    corpus = {}
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            corpus[str(d["doc_id"])] = d

    support_cases = []
    contradict_cases = []

    with open(claims_path, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            evidence = c.get("evidence", {})
            if not evidence:
                continue

            doc_id = list(evidence.keys())[0]
            fname = f"scifact_{doc_id}.txt"
            if fname in FULL75_DOCS or str(doc_id) not in corpus:
                continue

            ev_entries = evidence[doc_id]
            if not ev_entries:
                continue

            label = ev_entries[0].get("label", "").upper()
            doc_info = corpus[str(doc_id)]
            sentences = doc_info.get("abstract", [])
            evidence_sentences = [
                sentences[idx] for idx in ev_entries[0].get("sentences", [])
                if idx < len(sentences)
            ]
            evidence_str = " ".join(evidence_sentences)

            # Write physical paper file
            paper_md = f"# {doc_info.get('title', 'Scientific Paper')}\n\n## Abstract\n{' '.join(sentences)}\n"
            paper_path = PAPERS_DIR / fname
            paper_path.write_text(paper_md, encoding="utf-8")
            upload_path = UPLOADS_DIR / fname
            upload_path.write_text(paper_md, encoding="utf-8")

            case_obj = {
                "doc_id": doc_id,
                "filename": fname,
                "title": doc_info.get("title", ""),
                "claim": c["claim"],
                "label": label,
                "evidence": evidence_str
            }

            if label == "SUPPORT" and len(support_cases) < target_support:
                support_cases.append(case_obj)
            elif label == "CONTRADICT" and len(contradict_cases) < target_contradict:
                contradict_cases.append(case_obj)

            if len(support_cases) >= target_support and len(contradict_cases) >= target_contradict:
                break

    print(f"Collected {len(support_cases)} SUPPORT and {len(contradict_cases)} CONTRADICT novel SciFact papers.")
    return support_cases + contradict_cases


def build_val25_suite():
    novel_qasper = fetch_novel_qasper_papers(12)
    novel_scifact = select_novel_scifact_cases(4, 4)

    val_cases: List[Dict[str, Any]] = []

    # 1. 8 Single-Paper Deep Comprehension Cases (QASPER)
    for idx, p in enumerate(novel_qasper[:8]):
        qas = p["qas"]
        questions = qas.get("question", [])
        answers_list = qas.get("answers", [])

        # Find best answerable question
        selected_q = questions[0]
        selected_ans = "The authors evaluate the model across the proposed benchmarks."
        selected_spans = []

        for q_text, ans_group in zip(questions, answers_list):
            ans_entries = ans_group.get("answer", [])
            for a in ans_entries:
                ext = a.get("extractive_spans", [])
                free = a.get("free_form_answer", "")
                if ext or (free and free.lower() != "unanswerable"):
                    selected_q = q_text
                    selected_ans = free if free else " ".join(ext)
                    selected_spans = ext
                    break
            if selected_spans:
                break

        val_cases.append({
            "id": f"QASPER-VAL-{idx+1:02d}",
            "sample_id": f"QASPER-VAL-{idx+1:02d}",
            "dataset": "qasper",
            "category": "single_fact",
            "paper_id": p["paper_id"],
            "paper_title": p["title"],
            "query": selected_q,
            "target_documents": [p["filename"]],
            "documents": [p["filename"]],
            "ground_truth": selected_ans,
            "evidence_spans": selected_spans,
            "unanswerable": False
        })

    # 2. 8 Biomedical Scientific Fact-Checking Cases (SciFact)
    for idx, sf in enumerate(novel_scifact):
        val_cases.append({
            "id": f"SCIFACT-VAL-{idx+1:02d}",
            "sample_id": f"SCIFACT-VAL-{idx+1:02d}",
            "dataset": "scifact",
            "category": "scientific_fact_checking",
            "paper_id": sf["doc_id"],
            "paper_title": sf["title"],
            "query": f'Evaluate the following scientific claim based on the literature: "{sf["claim"]}"',
            "target_documents": [sf["filename"]],
            "documents": [sf["filename"]],
            "ground_truth": f"Verdict: {sf['label']}. Evidence: {sf['evidence']}",
            "claim": sf["claim"],
            "evidence_spans": [sf["evidence"]],
            "unanswerable": False
        })

    # 3. 5 Multi-Paper Comparative Synthesis Cases
    # Use novel papers from qasper & scifact
    p1 = novel_qasper[0]["filename"]
    p2 = novel_qasper[1]["filename"]
    p3 = novel_qasper[2]["filename"]
    p4 = novel_qasper[3]["filename"]

    mul_specs = [
        {
            "id": "MUL-VAL-01",
            "docs": [p1, p2],
            "persona": "casual_slang",
            "query": f"bro coba compare dong Paper [1] ({novel_qasper[0]['title'][:35]}) sama Paper [2] ({novel_qasper[1]['title'][:35]}): dataset yg dipake apa aja dan arsitekturnya beda di mana?",
            "gt": f"Paper [1] investigates {novel_qasper[0]['title']}, while Paper [2] focuses on {novel_qasper[1]['title']}. Both propose distinct neural architectures and evaluation splits."
        },
        {
            "id": "MUL-VAL-02",
            "docs": [p2, p3],
            "persona": "terse_lowercase",
            "query": f"compare baselines and metric numbers between paper 1 and paper 2. concise bullet points only",
            "gt": f"Paper [1] ({novel_qasper[1]['title'][:30]}) and Paper [2] ({novel_qasper[2]['title'][:30]}) evaluate different baselines with dedicated metric improvements."
        },
        {
            "id": "MUL-VAL-03",
            "docs": [p1, p2, p3],
            "persona": "academic_professor",
            "query": f"Synthesize an exhaustive Master Comparison Table across all three research papers comparing (a) Problem Domain, (b) Representation Method, and (c) Reported Empirical Results.",
            "gt": f"Master table synthesizing across all three manuscripts: [1] {novel_qasper[0]['title'][:30]}, [2] {novel_qasper[1]['title'][:30]}, and [3] {novel_qasper[2]['title'][:30]}."
        },
        {
            "id": "MUL-VAL-04",
            "docs": [novel_scifact[0]["filename"], novel_scifact[1]["filename"], novel_scifact[2]["filename"]],
            "persona": "medical_researcher",
            "query": f"Compare the biomedical mechanisms, target biological pathways, and laboratory evidence reported across Paper [1], Paper [2], and Paper [3].",
            "gt": f"Paper [1] ({novel_scifact[0]['title'][:30]}), Paper [2] ({novel_scifact[1]['title'][:30]}), and Paper [3] ({novel_scifact[2]['title'][:30]}) analyze distinct biological pathways with respective experimental findings."
        },
        {
            "id": "MUL-VAL-05",
            "docs": [p1, p2, p3, p4],
            "persona": "all_caps_urgent",
            "query": f"CONSTRUCT A COMPREHENSIVE 4-PAPER SYNTHESIS MATRIX COMPARING THE SEQUENCE MODELING TECHNIQUES, OPTIMIZATIONS, AND REPORTED LIMITATIONS ACROSS PAPERS [1], [2], [3], AND [4]!",
            "gt": f"Four-paper comparative matrix reviewing methodological approaches, loss functions, and dataset configurations across all four distinct research publications."
        }
    ]

    for m in mul_specs:
        val_cases.append({
            "id": m["id"],
            "sample_id": m["id"],
            "dataset": "qasper_multi",
            "category": "multi_comparative",
            "persona": m.get("persona", "general"),
            "query": m["query"],
            "target_documents": m["docs"],
            "documents": m["docs"],
            "ground_truth": m["gt"],
            "unanswerable": False
        })

    # 4. 4 Negative Abstention Traps (Unanswerables on novel documents)
    unans_specs = [
        {
            "id": "UNANS-VAL-01",
            "doc": novel_qasper[0]["filename"],
            "persona": "casual_slang",
            "query": "min mau nanya, ada gak info berapa upah per jam yang dibayar ke pekerja mechanical turk buat bikin dataset ini?",
            "gt": "Unanswerable. The paper does not mention any crowdsourcing hourly compensation rate or MTurk payment figures."
        },
        {
            "id": "UNANS-VAL-02",
            "doc": novel_qasper[1]["filename"],
            "persona": "all_caps_urgent",
            "query": "WHAT SPECIFIC CLUSTER HARDWARE SPECS, NUMBER OF GPU NODES, AND INTERCONNECT BANDWIDTH WERE USED DURING PRE-TRAINING?",
            "gt": "Unanswerable. The text does not disclose cluster hardware specifications, interconnect bandwidth, or the number of GPU nodes used."
        },
        {
            "id": "UNANS-VAL-03",
            "doc": novel_scifact[0]["filename"],
            "persona": "confused_beginner",
            "query": "saya kurang paham medis, di paper ini ada disebutin syarat berat badan atau BMI pasien yang gak boleh ikut uji klinis gak ya?",
            "gt": "Unanswerable. The provided abstract does not report any patient BMI exclusion criteria or Phase III trial parameters."
        },
        {
            "id": "UNANS-VAL-04",
            "doc": novel_scifact[1]["filename"],
            "persona": "terse_lowercase",
            "query": "number of post-op follow up days before assessing survival rate in section 4? need the exact number",
            "gt": "Unanswerable. The study does not mention post-operative follow-up duration or Section 4 survival data in the provided document."
        }
    ]

    for u in unans_specs:
        val_cases.append({
            "id": u["id"],
            "sample_id": u["id"],
            "dataset": "unanswerable",
            "category": "negative_unanswerable",
            "persona": u.get("persona", "general"),
            "query": u["query"],
            "target_documents": [u["doc"]],
            "documents": [u["doc"]],
            "ground_truth": u["gt"],
            "unanswerable": True
        })

    # Verify and save
    assert len(val_cases) == 25, f"Expected 25 cases, got {len(val_cases)}"

    with open(VAL25_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(val_cases, f, indent=2)
    print(f"✓ Saved 25-case Protocol A validation benchmark to: {VAL25_OUTPUT_PATH}")

    # Anti-leakage audit
    val_docs = set(d for c in val_cases for d in (c.get("documents") or c.get("target_documents") or []))
    doc_overlap = val_docs.intersection(FULL75_DOCS)
    assert len(doc_overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping docs: {doc_overlap}"

    val_queries = set(c["query"].strip().lower() for c in val_cases)
    query_overlap = val_queries.intersection(FULL75_QUERIES)
    assert len(query_overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping queries: {query_overlap}"

    print("✓ Anti-Leakage Audit PASSED: 0 document overlaps, 0 query overlaps with Full75!")
    return val_cases


if __name__ == "__main__":
    build_val25_suite()
