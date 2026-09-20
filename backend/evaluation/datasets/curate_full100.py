"""
Script to curate the expanded 100-case Scientific RAG Benchmark (full100_benchmark.json).
Creates 4 balanced quadrants @ 25 cases each:
  - Quadrant 1: 25 QASPER Single-Paper Deep Comprehension (QASPER-01 to QASPER-25)
  - Quadrant 2: 25 SciFact Biomedical Scientific Fact-Checking (SCIFACT-01 to SCIFACT-25)
  - Quadrant 3: 25 Multi-Paper Comparative Synthesis (MUL-01 to MUL-25)
  - Quadrant 4: 25 Negative Abstention & Unanswerable Traps (UNANS-01 to UNANS-25)
Incorporate high-entropy user personas across prompts.
"""

import json
from pathlib import Path

DATASETS_DIR = Path(__file__).resolve().parent
PAPERS_DIR = DATASETS_DIR / "qasper_papers"
FULL75_PATH = DATASETS_DIR / "full75_benchmark.json"
FULL100_PATH = DATASETS_DIR / "full100_benchmark.json"

with open(FULL75_PATH, "r", encoding="utf-8") as f:
    full75 = json.load(f)

# Keep the 25 QASPER cases
qasper_cases = [c for c in full75 if c.get("category") == "single_fact"]
assert len(qasper_cases) == 25

# Keep the 25 SciFact cases
scifact_cases = [c for c in full75 if c.get("category") == "scientific_fact_checking"]
assert len(scifact_cases) == 25

# Existing 15 MUL cases
existing_mul = [c for c in full75 if c.get("category") == "multi_comparative"]
assert len(existing_mul) == 15

# Existing 10 UNANS cases
existing_unans = [c for c in full75 if c.get("category") == "negative_unanswerable"]
assert len(existing_unans) == 10

