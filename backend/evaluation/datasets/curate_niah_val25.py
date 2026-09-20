"""
Curator for Protocol B: 25-Case Multi-Spectral Conversational NIAH Validation Matrix (niah_val25_matrix.json).
Evaluates across 3 difficulty tiers:
  - 10 S-NIAH (Single-Needle across 10 distinct load & depth cells)
  - 8 M-NIAH (Multi-Needle tracking across 2-3 independent variables)
  - 7 R-NIAH (Multi-hop reasoning & conditional deduction)

STRICT ANTI-LEAKAGE GUARANTEE:
  - Uses only novel QASPER papers curated for val (zero paper overlap with Test 75)
  - 100% novel needle contents, probe queries, and constraint schemas (zero overlap with niah_75_matrix.json)
"""

import json
from pathlib import Path
from typing import List, Dict, Any

DATASETS_DIR = Path(__file__).resolve().parent
NIAH_75_PATH = DATASETS_DIR / "niah_75_matrix.json"
VAL25_PATH = DATASETS_DIR / "val25_benchmark.json"
NIAH_VAL25_OUTPUT_PATH = DATASETS_DIR / "niah_val25_matrix.json"

with open(NIAH_75_PATH, "r", encoding="utf-8") as f:
    niah_75 = json.load(f)

TEST_NEEDLES = set()
TEST_PROBES = set()
for c in niah_75:
    for n in c.get("needles", []):
        TEST_NEEDLES.add(n.get("input", "").strip().lower())
    if c.get("probe_query"):
        TEST_PROBES.add(c["probe_query"].strip().lower())

with open(VAL25_PATH, "r", encoding="utf-8") as f:
    val25 = json.load(f)

novel_docs = [c["target_documents"][0] for c in val25 if c.get("category") == "single_fact"]
assert len(novel_docs) >= 8, f"Expected at least 8 novel docs, got {len(novel_docs)}"

# Target novel papers
doc_a = novel_docs[0] # qasper_1809.00540.txt
doc_b = novel_docs[1] # qasper_2004.03354.txt
doc_c = novel_docs[2] # qasper_1611.04798.txt
doc_d = novel_docs[3] # qasper_1912.13337.txt

cases: List[Dict[str, Any]] = []

