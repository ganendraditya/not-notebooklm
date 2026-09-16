# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-16 09:54:42 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** PASSED (Production Certified)
- **Consensus Pass Rate:** **84.0%** (21/25 cases passed)
- **Composite Consensus Score:** **0.949** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.913** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (N/A) + TruLens (N/A) + Promptfoo (1.000) + Ragas (0.981) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.974** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (N/A) + TruLens (N/A) + Promptfoo (0.974) + Ragas (N/A) |
| **Pillar 3: Ground-Truth Correctness** | **0.944** | >= 0.800 | Dual-Judge Consensus: LlamaIndex + Promptfoo GT Alignment |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.760* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `N/A` | `N/A` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `N/A` | `N/A` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `1.000` | `0.974` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.981` | `N/A` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `0.760 (Binary)` | `0.880` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-VAL-1912_01214-01` | N/A | N/A | 0.975 | 0.000 | 1.000 | **0.500** | **0.950** | 0.850 | `FAIL` |
| `QASPER-VAL-1912_01214-02` | N/A | N/A | 0.975 | 0.800 | 0.000 | **0.900** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-03` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-04` | N/A | N/A | 0.975 | 1.000 | 1.000 | **1.000** | **0.950** | 0.775 | `PASS` |
| `QASPER-VAL-1810_08699-01` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-02` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-03` | N/A | N/A | 0.975 | 1.000 | 1.000 | **1.000** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1609_00425-01` | N/A | N/A | 0.975 | 0.846 | 0.000 | **0.923** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1609_00425-02` | N/A | N/A | 0.975 | 1.000 | 0.000 | **1.000** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1801_05147-01` | N/A | N/A | 0.925 | 1.000 | 0.000 | **1.000** | **0.850** | 0.500 | `PASS` |
| `QASPER-VAL-1801_05147-02` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1811_00383-01` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1811_00383-02` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1811_00383-03` | N/A | N/A | 1.000 | 0.000 | 1.000 | **0.500** | **1.000** | 1.000 | `FAIL` |
| `QASPER-VAL-1909_09067-01` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-02` | N/A | N/A | 0.975 | 0.000 | 1.000 | **0.500** | **0.950** | 0.975 | `FAIL` |
| `QASPER-VAL-1704_06194-01` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-02` | N/A | N/A | 0.975 | 1.000 | 1.000 | **1.000** | **0.950** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-03` | N/A | N/A | 1.000 | 0.000 | 1.000 | **0.500** | **1.000** | 1.000 | `FAIL` |
| `QASPER-VAL-1704_06194-04` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 0.600 | `PASS` |
| `QASPER-VAL-1909_00512-01` | N/A | N/A | 0.975 | 1.000 | 0.000 | **1.000** | **0.950** | 0.950 | `PASS` |
| `QASPER-VAL-1909_00512-02` | N/A | N/A | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-2003_03106-01` | N/A | N/A | 0.975 | 1.000 | 0.000 | **1.000** | **0.950** | 0.750 | `PASS` |
| `QASPER-VAL-2003_03106-02` | N/A | N/A | 1.000 | N/A | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-2003_03106-03` | N/A | N/A | 1.000 | N/A | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*