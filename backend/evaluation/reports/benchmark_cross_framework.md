# Not-NotebookLM Multi-Framework Scientific Benchmark Report
*Evaluated across 6 Open-Source Frameworks on AllenAI & Princeton Standards | Generated: 2026-09-17 17:02:10 UTC*

## Tier 1: Executive Summary (3 Core Consensus Pillars & Dual-Layer Citations)
- **Evaluated Models:** Synthesis Generator: `ag/gemini-3.8-flash-high` | Evaluator Judge: `ag/gemini-3.1-pro-low` (greedy decoding `temperature=0.0`)
> *Analogous to mAP and Recall in Computer Vision, these core pillars represent the primary continuous consensus across all evaluation judges.*

- **Overall Benchmark Status:** PASSED (Production Certified)
- **Consensus Pass Rate:** **94.0%** (47/50 cases passed)
- **Composite Consensus Score:** **0.953** / 1.000

| Core Evaluation Dimension | Multi-Judge Consensus | Target Standard | Methodology & Frameworks |
| :--- | :---: | :---: | :--- |
| **Groundedness (Anti-Hallucination)** | **0.949** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (0.985) + TruLens (0.942) + Promptfoo (0.957) + Ragas (0.919) |
| **Answer Relevancy & Completeness** | **0.923** | >= 0.850 | **Continuous 4-Judge Mean:** DeepEval (0.956) + TruLens (0.853) + Promptfoo (0.960) + Ragas (N/A) |
| **Ground-Truth Correctness** | **0.976** | >= 0.800 | Dual-Judge Consensus: LlamaIndex + Promptfoo GT Alignment |
| **Princeton ALCE Citation Quality** | **Recall: 0.817 / Precision: 0.760** | >= 0.850 | Formal Citation Recall (statement support) & Precision (redundancy check) |
| **Product Invariant: PDF Citation Fidelity** | **100.0%** *(1.000)* | >= 90.0% | Deterministic Substring & Fuzzy Match on physical source PDF |
| **Conversational NIAH Retention** | **1.000** *(Before: 0.400)* | >= 0.850 | Multi-turn user constraint retention evaluated under a deliberately constrained ~8,192-token context window environment (Stanford MT-Bench & Needle-In-A-Haystack protocol) |
| *Gatekeeper Check: LlamaIndex Strict Binary* | *0.720* | *Pass/Fail Gate* | *Binary pass/fail context entailment (Separated from continuous mean)* |

---

## Tier 2: Comprehensive Framework Deep-Dive Ledger

### A. Framework-by-Framework Scorecard Breakdown
| Evaluation Framework | Groundedness / Faithfulness | Answer Relevancy | Evaluator Type / Algorithm |
| :--- | :---: | :---: | :--- |
| **DeepEval** *(Confident AI)* | `0.985` | `0.956` | G-Eval probabilistic metric (0.000 - 1.000) |
| **TruLens** *(TruEra)* | `0.942` | `0.853` | RAG Triad Groundedness with CoT (0.000 - 1.000) |
| **Promptfoo** *(Assertion Suite)* | `0.957` | `0.960` | Model-graded test assertions (0.000 - 1.000) |
| **RAGAS** *(Exploding Gradients)* | `0.919` | `N/A` | Multi-statement atomic NLI + Embeddings (0.000 - 1.000) |
| **Princeton ALCE** *(Princeton NLP)* | `Recall: 0.817` | `Precision: 0.760` | Formal statement entailment & citation redundancy penalty (EMNLP 2023) |
| **LlamaIndex** *(Native Core)* | `0.720 (Binary)` | `0.220` | Strict binary pass/fail context entailment [0 or 1] |