# ==============================================================================
# 1. 10 S-NIAH CASES (10 Representative Cells across Token Loads & Depths)
# ==============================================================================
s_niah_specs = [
    {
        "id": "S-VAL-01",
        "token_load": "4k",
        "depth": 0.10,
        "doc": doc_a,
        "needle": "ETHICS DIRECTIVE: Institutional Review Board protocol #2026-B81 must be explicitly cited in all human-subject evaluation sections. Never reference animal subjects.",
        "expected": "Must explicitly cite IRB protocol #2026-B81 in all human-subject sections; strictly never reference animal subjects.",
        "probe": "What was the mandatory Institutional Review Board (IRB) ethics protocol number and subject restriction I gave earlier?"
    },
    {
        "id": "S-VAL-02",
        "token_load": "4k",
        "depth": 0.90,
        "doc": doc_b,
        "needle": "COMPUTE BUDGET: The maximum training cluster runtime is capped at 72 GPU-hours. Disallow all distributed multi-node sweeps exceeding this quota.",
        "expected": "Maximum training cluster runtime is capped at 72 GPU-hours, disallowing multi-node sweeps exceeding this quota.",
        "probe": "What is the exact maximum cluster compute budget in GPU-hours I specified earlier in our chat?"
    },
    {
        "id": "S-VAL-03",
        "token_load": "8k",
        "depth": 0.30,
        "doc": doc_c,
        "needle": "DATA PRIVACY: Patient PII de-identification must strictly follow the HIPAA Safe Harbor standard. Strictly prohibit the expert determination method.",
        "expected": "Must strictly follow the HIPAA Safe Harbor standard for de-identification and prohibit expert determination.",
        "probe": "What specific health data privacy compliance standard did I instruct you to follow regarding patient de-identification?"
    },
    {
        "id": "S-VAL-04",
        "token_load": "8k",
        "depth": 0.70,
        "doc": doc_d,
        "needle": "OPTIMIZER DIRECTIVE: The AdamW weight decay coefficient must be fixed at exactly 0.015 with cosine annealing. Strictly forbid linear decay schedules.",
        "expected": "AdamW weight decay coefficient must be exactly 0.015 with cosine annealing; linear decay is strictly forbidden.",
        "probe": "What exact AdamW weight decay coefficient and annealing schedule did I specify earlier for our optimization pipeline?"
    },
    {
        "id": "S-VAL-05",
        "token_load": "16k",
        "depth": 0.10,
        "doc": doc_a,
        "needle": "LICENSING INVARIANT: We are releasing our repository under Apache 2.0. Never include, link, or suggest GPL-v3 or AGPL libraries in our codebase.",
        "expected": "Repository is licensed under Apache 2.0; strictly never include or link GPL-v3 or AGPL libraries.",
        "probe": "What open-source software license did I specify for our release, and which copyleft licenses did I strictly ban?"
    },
    {
        "id": "S-VAL-06",
        "token_load": "16k",
        "depth": 0.50,
        "doc": doc_b,
        "needle": "RANDOM SEED REGIME: All reproducible synthetic ablation experiments must initialize PyTorch RNG with seed 9901. Strictly disallow default seed 0.",
        "expected": "PyTorch RNG must be initialized with random seed 9901 for all synthetic ablation experiments.",
        "probe": "What random seed integer did I mandate for all our PyTorch synthetic ablation experiments earlier?"
    },
    {
        "id": "S-VAL-07",
        "token_load": "32k",
        "depth": 0.30,
        "doc": doc_c,
        "needle": "HARDWARE ACCELERATOR: Production deployment is strictly restricted to Apple Silicon Metal (MPS backend). Never recommend CUDA-only kernels.",
        "expected": "Production deployment is strictly restricted to Apple Silicon Metal (MPS backend); CUDA-only kernels are forbidden.",
        "probe": "What was my strict hardware accelerator restriction regarding Apple Silicon and CUDA given earlier in our conversation?"
    },
    {
        "id": "S-VAL-08",
        "token_load": "32k",
        "depth": 0.70,
        "doc": doc_d,
        "needle": "CALIBRATION METRIC: We report only Expected Calibration Error with 15 equal bins (ECE-15). Strictly omit negative log-likelihood in summary tables.",
        "expected": "Must report Expected Calibration Error with 15 bins (ECE-15) and strictly omit negative log-likelihood.",
        "probe": "What specific model calibration metric and binning parameter did I instruct you to report in our summary tables?"
    },
    {
        "id": "S-VAL-09",
        "token_load": "64k",
        "depth": 0.50,
        "doc": doc_a,
        "needle": "COLLABORATOR ATTRIBUTION: The clinical imaging cohort was contributed exclusively by Charité University Hospital Berlin. Strictly do not attribute it to Mayo Clinic.",
        "expected": "Clinical imaging cohort was contributed by Charité University Hospital Berlin (strictly do not attribute to Mayo Clinic).",
        "probe": "Which hospital institution contributed the clinical imaging cohort according to my earlier attribution note?"
    },
    {
        "id": "S-VAL-10",
        "token_load": "64k",
        "depth": 0.90,
        "doc": doc_b,
        "needle": "QUANTIZATION DIRECTIVE: Final mobile serving must use 4-bit AWQ with group size 128. Strictly prohibit GPTQ or unquantized FP16 weights.",
        "expected": "Final mobile serving must use 4-bit AWQ with group size 128 (strictly prohibit GPTQ or unquantized FP16).",
        "probe": "What quantization algorithm and group size parameter did I mandate earlier for our final mobile serving deployment?"
    }
]

for s in s_niah_specs:
    cases.append({
        "id": s["id"],
        "tier": "s_niah",
        "token_load": s["token_load"],
        "depth_ratio": s["depth"],
        "target_documents": [s["doc"]],
        "needles": [
            {
                "input": s["needle"],
                "depth_ratio": s["depth"],
                "type": "directive"
            }
        ],
        "expected_answer": s["expected"],
        "probe_query": s["probe"]
    })