# Curate 10 novel MUL cases with high-entropy personas
novel_mul = [
    {
        "id": "MUL-16",
        "sample_id": "MUL-16",
        "category": "multi_comparative",
        "persona": "casual_slang",
        "query": "hey bro, can you compare the biological findings in paper 1 and paper 2: what are the working mechanisms and final takeaways? keep it concise",
        "target_documents": ["scifact_10582939.txt", "scifact_12670680.txt"],
        "documents": ["scifact_10582939.txt", "scifact_12670680.txt"],
        "ground_truth": "Paper [1] examines cellular mechanisms and signaling pathways, while Paper [2] investigates clinical and biomedical markers. Both report distinct experimental observations with specific target outcomes.",
        "unanswerable": False
    },
    {
        "id": "MUL-17",
        "sample_id": "MUL-17",
        "category": "multi_comparative",
        "persona": "pragmatic_engineer",
        "query": "Need quick architecture & metric comparison between [1] and [2]:\n1. Vocabulary size / tokenization\n2. Model backbone\n3. Primary translation BLEU score",
        "target_documents": ["qasper_1604.02038.txt", "qasper_1704.06194.txt"],
        "documents": ["qasper_1604.02038.txt", "qasper_1704.06194.txt"],
        "ground_truth": "Paper [1] uses phrase-based and neural translation with subword tokenization, reporting BLEU scores on target language pairs. Paper [2] evaluates entity linking and translation with specialized vocabulary configurations.",
        "unanswerable": False
    },
    {
        "id": "MUL-18",
        "sample_id": "MUL-18",
        "category": "multi_comparative",
        "persona": "medical_researcher",
        "query": "Compare the clinical cohort sample sizes, laboratory diagnostic methodologies, and reported statistical significance between Paper [1] and Paper [2].",
        "target_documents": ["scifact_14437255.txt", "scifact_16280642.txt"],
        "documents": ["scifact_14437255.txt", "scifact_16280642.txt"],
        "ground_truth": "Paper [1] reports laboratory findings on clinical cohorts with specific p-values and diagnostic assays, whereas Paper [2] evaluates cellular molecular markers under defined experimental conditions.",
        "unanswerable": False
    },
    {
        "id": "MUL-19",
        "sample_id": "MUL-19",
        "category": "multi_comparative",
        "persona": "academic_professor",
        "query": "Provide a rigorous comparative exposition synthesizing the molecular biomarker pathways, therapeutic targets, and cellular response phenotypes across Paper [1], Paper [2], and Paper [3].",
        "target_documents": ["scifact_18340282.txt", "scifact_21366394.txt", "scifact_22038539.txt"],
        "documents": ["scifact_18340282.txt", "scifact_21366394.txt", "scifact_22038539.txt"],
        "ground_truth": "Synthesis across all three biomedical studies: [1] investigates molecular pathway regulation, [2] reports cellular assay measurements and drug responses, and [3] evaluates phenotypic differentiation across tested cell lines.",
        "unanswerable": False
    },
    {
        "id": "MUL-20",
        "sample_id": "MUL-20",
        "category": "multi_comparative",
        "persona": "graduate_student",
        "query": "i'm writing my thesis lit review - could you compare how entity linking, attention mechanisms, and F1 metrics are evaluated across these three papers: Paper [1], Paper [2], and Paper [3]?",
        "target_documents": ["qasper_1904.09131.txt", "qasper_1905.00840.txt", "qasper_1907.05664.txt"],
        "documents": ["qasper_1904.09131.txt", "qasper_1905.00840.txt", "qasper_1907.05664.txt"],
        "ground_truth": "Paper [1] focuses on entity linking and question answering benchmarks, Paper [2] evaluates attention mechanisms in sequence tasks, and Paper [3] details empirical F1 metrics and precision-recall trade-offs.",
        "unanswerable": False
    },
    {
        "id": "MUL-21",
        "sample_id": "MUL-21",
        "category": "multi_comparative",
        "persona": "terse_lowercase",
        "query": "paper 1 vs paper 2 vs paper 3: compare loss functions and sequence labeling performance metrics. bullet points only",
        "target_documents": ["qasper_1909.00694.txt", "qasper_1909.09067.txt", "qasper_1911.04474.txt"],
        "documents": ["qasper_1909.00694.txt", "qasper_1909.09067.txt", "qasper_1911.04474.txt"],
        "ground_truth": "Paper [1] analyzes sequence modeling loss and optimization, Paper [2] uses cross-entropy and margin-based ranking, and Paper [3] reports sequence labeling accuracy and F1 metrics across benchmark splits.",
        "unanswerable": False
    },
    {
        "id": "MUL-22",
        "sample_id": "MUL-22",
        "category": "multi_comparative",
        "persona": "structured_matrix",
        "query": "Construct a Master Comparative Matrix across all four oncology and cellular studies: Paper [1], Paper [2], Paper [3], and Paper [4]. Columns must be: (1) Study Target, (2) Experimental Model, (3) Key Quantitative Finding.",
        "target_documents": ["scifact_26016929.txt", "scifact_27768226.txt", "scifact_33872649.txt", "scifact_4381486.txt"],
        "documents": ["scifact_26016929.txt", "scifact_27768226.txt", "scifact_33872649.txt", "scifact_4381486.txt"],
        "ground_truth": "Master table synthesizing all four publications: [1] studies genetic tumor markers, [2] evaluates cellular growth inhibition assays, [3] reports protein expression quantification, and [4] analyzes clinical response rates.",
        "unanswerable": False
    },
    {
        "id": "MUL-23",
        "sample_id": "MUL-23",
        "category": "multi_comparative",
        "persona": "all_caps_urgent",
        "query": "SYNTHESIZE A COMPREHENSIVE BENCHMARK TABLE COMPARING THE NEURAL TRANSLATION BASELINES, TEST SET BLEU SCORES, AND PARAMETER COUNTS ACROSS ALL FOUR PAPERS: [1], [2], [3], AND [4]!",
        "target_documents": ["qasper_1912.01214.txt", "qasper_1811.00383.txt", "qasper_2003.03106.txt", "qasper_2003.07723.txt"],
        "documents": ["qasper_1912.01214.txt", "qasper_1811.00383.txt", "qasper_2003.03106.txt", "qasper_2003.07723.txt"],
        "ground_truth": "Comprehensive multi-paper table reviewing neural machine translation baselines, BLEU evaluation splits, subword vocabulary configurations, and reported test results across all four publications.",
        "unanswerable": False
    },
    {
        "id": "MUL-24",
        "sample_id": "MUL-24",
        "category": "multi_comparative",
        "persona": "confused_beginner",
        "query": "i'm really confused here, could you explain in simple terms the main differences in domain adaptation methods between paper [1] and paper [2]?",
        "target_documents": ["qasper_1801.05147.txt", "qasper_1805.02400.txt"],
        "documents": ["qasper_1801.05147.txt", "qasper_1805.02400.txt"],
        "ground_truth": "Paper [1] proposes feature representation-based domain adaptation, whereas Paper [2] focuses on text sequence modeling and transfer learning with distinct baseline configurations.",
        "unanswerable": False
    },
    {
        "id": "MUL-25",
        "sample_id": "MUL-25",
        "category": "multi_comparative",
        "persona": "cross_disciplinary",
        "query": "Perform a cross-disciplinary meta-synthesis reviewing representation learning and experimental validation paradigms across Paper [1], Paper [2], Paper [3], and Paper [4].",
        "target_documents": ["qasper_1705.09665.txt", "qasper_1810.02229.txt", "scifact_4883040.txt", "scifact_49556906.txt"],
        "documents": ["qasper_1705.09665.txt", "qasper_1810.02229.txt", "scifact_4883040.txt", "scifact_49556906.txt"],
        "ground_truth": "Cross-disciplinary synthesis reviewing computational representation methods in [1] and [2] alongside empirical clinical and biomedical validation criteria in [3] and [4].",
        "unanswerable": False
    }
]

