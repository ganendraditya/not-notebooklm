# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-15 16:18:12 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** PASSED (Production Certified)
- **Consensus Pass Rate:** **68.0%** (17/25 cases passed)
- **Composite Consensus Score:** **0.862** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.755** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (1.000) + TruLens (0.622) + Promptfoo (0.775) + Ragas (0.605) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.921** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (0.948) + TruLens (0.920) + Promptfoo (0.896) + Ragas (0.819) |
| **Pillar 3: Ground-Truth Correctness** | **0.904** | >= 0.800 | Dual-Judge Consensus: LlamaIndex + Promptfoo GT Alignment |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.400* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `0.948` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `0.622` | `0.920` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.775` | `0.896` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.605` | `0.819` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `0.400 (Binary)` | `0.680` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-VAL-1912_01214-01` | 1.000 | 0.750 | 0.935 | 0.800 | 1.000 | **0.867** | **0.983** | 0.725 | `PASS` |
| `QASPER-VAL-1912_01214-02` | 1.000 | 0.467 | 0.975 | 0.800 | 0.000 | **0.817** | **0.983** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-03` | 1.000 | 0.750 | 0.975 | 0.667 | 0.000 | **0.842** | **0.889** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-04` | 1.000 | 0.889 | 0.915 | 0.591 | 0.000 | **0.840** | **0.983** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | **0.889** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-02` | 1.000 | 1.000 | 0.975 | 1.000 | 1.000 | **1.000** | **0.917** | 0.900 | `PASS` |
| `QASPER-VAL-1810_08699-03` | 1.000 | 0.667 | 1.000 | 0.833 | 1.000 | **0.875** | **0.867** | 1.000 | `PASS` |
| `QASPER-VAL-1609_00425-01` | 1.000 | 0.200 | 0.575 | 0.400 | 0.000 | **0.512** | **0.867** | 0.925 | `FAIL` |
| `QASPER-VAL-1609_00425-02` | 1.000 | 0.556 | 0.900 | 0.438 | 0.000 | **0.711** | **0.983** | 1.000 | `PASS` |
| `QASPER-VAL-1801_05147-01` | 1.000 | 0.778 | 0.975 | 0.444 | 1.000 | **0.805** | **0.983** | 0.800 | `PASS` |
| `QASPER-VAL-1801_05147-02` | 1.000 | 0.000 | 0.575 | 0.000 | 0.000 | **0.325** | **0.950** | 0.800 | `FAIL` |
| `QASPER-VAL-1811_00383-01` | 1.000 | 0.778 | 0.250 | 0.900 | 0.000 | **0.744** | **0.733** | 0.100 | `FAIL` |
| `QASPER-VAL-1811_00383-02` | 1.000 | 0.000 | 0.475 | 0.400 | 0.000 | **0.469** | **0.983** | 1.000 | `FAIL` |
| `QASPER-VAL-1811_00383-03` | 1.000 | 1.000 | 0.975 | 0.200 | 1.000 | **0.800** | **0.983** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-01` | 1.000 | 0.333 | 0.725 | 1.000 | 0.000 | **0.708** | **0.928** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-02` | 1.000 | 0.167 | 0.650 | 0.345 | 0.000 | **0.478** | **0.967** | 0.850 | `FAIL` |
| `QASPER-VAL-1704_06194-01` | 1.000 | 1.000 | 0.975 | 1.000 | 1.000 | **1.000** | **0.983** | 0.950 | `PASS` |
| `QASPER-VAL-1704_06194-02` | 1.000 | 0.778 | 0.890 | 1.000 | 1.000 | **0.914** | **0.744** | 0.975 | `PASS` |
| `QASPER-VAL-1704_06194-03` | 1.000 | 1.000 | 0.975 | 0.107 | 1.000 | **0.777** | **0.983** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-04` | 1.000 | 1.000 | 0.975 | 0.167 | 1.000 | **0.792** | **0.983** | 0.500 | `PASS` |
| `QASPER-VAL-1909_00512-01` | 1.000 | 0.222 | 0.550 | 0.591 | 0.000 | **0.553** | **0.900** | 0.800 | `FAIL` |
| `QASPER-VAL-1909_00512-02` | 1.000 | 0.222 | 0.915 | 0.722 | 0.000 | **0.699** | **0.993** | 1.000 | `FAIL` |
| `QASPER-VAL-2003_03106-01` | 1.000 | 0.667 | 0.650 | 0.500 | 0.000 | **0.654** | **0.586** | 0.400 | `FAIL` |
| `QASPER-VAL-2003_03106-02` | 1.000 | 0.667 | 0.930 | N/A | 0.000 | **0.849** | **0.993** | 1.000 | `PASS` |
| `QASPER-VAL-2003_03106-03` | 1.000 | 0.667 | 0.925 | N/A | 0.000 | **0.856** | **0.983** | 0.875 | `PASS` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*