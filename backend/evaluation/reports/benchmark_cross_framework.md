# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-15 04:24:04 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary consensus across all evaluation judges.*

- **Overall Benchmark Status:** REVIEW REQUIRED
- **Consensus Pass Rate:** **0.0%** (0/2 cases passed)
- **Composite Consensus Score:** **0.601** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Industry Standing |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.460** | >= 0.850 | Cross-verified by DeepEval, TruLens & LlamaIndex |
| **Pillar 2: Answer Relevancy & Completeness** | **0.416** | >= 0.850 | Optimal Query Fulfillment |
| **Pillar 3: Ground-Truth Correctness** | **0.750** | >= 0.800 | Aligned with Human Expert Annotators |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** | >= 90.0% | Authentic Source Text Match |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `0.750` | G-Eval probabilistic metric |
| **TruLens** *(TruEra)* | `0.167` | `0.500` | RAG Triad Groundedness with CoT |
| **LlamaIndex** *(Native Core)* | `0.000 *(Strict Binary)*` | `0.000` | Binary pass/fail context entailment |
| **RAGAS** *(Exploding Gradients)* | `0.000` | `0.840` | Multi-statement atomic NLI + Embeddings |
| **Promptfoo** *(Assertion Suite)* | `0.675` | `Evaluated` | Model-graded test assertions |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | LlamaIndex | Promptfoo | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-1801_05147-01` | 1.000 | 0.000 | 0.000 | 0.950 | **0.487** | **0.333** | 0.600 | `FAIL` |
| `QASPER-1801_05147-02` | 1.000 | 0.333 | 0.000 | 0.400 | **0.433** | **0.500** | 0.900 | `FAIL` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*