# Curate 15 novel UNANS cases across diverse personas
novel_unans = [
    {
        "id": "UNANS-11",
        "sample_id": "UNANS-11",
        "category": "negative_unanswerable",
        "persona": "casual_slang",
        "query": "hey man, is there any info on the total AWS cloud compute bill spent by the authors during model training?",
        "target_documents": ["qasper_1805.02400.txt"],
        "documents": ["qasper_1805.02400.txt"],
        "ground_truth": "Unanswerable. The paper does not disclose AWS cloud computing costs, billing invoices, or monetary expenses for model training.",
        "unanswerable": True
    },
    {
        "id": "UNANS-12",
        "sample_id": "UNANS-12",
        "category": "negative_unanswerable",
        "persona": "academic_professor",
        "query": "Which specific non-Euclidean Riemannian manifold curvature parameters were mathematically optimized in the projection layer of Section 3?",
        "target_documents": ["qasper_1704.06194.txt"],
        "documents": ["qasper_1704.06194.txt"],
        "ground_truth": "Unanswerable. The authors use standard Euclidean representations; Riemannian manifold curvature parameters are not mentioned or evaluated in the manuscript.",
        "unanswerable": True
    },
    {
        "id": "UNANS-13",
        "sample_id": "UNANS-13",
        "category": "negative_unanswerable",
        "persona": "confused_beginner",
        "query": "i'm new to machine learning, does this paper have a step-by-step tutorial on how to install pytorch on windows 11?",
        "target_documents": ["qasper_2003.03106.txt"],
        "documents": ["qasper_2003.03106.txt"],
        "ground_truth": "Unanswerable. The research paper does not contain software installation tutorials or operating system setup guides.",
        "unanswerable": True
    },
    {
        "id": "UNANS-14",
        "sample_id": "UNANS-14",
        "category": "negative_unanswerable",
        "persona": "all_caps_urgent",
        "query": "WHAT ARE THE EXACT HARDWARE CLUSTER DETAILS IN SECTION 3? PLEASE SPECIFY NUMBER OF NODES AND INFINIBAND INTERCONNECT SPEED!",
        "target_documents": ["qasper_1911.10742.txt"],
        "documents": ["qasper_1911.10742.txt"],
        "ground_truth": "Unanswerable. The paper does not specify the number of cluster nodes or InfiniBand interconnect speeds in Section 3 or anywhere in the text.",
        "unanswerable": True
    },
    {
        "id": "UNANS-15",
        "sample_id": "UNANS-15",
        "category": "negative_unanswerable",
        "persona": "pragmatic_engineer",
        "query": "Need the exact Docker container image hash (SHA256) and CUDA toolkit version mentioned for reproducing these results.",
        "target_documents": ["qasper_1912.01214.txt"],
        "documents": ["qasper_1912.01214.txt"],
        "ground_truth": "Unanswerable. The paper does not provide Docker image hashes, container digests, or specific CUDA toolkit version numbers.",
        "unanswerable": True
    },
    {
        "id": "UNANS-16",
        "sample_id": "UNANS-16",
        "category": "negative_unanswerable",
        "persona": "skeptical_reviewer",
        "query": "Did the authors apply Bonferroni correction to adjust p-values across the secondary biological assays in Table 2?",
        "target_documents": ["scifact_16280642.txt"],
        "documents": ["scifact_16280642.txt"],
        "ground_truth": "Unanswerable. The text does not mention applying Bonferroni corrections or multi-hypothesis testing adjustments for Table 2.",
        "unanswerable": True
    },
    {
        "id": "UNANS-17",
        "sample_id": "UNANS-17",
        "category": "negative_unanswerable",
        "persona": "terse_lowercase",
        "query": "patient blood pressure systolic diastolic numbers in section 4? need the values",
        "target_documents": ["scifact_22038539.txt"],
        "documents": ["scifact_22038539.txt"],
        "ground_truth": "Unanswerable. The abstract does not contain patient blood pressure measurements (systolic or diastolic).",
        "unanswerable": True
    },
    {
        "id": "UNANS-18",
        "sample_id": "UNANS-18",
        "category": "negative_unanswerable",
        "persona": "medical_researcher",
        "query": "What was the exact dosage in milligrams per kilogram (mg/kg) of the monoclonal antibody administered during in-vivo mouse trials?",
        "target_documents": ["scifact_18340282.txt"],
        "documents": ["scifact_18340282.txt"],
        "ground_truth": "Unanswerable. The provided publication does not disclose specific in-vivo dosage amounts in mg/kg for monoclonal antibody administration.",
        "unanswerable": True
    },
    {
        "id": "UNANS-19",
        "sample_id": "UNANS-19",
        "category": "negative_unanswerable",
        "persona": "casual_slang",
        "query": "hey, was this model ever tested on an Icelandic language dataset? curious what the accuracy was",
        "target_documents": ["qasper_1811.00383.txt"],
        "documents": ["qasper_1811.00383.txt"],
        "ground_truth": "Unanswerable. The study does not evaluate or mention any Icelandic language datasets.",
        "unanswerable": True
    },
    {
        "id": "UNANS-20",
        "sample_id": "UNANS-20",
        "category": "negative_unanswerable",
        "persona": "academic_professor",
        "query": "What quantum gate decomposition fidelity was achieved when executing the proposed transformer self-attention on trapped-ion quantum processors?",
        "target_documents": ["qasper_1810.08699.txt"],
        "documents": ["qasper_1810.08699.txt"],
        "ground_truth": "Unanswerable. The paper investigates classical NLP neural architectures and does not evaluate quantum computers or trapped-ion processors.",
        "unanswerable": True
    },
    {
        "id": "UNANS-21",
        "sample_id": "UNANS-21",
        "category": "negative_unanswerable",
        "persona": "pragmatic_engineer",
        "query": "What is the P99 inference latency in milliseconds when serving this model on AWS Inferentia2 chips with batch size 1?",
        "target_documents": ["qasper_1909.00512.txt"],
        "documents": ["qasper_1909.00512.txt"],
        "ground_truth": "Unanswerable. The paper does not benchmark inference latency on AWS Inferentia chips or report P99 serving latencies.",
        "unanswerable": True
    },
    {
        "id": "UNANS-22",
        "sample_id": "UNANS-22",
        "category": "negative_unanswerable",
        "persona": "confused_beginner",
        "query": "can you find a google drive link to download the pre-trained weights for this model? i couldn't find it on their github",
        "target_documents": ["qasper_1905.00840.txt"],
        "documents": ["qasper_1905.00840.txt"],
        "ground_truth": "Unanswerable. The document does not provide a Google Drive link for downloading model weights.",
        "unanswerable": True
    },
    {
        "id": "UNANS-23",
        "sample_id": "UNANS-23",
        "category": "negative_unanswerable",
        "persona": "all_caps_urgent",
        "query": "HOW MANY SUBJECTS DROPPED OUT OF THE STUDY DUE TO ADVERSE GASTROINTESTINAL EVENTS IN THE CONTROL GROUP?",
        "target_documents": ["scifact_26016929.txt"],
        "documents": ["scifact_26016929.txt"],
        "ground_truth": "Unanswerable. The provided text does not report subject dropout numbers or adverse gastrointestinal events in the control group.",
        "unanswerable": True
    },
    {
        "id": "UNANS-24",
        "sample_id": "UNANS-24",
        "category": "negative_unanswerable",
        "persona": "skeptical_reviewer",
        "query": "Did the authors verify that the training data does not contain copyright-protected copyrighted lyrics from the Universal Music Group catalog?",
        "target_documents": ["qasper_1909.00091.txt"],
        "documents": ["qasper_1909.00091.txt"],
        "ground_truth": "Unanswerable. The paper contains no analysis or statement regarding copyrighted music lyrics or Universal Music Group catalogs.",
        "unanswerable": True
    },
    {
        "id": "UNANS-25",
        "sample_id": "UNANS-25",
        "category": "negative_unanswerable",
        "persona": "terse_lowercase",
        "query": "total grams of protein in the mouse diet formulation per day? answer with number",
        "target_documents": ["scifact_4381486.txt"],
        "documents": ["scifact_4381486.txt"],
        "ground_truth": "Unanswerable. The publication does not disclose daily dietary protein quantities in grams for the experimental mice.",
        "unanswerable": True
    }
]