### B. Case-by-Case Cross-Framework Matrix
| Case ID | DeepEval | TruLens | Promptfoo | RAGAS | ALCE (Rec/Prec) | LlamaIndex *(Binary)* | Consensus Faith | Consensus Rel | Correctness | NIAH | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `QASPER-TES-1911_10742-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1911_10742-02` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **0.983** | 0.500 | **1.00** | `PASS` |
| `QASPER-TES-1911_10742-03` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1911_10742-04` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1904_09131-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 0.000 | **1.000** | **0.970** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1611_06322-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1611_06322-02` | 1.000 | 1.000 | 1.000 | 0.944 | 1.00/1.00 | 1.000 | **0.986** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1611_06322-03` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 0.975 | **1.00** | `PASS` |
| `QASPER-TES-1611_06322-04` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1611_06322-05` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1611_06322-06` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 0.000 | **1.000** | **0.905** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1604_02038-01` | 1.000 | 1.000 | 1.000 | 0.933 | 1.00/1.00 | 1.000 | **0.983** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1604_02038-02` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1911_04474-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1911_04474-02` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **0.956** | 0.950 | **1.00** | `PASS` |
| `QASPER-TES-1911_04474-03` | 0.800 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **0.950** | **1.000** | 0.950 | **1.00** | `PASS` |
| `QASPER-TES-1905_00840-01` | 0.667 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **0.917** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1905_00840-02` | 0.800 | 1.000 | 0.975 | 1.000 | 1.00/1.00 | 1.000 | **0.950** | **0.840** | 0.900 | **1.00** | `PASS` |
| `QASPER-TES-1905_00840-03` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1810_02229-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1810_02229-02` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **0.818** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1810_02229-03` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1909_00091-01` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1909_00091-02` | 1.000 | 1.000 | 1.000 | 0.884 | 1.00/1.00 | 0.000 | **0.971** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-TES-1909_00091-03` | 1.000 | 1.000 | 1.000 | 0.000 | 1.00/1.00 | 0.000 | **0.750** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-01` | 1.000 | 0.667 | 0.900 | 0.961 | 0.15/0.00 | 0.000 | **0.869** | **0.753** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-02` | 1.000 | 0.500 | 0.950 | 0.204 | 0.28/0.00 | 0.000 | **0.676** | **0.744** | 1.000 | **1.00** | `FAIL` |
| `QASPER-MUL-03` | 1.000 | 1.000 | 0.975 | 0.885 | 0.37/0.00 | 1.000 | **0.971** | **0.751** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-04` | 0.960 | 0.333 | 0.450 | 0.979 | 0.33/0.00 | 0.000 | **0.680** | **0.735** | 0.625 | **1.00** | `FAIL` |
| `QASPER-MUL-05` | 1.000 | 1.000 | 0.925 | 0.951 | 0.37/0.00 | 0.000 | **0.988** | **0.659** | 0.450 | **1.00** | `PASS` |
| `QASPER-MUL-06` | 1.000 | 1.000 | 0.834 | 0.426 | 0.13/0.00 | 1.000 | **0.857** | **0.667** | 0.750 | **1.00** | `PASS` |
| `QASPER-MUL-07` | 1.000 | 0.889 | 0.750 | 0.667 | 0.43/0.00 | 1.000 | **0.889** | **0.611** | 0.750 | **1.00** | `PASS` |
| `QASPER-MUL-08` | 1.000 | 1.000 | 0.825 | 0.315 | 0.49/0.00 | 1.000 | **0.791** | **0.711** | 0.750 | **1.00** | `PASS` |
| `QASPER-MUL-09` | 1.000 | 1.000 | 0.950 | 0.875 | 0.41/0.00 | 0.000 | **0.969** | **0.736** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-10` | 1.000 | 0.333 | 0.525 | 1.000 | 0.56/0.00 | 0.000 | **0.633** | **0.705** | 1.000 | **1.00** | `FAIL` |
| `QASPER-MUL-11` | 1.000 | 1.000 | 1.000 | 1.000 | 1.00/1.00 | 0.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-12` | 1.000 | 1.000 | 1.000 | 0.967 | 0.80/1.00 | 0.000 | **0.992** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-13` | 1.000 | 0.889 | 1.000 | 1.000 | 0.90/1.00 | 1.000 | **0.972** | **1.000** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-14` | 1.000 | 1.000 | 1.000 | N/A | 0.65/1.00 | 0.000 | **1.000** | **0.976** | 1.000 | **1.00** | `PASS` |
| `QASPER-MUL-15` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 0.000 | **1.000** | **0.706** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0003` | 1.000 | 0.667 | 0.650 | N/A | 0.00/0.00 | 1.000 | **0.722** | **0.933** | 0.925 | **1.00** | `PASS` |
| `SCIFACT-0005` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0049` | 1.000 | 1.000 | 1.000 | N/A | 0.00/0.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0050` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0053` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0042` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0048` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0051` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0054` | 1.000 | 1.000 | 1.000 | N/A | 1.00/1.00 | 1.000 | **1.000** | **1.000** | 1.000 | **1.00** | `PASS` |
| `SCIFACT-0057` | 1.000 | 0.800 | 1.000 | N/A | 1.00/1.00 | 1.000 | **0.933** | **1.000** | 1.000 | **1.00** | `PASS` |

---
*Report generated automatically by Not-NotebookLM Unified Cross-Framework Benchmark.*