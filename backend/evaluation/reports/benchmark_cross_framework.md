# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** REVIEW REQUIRED
- **Consensus Pass Rate:** **50.0%** (1/2 cases passed)
- **Composite Consensus Score:** **0.745** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Continuous Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.511** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (1.000) + TruLens (0.084) + Promptfoo (0.625) + Ragas (0.000) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.880** | >= 0.850 | **Continuous 3-Judge Mean:** DeepEval (0.778) + TruLens (1.000) + Ragas (0.801) |
| **Pillar 3: Ground-Truth Correctness** | **0.800** | >= 0.800 | Aligned with Human Expert Annotators (QASPER Ground Truth) |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.000 (Fail)* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Explicitly excluded from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `0.778` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `0.084` | `1.000` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.625` | `Evaluated` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.000` | `0.801` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **LlamaIndex** *(Native Core)* | `0.000 (Binary)` | `0.000` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-1801_05147-01` | 1.000 | 0.000 | 0.400 | 0.000 | 0.000 | **0.350** | **0.835** | 0.700 | `FAIL` (0.654) |
| `QASPER-1801_05147-02` | 1.000 | 0.167 | 0.850 | N/A | 0.000 | **0.672** | **0.925** | 0.900 | `PASS` (0.835) |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*
