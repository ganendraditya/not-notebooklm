# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-16 01:49:54 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** REVIEW REQUIRED
- **Consensus Pass Rate:** **40.0%** (10/25 cases passed)
- **Composite Consensus Score:** **0.794** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.613** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (N/A) + TruLens (N/A) + Promptfoo (0.749) + Ragas (0.546) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.883** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (N/A) + TruLens (N/A) + Promptfoo (0.883) + Ragas (0.810) |
| **Pillar 3: Ground-Truth Correctness** | **0.896** | >= 0.800 | Dual-Judge Consensus: LlamaIndex + Promptfoo GT Alignment |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.280* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `N/A` | `N/A` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `N/A` | `N/A` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.749` | `0.883` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.546` | `0.810` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `0.280 (Binary)` | `0.520` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-VAL-1912_01214-01` | N/A | N/A | 0.725 | 0.615 | 1.000 | **0.607** | **0.850** | 0.500 | `FAIL` |
| `QASPER-VAL-1912_01214-02` | N/A | N/A | 0.950 | 0.636 | 0.000 | **0.793** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-03` | N/A | N/A | 0.900 | 0.583 | 0.000 | **0.716** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-04` | N/A | N/A | 0.975 | 0.500 | 0.000 | **0.750** | **0.950** | 0.925 | `PASS` |
| `QASPER-VAL-1810_08699-01` | N/A | N/A | 1.000 | 0.933 | 1.000 | **0.967** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-02` | N/A | N/A | 0.975 | 1.000 | 1.000 | **1.000** | **0.950** | 0.950 | `PASS` |
| `QASPER-VAL-1810_08699-03` | N/A | N/A | 0.925 | 0.600 | 0.000 | **0.750** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1609_00425-01` | N/A | N/A | 0.575 | 0.533 | 0.000 | **0.492** | **0.700** | 0.825 | `FAIL` |
| `QASPER-VAL-1609_00425-02` | N/A | N/A | 0.900 | 0.000 | 0.000 | **0.425** | **0.950** | 1.000 | `FAIL` |
| `QASPER-VAL-1801_05147-01` | N/A | N/A | 0.775 | 0.333 | 0.000 | **0.592** | **0.700** | 0.450 | `FAIL` |
| `QASPER-VAL-1801_05147-02` | N/A | N/A | 0.875 | 0.125 | 0.000 | **0.487** | **0.900** | 0.925 | `FAIL` |
| `QASPER-VAL-1811_00383-01` | N/A | N/A | 0.350 | 0.600 | 0.000 | **0.500** | **0.300** | 0.200 | `FAIL` |
| `QASPER-VAL-1811_00383-02` | N/A | N/A | 0.725 | 0.111 | 0.000 | **0.305** | **0.950** | 0.950 | `FAIL` |
| `QASPER-VAL-1811_00383-03` | N/A | N/A | 0.650 | 0.333 | 0.000 | **0.367** | **0.900** | 0.975 | `FAIL` |
| `QASPER-VAL-1909_09067-01` | N/A | N/A | 1.000 | 0.778 | 1.000 | **0.889** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-02` | N/A | N/A | 0.625 | 1.000 | 0.000 | **0.700** | **0.850** | 0.800 | `PASS` |
| `QASPER-VAL-1704_06194-01` | N/A | N/A | 0.950 | 0.000 | 0.000 | **0.475** | **0.950** | 1.000 | `FAIL` |
| `QASPER-VAL-1704_06194-02` | N/A | N/A | 0.775 | 1.000 | 1.000 | **0.850** | **0.850** | 0.975 | `PASS` |
| `QASPER-VAL-1704_06194-03` | N/A | N/A | 0.975 | 0.000 | 1.000 | **0.500** | **0.950** | 1.000 | `FAIL` |
| `QASPER-VAL-1704_06194-04` | N/A | N/A | 0.975 | 0.200 | 1.000 | **0.600** | **0.950** | 0.500 | `FAIL` |
| `QASPER-VAL-1909_00512-01` | N/A | N/A | 0.750 | 0.000 | 0.000 | **0.325** | **0.850** | 0.825 | `FAIL` |
| `QASPER-VAL-1909_00512-02` | N/A | N/A | 0.475 | 0.000 | 0.000 | **0.237** | **0.950** | 1.000 | `FAIL` |
| `QASPER-VAL-2003_03106-01` | N/A | N/A | 0.625 | 0.500 | 0.000 | **0.450** | **0.850** | 0.575 | `FAIL` |
| `QASPER-VAL-2003_03106-02` | N/A | N/A | 0.800 | N/A | 0.000 | **0.650** | **0.950** | 0.975 | `FAIL` |
| `QASPER-VAL-2003_03106-03` | N/A | N/A | 0.910 | N/A | 0.000 | **0.900** | **0.920** | 0.925 | `PASS` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*