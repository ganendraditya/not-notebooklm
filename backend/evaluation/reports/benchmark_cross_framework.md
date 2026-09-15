# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 5 Industry-Standard Frameworks on AllenAI QASPER | Generated: 2026-09-15 04:10:42 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars)
> *Analogous to mAP and Recall in Computer Vision, these three core pillars represent the primary consensus across all evaluation judges.*

- **Overall Benchmark Status:** REVIEW REQUIRED
- **Consensus Pass Rate:** **0.0%** (0/2 cases passed)
- **Composite Consensus Score:** **0.544** / 1.000

| Core Evaluation Pillar | Multi-Judge Consensus | Target Threshold | Industry Standing |
| :--- | :---: | :---: | :--- |
| **Pillar 1: Groundedness (Anti-Hallucination)** | **0.367** | >= 0.850 | Cross-verified by DeepEval, TruLens & LlamaIndex |
| **Pillar 2: Answer Relevancy & Completeness** | **0.401** | >= 0.850 | Optimal Query Fulfillment |
| **Pillar 3: Ground-Truth Correctness** | **0.650** | >= 0.800 | Aligned with Human Expert Annotators |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** | >= 90.0% | Authentic Source Text Match |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `1.000` | `0.705` | G-Eval probabilistic metric |
| **TruLens** *(TruEra)* | `0.100` | `0.500` | RAG Triad Groundedness with CoT |
| **LlamaIndex** *(Native Core)* | `0.000` | `0.000` | Strict context entailment |
| **RAGAS** *(Exploding Gradients)* | `0.200` | `Evaluated` | Multi-statement atomic NLI |
| **Promptfoo** *(Assertion Suite)* | `PASS` | `PASS` | Model-graded test assertions |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | LlamaIndex | Consensus Faith | Consensus Rel | Correctness | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-1801_05147-01` | 1.000 | 0.200 | 0.000 | **0.400** | **0.303** | 0.500 | `FAIL` |
| `QASPER-1801_05147-02` | 1.000 | 0.000 | 0.000 | **0.333** | **0.500** | 0.800 | `FAIL` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*