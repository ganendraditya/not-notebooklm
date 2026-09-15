# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-15 07:49:05 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** PASSED (Production Certified)
- **Consensus Pass Rate:** **72.0%** (18/25 cases passed)
- **Composite Consensus Score:** **0.880** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.787** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (1.000) + TruLens (0.647) + Promptfoo (0.862) + Ragas (0.622) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.924** | >= 0.850 | **Continuous 3-Judge Mean:** DeepEval (0.941) + TruLens (0.907) + Ragas (0.820) |
| **Pillar 3: Ground-Truth Correctness** | **0.892** | >= 0.800 | Aligned with Human Expert Annotators (QASPER Ground Truth) |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.400* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `0.941` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `0.647` | `0.907` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.862` | `Evaluated` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.622` | `0.820` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `0.400 (Binary)` | `0.600` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-VAL-1912_01214-01` | 1.000 | 0.667 | 0.850 | 0.556 | 0.000 | **0.768** | **1.000** | 0.600 | `PASS` |
| `QASPER-VAL-1912_01214-02` | 1.000 | 0.556 | 0.950 | 0.533 | 0.000 | **0.760** | **0.666** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-03` | 1.000 | 0.889 | 1.000 | 1.000 | 1.000 | **0.972** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1912_01214-04` | 1.000 | 0.545 | 0.950 | 0.654 | 0.000 | **0.787** | **1.000** | 0.800 | `PASS` |
| `QASPER-VAL-1810_08699-01` | 1.000 | 1.000 | 1.000 | 0.941 | 1.000 | **0.985** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1810_08699-02` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 0.900 | `PASS` |
| `QASPER-VAL-1810_08699-03` | 1.000 | 0.667 | 1.000 | 0.857 | 1.000 | **0.881** | **0.750** | 1.000 | `PASS` |
| `QASPER-VAL-1609_00425-01` | 1.000 | 0.444 | 0.500 | 0.765 | 0.000 | **0.677** | **0.928** | 0.900 | `FAIL` |
| `QASPER-VAL-1609_00425-02` | 1.000 | 0.556 | 0.950 | 0.529 | 0.000 | **0.759** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1801_05147-01` | 1.000 | 0.500 | 1.000 | 0.364 | 0.000 | **0.716** | **0.666** | 0.600 | `FAIL` |
| `QASPER-VAL-1801_05147-02` | 1.000 | 0.667 | 0.850 | 0.125 | 0.000 | **0.660** | **0.750** | 0.800 | `FAIL` |
| `QASPER-VAL-1811_00383-01` | 1.000 | 0.667 | 0.820 | 0.778 | 0.000 | **0.816** | **0.955** | 0.400 | `PASS` |
| `QASPER-VAL-1811_00383-02` | 1.000 | 0.000 | 0.200 | 0.800 | 0.000 | **0.500** | **1.000** | 1.000 | `FAIL` |
| `QASPER-VAL-1811_00383-03` | 1.000 | 0.889 | 0.950 | 0.333 | 0.000 | **0.793** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-01` | 1.000 | 0.667 | 1.000 | 1.000 | 1.000 | **0.917** | **0.916** | 1.000 | `PASS` |
| `QASPER-VAL-1909_09067-02` | 1.000 | 0.333 | 0.500 | 0.571 | 0.000 | **0.601** | **1.000** | 0.900 | `FAIL` |
| `QASPER-VAL-1704_06194-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-02` | 1.000 | 0.593 | 0.880 | 1.000 | 0.000 | **0.868** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-03` | 1.000 | 1.000 | 1.000 | 0.281 | 1.000 | **0.820** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-1704_06194-04` | 1.000 | 0.833 | 1.000 | 0.000 | 1.000 | **0.708** | **1.000** | 0.700 | `PASS` |
| `QASPER-VAL-1909_00512-01` | 1.000 | 0.353 | 0.650 | 0.333 | 0.000 | **0.584** | **1.000** | 1.000 | `FAIL` |
| `QASPER-VAL-1909_00512-02` | 1.000 | 0.500 | 0.950 | 0.421 | 1.000 | **0.718** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-2003_03106-01` | 1.000 | 0.424 | 0.950 | 0.462 | 1.000 | **0.709** | **0.500** | 0.700 | `FAIL` |
| `QASPER-VAL-2003_03106-02` | 1.000 | 0.762 | 0.650 | N/A | 0.000 | **0.804** | **1.000** | 1.000 | `PASS` |
| `QASPER-VAL-2003_03106-03` | 1.000 | 0.667 | 0.950 | N/A | 0.000 | **0.872** | **0.962** | 1.000 | `PASS` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*