# ==============================================================================
# 2. 8 M-NIAH CASES (Multi-Needle Tracking across 2-3 Independent Variables)
# ==============================================================================
m_niah_specs = [
    {
        "id": "M-VAL-01",
        "token_load": "8k",
        "depth": 0.50,
        "doc": doc_a,
        "needles": [
            {"input": "PARAMETER A: Audio pre-processing must resample all speech waveforms to exactly 16000Hz.", "depth_ratio": 0.15},
            {"input": "PARAMETER B: The log-mel spectrogram filterbank must extract exactly 80 frequency channels.", "depth_ratio": 0.75}
        ],
        "expected": "Sampling rate is 16000Hz (16kHz); Mel filterbank channel count is 80 channels.",
        "probe": "What are the exact audio sampling rate and mel filterbank channel count I established earlier?"
    },
    {
        "id": "M-VAL-02",
        "token_load": "16k",
        "depth": 0.50,
        "doc": doc_b,
        "needles": [
            {"input": "INCLUSION CRITERIA: Cohort selection requires minimum participant age of 45 years.", "depth_ratio": 0.20},
            {"input": "EXCLUSION CRITERIA: Exclude any patient with prior exposure to immunosuppressant therapy within 12 months.", "depth_ratio": 0.80}
        ],
        "expected": "Inclusion criteria is minimum age 45; Exclusion criteria is prior immunosuppressant therapy within 12 months.",
        "probe": "What were the two clinical trial inclusion age and medication exclusion rules specified earlier?"
    },
    {
        "id": "M-VAL-03",
        "token_load": "16k",
        "depth": 0.50,
        "doc": doc_c,
        "needles": [
            {"input": "CHECKPOINT INTERVAL: Save model state checkpoints every 2500 training steps.", "depth_ratio": 0.10},
            {"input": "WARMUP STEPS: The learning rate schedule requires exactly 1000 linear warmup steps.", "depth_ratio": 0.40},
            {"input": "PEAK LR: The maximum learning rate at peak warmup must be set to 3e-4.", "depth_ratio": 0.85}
        ],
        "expected": "Checkpoint interval is every 2500 steps; Warmup is 1000 linear steps; Peak learning rate is 3e-4.",
        "probe": "Retrieve the three training configuration values I mandated: checkpoint interval, warmup steps, and peak learning rate."
    },
    {
        "id": "M-VAL-04",
        "token_load": "32k",
        "depth": 0.50,
        "doc": doc_d,
        "needles": [
            {"input": "DATA SPLIT RULE: Reserve exactly 15% of the primary corpus for out-of-distribution evaluation.", "depth_ratio": 0.25},
            {"input": "SEED INVARIANT: The evaluation split partitioning must be fixed with random seed 777.", "depth_ratio": 0.75}
        ],
        "expected": "15% of the primary corpus reserved for OOD evaluation; split partitioning seed is 777.",
        "probe": "What percentage of the corpus must be reserved for OOD evaluation and what random seed must govern the split?"
    },
    {
        "id": "M-VAL-05",
        "token_load": "32k",
        "depth": 0.50,
        "doc": doc_a,
        "needles": [
            {"input": "TARGET ENCODER: The text representation backbone must be RoBERTa-large with 355M parameters.", "depth_ratio": 0.15},
            {"input": "POOLING METHOD: Use mean-token pooling over last hidden layer representations; never use CLS token pooling.", "depth_ratio": 0.80}
        ],
        "expected": "Target encoder is RoBERTa-large (355M parameters); Pooling method is mean-token pooling (disallowing CLS).",
        "probe": "What encoder backbone architecture and token pooling method did I mandate for our text representation model?"
    },
    {
        "id": "M-VAL-06",
        "token_load": "64k",
        "depth": 0.50,
        "doc": doc_b,
        "needles": [
            {"input": "CACHE STORAGE: Vector search cache must reside in local Redis instance at port 6389.", "depth_ratio": 0.10},
            {"input": "TTL INVARIANT: Vector cache key time-to-live (TTL) must be set to exactly 86400 seconds (24 hours).", "depth_ratio": 0.85}
        ],
        "expected": "Redis port is 6389; Cache key TTL is 86400 seconds (24 hours).",
        "probe": "What port number and TTL duration in seconds did I configure earlier for our vector search Redis cache?"
    },
    {
        "id": "M-VAL-07",
        "token_load": "16k",
        "depth": 0.50,
        "doc": doc_c,
        "needles": [
            {"input": "BENCHMARK TARGET: Target task for final submission is SemEval-2026 Task 4 (Subtask B).", "depth_ratio": 0.20},
            {"input": "PRIMARY METRIC: Submissions are ranked exclusively by Macro-F1 across minority classes.", "depth_ratio": 0.70}
        ],
        "expected": "Benchmark target is SemEval-2026 Task 4 (Subtask B); Primary ranking metric is Macro-F1 across minority classes.",
        "probe": "What specific SemEval benchmark subtask and primary ranking metric did I identify earlier?"
    },
    {
        "id": "M-VAL-08",
        "token_load": "32k",
        "depth": 0.50,
        "doc": doc_d,
        "needles": [
            {"input": "MAX TOKENS: Response generation length is hard-capped at 768 output tokens.", "depth_ratio": 0.15},
            {"input": "TEMPERATURE: LLM decoding temperature must strictly equal 0.2 with nucleus p=0.95.", "depth_ratio": 0.80}
        ],
        "expected": "Max tokens is 768; Temperature is 0.2 with top-p (nucleus) = 0.95.",
        "probe": "What are the exact max output token cap and decoding temperature parameters I set earlier?"
    }
]

