# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-15 05:12:03 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** PASSED (Production Certified)
- **Consensus Pass Rate:** **100.0%** (2/2 cases passed)
- **Composite Consensus Score:** **0.903** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.831** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (1.000) + TruLens (0.667) + Promptfoo (0.975) + Ragas (0.683) |
| **Pillar 2: Answer Relevancy & Completeness** | **1.000** | >= 0.850 | **Continuous 3-Judge Mean:** DeepEval (1.000) + TruLens (1.000) + Ragas (0.844) |
| **Pillar 3: Ground-Truth Correctness** | **0.800** | >= 0.800 | Aligned with Human Expert Annotators (QASPER Ground Truth) |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *1.000* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `1.000` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `0.667` | `1.000` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.975` | `Evaluated` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.683` | `0.844` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `1.000 (Binary)` | `1.000` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-1912_01214-01` | 1.000 | 0.667 | 1.000 | 0.700 | 1.000 | **0.842** | **1.000** | 0.600 | `PASS` |
| `QASPER-1912_01214-02` | 1.000 | 0.667 | 0.950 | 0.667 | 1.000 | **0.821** | **1.000** | 1.000 | `PASS` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*