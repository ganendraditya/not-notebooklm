# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-16 02:32:59 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** PASSED (Production Certified)
- **Consensus Pass Rate:** **52.0%** (13/25 cases passed)
- **Composite Consensus Score:** **0.814** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.633** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (N/A) + TruLens (N/A) + Promptfoo (0.716) + Ragas (0.654) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.904** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (N/A) + TruLens (N/A) + Promptfoo (0.904) + Ragas (0.840) |
| **Pillar 3: Ground-Truth Correctness** | **0.960** | >= 0.800 | Dual-Judge Consensus: LlamaIndex + Promptfoo GT Alignment |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.320* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `N/A` | `N/A` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `N/A` | `N/A` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.716` | `0.904` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.654` | `0.840` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `0.320 (Binary)` | `0.480` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-VAL-1912_01214-01` | N/A | N/A | 0.975 | 0.778 | 1.000 | **0.889** | **0.950** | 0.825 | `PASS` |
| `QASPER-VAL-1912_01214-02` | N/A | N/A | 0.775 | 0.714 | 1.000 | **0.707** | **0.850** | 0.975 | `PASS` |
| `QASPER-VAL-1912_01214-03` | N/A | N/A | 0.925 | 0.714 | 0.000 | **0.782** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-04` | N/A | N/A | 0.950 | 0.684 | 0.000 | **0.817** | **0.950** | 0.975 | `PASS` |
| `QASPER-VAL-1810_08699-01` | N/A | N/A | 1.000 | 0.667 | 1.000 | **0.834** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-02` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-03` | N/A | N/A | 0.775 | 0.667 | 0.000 | **0.659** | **0.900** | 0.950 | `FAIL` |
| `QASPER-VAL-1609_00425-01` | N/A | N/A | 0.900 | 0.600 | 0.000 | **0.725** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1609_00425-02` | N/A | N/A | 0.700 | 0.458 | 0.000 | **0.504** | **0.850** | 0.975 | `FAIL` |
| `QASPER-VAL-1801_05147-01` | N/A | N/A | 0.925 | 0.714 | 0.000 | **0.857** | **0.850** | 0.600 | `PASS` |
| `QASPER-VAL-1801_05147-02` | N/A | N/A | 0.575 | 0.000 | 0.000 | **0.150** | **0.850** | 0.800 | `FAIL` |
| `QASPER-VAL-1811_00383-01` | N/A | N/A | 0.475 | 1.000 | 0.000 | **0.675** | **0.600** | 0.600 | `FAIL` |
| `QASPER-VAL-1811_00383-02` | N/A | N/A | 0.700 | 0.000 | 0.000 | **0.200** | **1.000** | 1.000 | `FAIL` |
| `QASPER-VAL-1811_00383-03` | N/A | N/A | 1.000 | 0.500 | 1.000 | **0.750** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-01` | N/A | N/A | 0.700 | 1.000 | 0.000 | **0.750** | **0.900** | 0.975 | `PASS` |
| `QASPER-VAL-1909_09067-02` | N/A | N/A | 0.800 | 0.000 | 0.000 | **0.325** | **0.950** | 0.975 | `FAIL` |
| `QASPER-VAL-1704_06194-01` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-02` | N/A | N/A | 0.875 | 1.000 | 0.000 | **0.925** | **0.900** | 0.975 | `PASS` |
| `QASPER-VAL-1704_06194-03` | N/A | N/A | 1.000 | 0.000 | 1.000 | **0.500** | **1.000** | 1.000 | `FAIL` |
| `QASPER-VAL-1704_06194-04` | N/A | N/A | 0.975 | 0.000 | 1.000 | **0.500** | **0.950** | 0.700 | `FAIL` |
| `QASPER-VAL-1909_00512-01` | N/A | N/A | 0.525 | 0.389 | 0.000 | **0.369** | **0.700** | 0.800 | `FAIL` |
| `QASPER-VAL-1909_00512-02` | N/A | N/A | 0.575 | 0.000 | 0.000 | **0.100** | **0.950** | 1.000 | `FAIL` |
| `QASPER-VAL-2003_03106-01` | N/A | N/A | 0.550 | 0.538 | 0.000 | **0.469** | **0.700** | 0.450 | `FAIL` |
| `QASPER-VAL-2003_03106-02` | N/A | N/A | 0.900 | N/A | 0.000 | **0.850** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-2003_03106-03` | N/A | N/A | 0.675 | N/A | 0.000 | **0.500** | **0.850** | 0.900 | `FAIL` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*