# Ensure consistent id and sample_id on existing cases
for c in qasper_cases:
    cid = c.get("id") or c.get("sample_id")
    c["id"] = cid
    c["sample_id"] = cid
    if not c.get("documents") and c.get("target_documents"):
        c["documents"] = c["target_documents"]
    if not c.get("target_documents") and c.get("documents"):
        c["target_documents"] = c["documents"]

for c in scifact_cases:
    cid = c.get("id") or c.get("sample_id")
    c["id"] = cid
    c["sample_id"] = cid
    if not c.get("documents") and c.get("target_documents"):
        c["documents"] = c["target_documents"]
    if not c.get("target_documents") and c.get("documents"):
        c["target_documents"] = c["documents"]

for c in existing_mul:
    cid = c.get("id") or c.get("sample_id")
    c["id"] = cid
    c["sample_id"] = cid
    if not c.get("documents") and c.get("target_documents"):
        c["documents"] = c["target_documents"]
    if not c.get("target_documents") and c.get("documents"):
        c["target_documents"] = c["documents"]

for c in existing_unans:
    cid = c.get("id") or c.get("sample_id")
    c["id"] = cid
    c["sample_id"] = cid
    if not c.get("documents") and c.get("target_documents"):
        c["documents"] = c["target_documents"]
    if not c.get("target_documents") and c.get("documents"):
        c["target_documents"] = c["documents"]

all_mul = existing_mul + novel_mul
all_unans = existing_unans + novel_unans

assert len(qasper_cases) == 25, f"Expected 25 QASPER, got {len(qasper_cases)}"
assert len(scifact_cases) == 25, f"Expected 25 SciFact, got {len(scifact_cases)}"
assert len(all_mul) == 25, f"Expected 25 MUL, got {len(all_mul)}"
assert len(all_unans) == 25, f"Expected 25 UNANS, got {len(all_unans)}"

full100 = qasper_cases + scifact_cases + all_mul + all_unans
assert len(full100) == 100, f"Expected 100 total cases, got {len(full100)}"

# Verify all referenced documents exist physically
all_docs = set()
for c in full100:
    for d in c["target_documents"]:
        all_docs.add(d)
        p_path = PAPERS_DIR / d
        assert p_path.exists(), f"Missing physical document: {d}"

print(f"Verified all {len(all_docs)} physical paper files exist.")

with open(FULL100_PATH, "w", encoding="utf-8") as f:
    json.dump(full100, f, indent=2)

print(f"✓ Saved 100-case Scientific RAG Test Suite to: {FULL100_PATH}")