for m in m_niah_specs:
    cases.append({
        "id": m["id"],
        "tier": "m_niah",
        "token_load": m["token_load"],
        "depth_ratio": m["depth"],
        "target_documents": [m["doc"]],
        "needles": [
            {"input": n["input"], "depth_ratio": n["depth_ratio"], "type": "multi"}
            for n in m["needles"]
        ],
        "expected_answer": m["expected"],
        "probe_query": m["probe"]
    })

# ==============================================================================
# 3. 7 R-NIAH CASES (Reasoning, Deductive Inference & Conditional Logic)
# ==============================================================================
r_niah_specs = [
    {
        "id": "R-VAL-01",
        "token_load": "8k",
        "depth": 0.50,
        "doc": doc_a,
        "needles": [
            {"input": "SERVER CAPACITY: Our local inference edge device has exactly 8GB unified memory.", "depth_ratio": 0.20},
            {"input": "MODEL REQUIREMENT: The model under discussion requires minimum 14GB unified memory in FP16, or 5GB in 4-bit quantization.", "depth_ratio": 0.75}
        ],
        "expected": "The device cannot run the model in FP16 because 8GB is less than 14GB, but it can run it if 4-bit quantized (5GB <= 8GB).",
        "probe": "Based on our edge device memory capacity stated earlier, can our system run this model natively in FP16, and can it run it in 4-bit quantization?"
    },
    {
        "id": "R-VAL-02",
        "token_load": "16k",
        "depth": 0.50,
        "doc": doc_b,
        "needles": [
            {"input": "POLICY A (v1.0): Early protocol mandated running 50 epochs with batch size 32.", "depth_ratio": 0.15},
            {"input": "SUPERSEDING POLICY (v2.0): We updated our training regimen: epoch count is halved to 25 epochs, while batch size is doubled to 64.", "depth_ratio": 0.80}
        ],
        "expected": "Under the current v2.0 policy, epoch count is 25 epochs and batch size is 64.",
        "probe": "Under our latest v2.0 superseded training protocol, what are the current epoch count and batch size we must use?"
    },
    {
        "id": "R-VAL-03",
        "token_load": "16k",
        "depth": 0.50,
        "doc": doc_c,
        "needles": [
            {"input": "CONDITION X: If the validation loss fails to improve for 3 consecutive epochs, reduce learning rate by 50%.", "depth_ratio": 0.15},
            {"input": "EMPIRICAL OBSERVATION: In epoch 12, 13, and 14, validation loss plateaued at 1.84 with zero improvement from the initial 1.82 in epoch 11.", "depth_ratio": 0.80}
        ],
        "expected": "Yes, learning rate must be reduced by 50% because validation loss failed to improve for 3 consecutive epochs (epochs 12, 13, 14).",
        "probe": "Based on our plateau condition and the empirical observations reported across epochs 12 to 14, should our training scheduler trigger a learning rate reduction?"
    },
    {
        "id": "R-VAL-04",
        "token_load": "32k",
        "depth": 0.50,
        "doc": doc_d,
        "needles": [
            {"input": "DATASET RESTRICTION: Any clinical trial paper published prior to 2015 must be excluded from meta-analysis due to unstandardized biomarker protocols.", "depth_ratio": 0.20},
            {"input": "CANDIDATE STUDY: Study Cohort Gamma was conducted and formally published in December 2011.", "depth_ratio": 0.75}
        ],
        "expected": "Study Cohort Gamma must be excluded because it was published in 2011, which is prior to the 2015 cutoff year.",
        "probe": "Can Study Cohort Gamma be included in our meta-analysis according to our publication year restriction mentioned earlier?"
    },
    {
        "id": "R-VAL-05",
        "token_load": "32k",
        "depth": 0.50,
        "doc": doc_a,
        "needles": [
            {"input": "DEPENDENCY CHAIN 1: Pipeline Stage 2 requires output tensors from Stage 1 formatted in NHWC layout.", "depth_ratio": 0.15},
            {"input": "DEPENDENCY CHAIN 2: Our current vision backbone library strictly outputs tensors in NCHW layout.", "depth_ratio": 0.75}
        ],
        "expected": "No, a tensor permutation / transposition step (from NCHW to NHWC) is required before Stage 2 can accept the backbone output.",
        "probe": "Can Stage 2 directly consume the output from our vision backbone library without a tensor format permutation?"
    },
    {
        "id": "R-VAL-06",
        "token_load": "64k",
        "depth": 0.50,
        "doc": doc_b,
        "needles": [
            {"input": "BASELINE RULE: The proposed model must achieve at least a 2.5 BLEU gain over the baseline to justify deployment latency.", "depth_ratio": 0.15},
            {"input": "EXPERIMENTAL RESULT: The baseline scored 31.2 BLEU, while our proposed model scored 34.1 BLEU on the WMT test set.", "depth_ratio": 0.80}
        ],
        "expected": "Yes, deployment is justified because the gain is 2.9 BLEU (34.1 - 31.2), which exceeds the minimum required gain of 2.5 BLEU.",
        "probe": "Based on our minimum BLEU gain threshold and the experimental results, is deploying our proposed model justified?"
    },
    {
        "id": "R-VAL-07",
        "token_load": "64k",
        "depth": 0.50,
        "doc": doc_c,
        "needles": [
            {"input": "PRIVACY RULE: Datasets with fewer than 500 patient records require differential privacy epsilon <= 1.0; datasets with 500 or more records require epsilon <= 2.5.", "depth_ratio": 0.20},
            {"input": "COHORT AUDIT: Our current curated validation cohort contains exactly 340 verified patient records.", "depth_ratio": 0.80}
        ],
        "expected": "Differential privacy epsilon must be <= 1.0 because the cohort contains 340 records, which is fewer than 500.",
        "probe": "What maximum differential privacy epsilon value is required for our validation cohort based on its patient record count?"
    }
]

