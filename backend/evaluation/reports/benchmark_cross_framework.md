# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-15 04:32:05 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary consensus across all evaluation judges.*

- **Overall Benchmark Status:** REVIEW REQUIRED
- **Consensus Pass Rate:** **0.0%** (0/2 cases passed)
- **Composite Consensus Score:** **0.634** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Frameworks Included in Mean |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.392** | >= 0.850 | **5 Frameworks:** DeepEval (1.000) + TruLens (0.084) + Promptfoo (0.625) + Ragas (0.000) + LlamaIndex (0.000) |
| **Pillar 2: Answer Relevancy & Completeness** | **0.628** | >= 0.850 | **4 Frameworks:** DeepEval (0.834) + TruLens (1.000) + Ragas (0.801) + LlamaIndex (0.000) |
| **Pillar 3: Ground-Truth Correctness** | **0.800** | >= 0.800 | Aligned with Human Expert Annotators (QASPER Ground Truth) |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** | >= 90.0% | Deterministic Substring & Fuzzy Match on raw PDF text |

> **Continuous 4-Framework Groundedness (Excluding LlamaIndex Binary):** **`0.427`**

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `0.834` | G-Eval probabilistic metric |
| **TruLens** *(TruEra)* | `0.084` | `1.000` | RAG Triad Groundedness with CoT |
| **Promptfoo** *(Assertion Suite)* | `0.625` | `Evaluated` | Model-graded test assertions (continuous score) |
| **RAGAS** *(Exploding Gradients)* | `0.000` | `0.801` | Multi-statement atomic NLI + Embeddings |
| **LlamaIndex** *(Native Core)* | `0.000 (Binary)` | `0.000` | Strict binary pass/fail context entailment |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | LlamaIndex | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-1801_05147-01` | 1.000 | 0.000 | 0.400 | 0.000 | 0.000 | **0.280** | **0.700** | 0.700 | `FAIL` |
| `QASPER-1801_05147-02` | 1.000 | 0.167 | 0.850 | N/A | 0.000 | **0.504** | **0.556** | 0.900 | `FAIL` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*