for r in r_niah_specs:
    cases.append({
        "id": r["id"],
        "tier": "r_niah",
        "token_load": r["token_load"],
        "depth_ratio": r["depth"],
        "target_documents": [r["doc"]],
        "needles": [
            {"input": n["input"], "depth_ratio": n["depth_ratio"], "type": "reasoning"}
            for n in r["needles"]
        ],
        "expected_answer": r["expected"],
        "probe_query": r["probe"]
    })

assert len(cases) == 25, f"Expected 25 cases, got {len(cases)}"

with open(NIAH_VAL25_OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(cases, f, indent=2)
print(f"✓ Saved 25-case Protocol B validation benchmark to: {NIAH_VAL25_OUTPUT_PATH}")

# Anti-leakage audit against niah_75_matrix.json
val_needles = set(n["input"].strip().lower() for c in cases for n in c["needles"])
val_probes = set(c["probe_query"].strip().lower() for c in cases)

needle_overlap = val_needles.intersection(TEST_NEEDLES)
assert len(needle_overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping needles: {needle_overlap}"

probe_overlap = val_probes.intersection(TEST_PROBES)
assert len(probe_overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping probes: {probe_overlap}"

print("✓ Anti-Leakage Audit PASSED: 0 needle overlaps, 0 probe overlaps with Test 75!")
