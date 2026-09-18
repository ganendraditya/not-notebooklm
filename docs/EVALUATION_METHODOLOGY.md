# Not-NotebookLM RAG Evaluation & Benchmarking Methodology
*A Rigorous, Multi-Framework Scientific Evaluation Standard for Academic AI Research Assistants*

---

## 1. Executive Overview & Core Philosophy

In traditional Machine Learning (ML), models are evaluated on numerical labels or structured classifications using metrics such as Precision, Recall, F1-Score, or RMSE. In contrast, Retrieval-Augmented Generation (RAG) produces open-ended natural language, where identical semantic facts can be phrased in countless ways, and where subtle word changes can introduce subtle hallucinations.

To avoid subjective qualitative spot-checks ("eyeball engineering") and prevent **LLM Self-Preference Bias**, Not-NotebookLM establishes a formal **Dual-Track, Multi-Framework Scientific Evaluation Methodology**.

### Core Evaluation Invariants:
1. **No Cherry-Picking**: Evaluation questions and document contexts are sourced sequentially from peer-reviewed scientific datasets (AllenAI QASPER, Princeton ALCE) without manual curation of favorable cases.
2. **Multi-Judge Consensus**: No single AI model or framework has absolute authority. Groundedness and Relevancy are audited concurrently across multiple industry-standard evaluation engines.
3. **Strict Scale Separation**: Discrete binary (0/1) gatekeepers are segregated from continuous (0.000–1.000) metrics to avoid severe mathematical distortion.
4. **Held-Out Blind Generalization**: Tuning is strictly isolated to a Validation Set (25 cases). A Held-Out Blind Test Set (25 unseen cases) is reserved exclusively for post-tuning verification to ensure zero overfitting.

---

## 2. The Multi-Framework Evaluation Ecosystem

Not-NotebookLM integrates six open-source evaluation frameworks into a unified headless runner (`backend/evaluation/run_benchmark.py`):

| Framework | Citation & Origin | Primary Role & Algorithm | Metric Output Scale |
| :--- | :--- | :--- | :---: |
| **RAGAS** | *Exploding Gradients (EACL 2024)* | Multi-statement atomic claim decomposition + Natural Language Inference (NLI) & vector embedding cosine similarity | Continuous (`0.000 - 1.000`) |
| **DeepEval** | *Confident AI (Microsoft G-Eval)* | G-Eval probabilistic rubric evaluation for factual entailment and non-contradiction | Continuous (`0.000 - 1.000`) |
| **TruLens** | *TruEra* | RAG Triad Groundedness with Chain-of-Thought (CoT) hypothesis verification and QA relevance | Continuous (`0.000 - 1.000`) |
| **Promptfoo** | *Open-Source Red-Teaming* | Model-graded continuous assertion suite verifying prompt adherence and negative abstention | Continuous (`0.000 - 1.000`) |
| **LlamaIndex** | *LlamaIndex Core Engine* | Strict contextual entailment gatekeeper & semantic ground-truth correctness | Binary (`0` or `1`) & Continuous (`0.000 - 1.000`) |
| **Princeton ALCE** | *Princeton NLP (EMNLP 2023)* | Formal Citation Quality Battery: Citation Recall (statement support) + Citation Precision (irrelevant citation detection) | Continuous (`0.000 - 1.000`) |

---

## 3. Two-Tier Scorecard Architecture

To balance executive readability (like mAP in Computer Vision) with full scientific transparency, all benchmark reports are rendered in a **Two-Tier structure**:

```
                              TWO-TIER SCORECARD
                                      │
     ┌────────────────────────────────┴────────────────────────────────┐
     ▼                                                                 ▼
[TIER 1: EXECUTIVE CONSENSUS]                       [TIER 2: DETAILED FRAMEWORK LEDGER]
• Groundedness (Anti-Hallucination)                 • DeepEval G-Eval Score & Reasoning
• Answer Relevancy & Completeness                   • TruLens Triad Groundedness & CoT
• Ground-Truth Correctness (Human GT)               • Ragas Atomic Claim NLI + Embeddings
• Princeton ALCE Citation Quality (Recall/Prec)     • Princeton ALCE Statement Entailment
• Standalone Gate: LlamaIndex Binary Pass/Fail      • LlamaIndex Binary Gatekeeper
```

### Tier 1: The 3 Core Continuous Consensus Pillars

1. **Pillar 1: Groundedness Consensus (Anti-Hallucination)**
   - *Definition:* The ratio of atomic claims in the generated response that are directly supported by the retrieved document chunks.
   - *Formula:*
     $$\text{Consensus Groundedness} = \frac{\text{DeepEval} + \text{TruLens} + \text{Promptfoo} + \text{Ragas}}{4}$$
   - *Production Standard:* $\ge 0.850$.

2. **Pillar 2: Answer Relevancy Consensus**
   - *Definition:* How directly, accurately, and completely the response fulfills the user's specific research query without extraneous digression.
   - *Formula:*
     $$\text{Consensus Relevancy} = \frac{\text{DeepEval} + \text{TruLens} + \text{Promptfoo} + \text{Ragas}}{4}$$
   - *Production Standard:* $\ge 0.850$.

3. **Pillar 3: Ground-Truth Correctness (Dual-Judge Consensus)**
   - *Definition:* Semantic and factual entity alignment between the generated response and the reference answer written by human peer-reviewers, cross-validated by two independent continuous judges to eliminate single-point evaluator failure.
   - *Formula:*
     $$\text{Consensus Correctness} = \frac{\text{LlamaIndex Correctness} + \text{Promptfoo GT Alignment}}{2}$$
   - *Production Standard:* $\ge 0.800$.

4. **Dual-Layer Citation Verification:**
   - **Layer A: Princeton ALCE Citation Quality (Semantic Entailment)**
     - *Citation Recall:* Ratio of statements $s_i$ whose cited passages $C_i$ logically entail $s_i$ under NLI ($\phi(\text{concat}(C_i), s_i) == 1$).
     - *Citation Precision:* Identification and penalization of irrelevant/redundant citations.
     - *Production Standard:* $\ge 0.850$.
   - **Layer B: Interactive Citation Fidelity (Zero-Token Physical Match)**
     - Mathematical verification that every sentence quoted in `<!-- CITATION_MAP -->` exists authentically in the raw physical PDF text via substring and fuzzy matching ($\ge 85\%$) to ensure reader jump-to-highlight stability.
     - *Production Standard:* $\ge 90.0\%$ ($0.900$).

5. **Standalone Gatekeeper: LlamaIndex Strict Binary**
   - *Definition:* An uncompromising pass/fail gatekeeper evaluating whether the entire response is 100% free of unreferenced assertions.
   - *Scale:* Binary integer (`1` = Pass, `0` = Fail).
   - *Rule:* **Explicitly excluded from the continuous arithmetic mean** to prevent scale mismatch distortion.

---

## 4. Mathematical Scale Separation Rule

A critical methodological rule enforced across Not-NotebookLM benchmarks:

$$\text{NEVER mix Binary Gatekeepers } (0 \text{ or } 1) \text{ into Continuous Means } [0.000, 1.000]$$

### The Scale Mismatch Problem:
If a response contains four fully supported scientific claims and one polite conversational preamble (e.g., *"Based on the study..."*), a binary classifier (LlamaIndex) issues a strict `0 (FAIL)`. If averaged naively with continuous scores:
$$\text{Flawed Mean} = \frac{0.920 + 0.880 + 0.900 + \mathbf{0.000}}{4} = \mathbf{0.675} \quad (\text{Artificially Deflated to FAIL})$$

Under Not-NotebookLM methodology:
$$\text{Continuous Consensus} = \frac{0.920 + 0.880 + 0.900}{3} = \mathbf{0.900} \quad (\text{Accurate Grade A})$$
$$\text{Binary Gatekeeper Status} = \mathbf{0 \text{ [Fail]}} \quad (\text{Reported transparently as a gate warning})$$

---

## 5. RAG Ops Optimization & Hill Climbing Playbook

When benchmark scores fall below target thresholds, optimization is executed systematically by targeting the specific failing subsystem:

```
                          METRIC-DRIVEN DIAGNOSIS
                                     │
     ┌───────────────────────────────┴───────────────────────────────┐
     ▼                                                               ▼
[RETRIEVAL BOTTLENECK]                                  [GENERATION BOTTLENECK]
(Context Recall / Precision < 0.80)                     (Groundedness / Relevancy < 0.85)
• Fix Chunker, Top-K & Vector Search                    • Fix System Prompt & Sampling
```

### A. Tuning the Retrieval Pipeline (`backend/rag/`):
| Symptom / Failing Metric | Root Cause | Engineering Action |
| :--- | :--- | :--- |
| **Context Recall < 0.80** | Vital facts/tables split across chunk boundaries | Increase chunk size (e.g., 600 $\to$ 1,000 tokens) in `academic_chunker.py` and raise chunk overlap (e.g., 100 $\to$ 200 tokens). |
| **Context Precision < 0.75** | Relevant excerpts buried beneath irrelevant noise | Increase Qdrant `similarity_top_k` (25 $\to$ 40) and calibrate FlashRank Cross-Encoder reranker depth (`top-12` pruning). |
| **Entity/Acronym Misses** | Dense vectors fail on exact keyword match (`KBQA`, `DL-PS`) | Reinforce BM25 keyword matching alongside dense vector search (Hybrid Search). |

### B. Tuning the Generation / Prompt Pipeline (`backend/rag/prompts.py`):
| Symptom / Failing Metric | Root Cause | Engineering Action |
| :--- | :--- | :--- |
| **NLI Penalty on Groundedness** | Model generates conversational preambles not in text | Enforce zero-preamble directives: *"Directly provide factual findings without introductory chatter or conversational preamble."* |
| **Low Correctness on Metrics** | Model reports relative deltas (`+1.08 F1`) but omits absolute values (`85.99 F1`) | Inject strict quantitative extraction rules: *"When reporting empirical performance, ALWAYS provide exact absolute metric scores alongside relative gains."* |
| **Hallucination on Negative Tests** | Model invents numbers when data is absent | Strengthen negative abstention directives: *"If a requested parameter or metric is not explicitly reported in the text, explicitly state that it is absent without inventing numbers."* |

---

## 6. Overfitting Prevention & Split Separation Protocol

To guarantee that RAG optimizations generalize to real-world scientific literature rather than memorizing test cases, evaluation enforces a **Train-Dev vs. Held-Out Blind Test protocol**:

```
                       50-QUESTION QASPER BENCHMARK
                                     │
     ┌───────────────────────────────┴───────────────────────────────┐
     ▼                                                               ▼
[VALIDATION SET: 25 QUESTIONS]                      [HELD-OUT TEST SET: 25 QUESTIONS]
• 9 arXiv Research Papers                           • 8 Completely Unseen arXiv Papers
• Used for active tuning & prompt iteration         • Strictly blind / untouched during tuning
• Command: --split val                              • Command: --split test
```

### Generalization Acceptance Criteria:
1. **Development Phase**: Tune prompt directives and chunking parameters until the **Validation Set (25 cases)** achieves:
   - Consensus Groundedness $\ge 0.850$
   - Consensus Relevancy $\ge 0.850$
   - Correctness $\ge 0.800$
2. **Blind Verification Phase**: Execute the identical pipeline on the **Held-Out Test Set (25 cases)** *without modifying any prompt or code*.
3. **Generalization Standard**: The Held-Out Test Set score must not drop by more than **5.0%** from the Validation score:
   $$\Delta_{\text{generalization}} = |\text{Score}_{\text{val}} - \text{Score}_{\text{test}}| \le 0.050$$
   - If $\Delta > 0.050$, the system is flagged for prompt overfitting.
   - If $\Delta \le 0.050$, the release is certified for production.

---

## 7. The 3-Tier Evaluation Pyramid (Fast-Val vs. Supreme Court)

Evaluating 25 academic research questions across 5 full frameworks requires **450+ sequential LLM API calls**, taking approximately **2 to 2.5 hours** per run. Running the full suite on every minor prompt tweak creates an intolerable developer bottleneck.

Inspired by software engineering's classic Test Pyramid, Not-NotebookLM organizes evaluation into a **3-Tier Pyramid**:

```
                   THE RAG EVALUATION PYRAMID
                              ▲
                             / \      TIER 3: "Supreme Court" (Full 5 Frameworks)
                            /   \     • DeepEval + TruLens + Promptfoo + Ragas + LlamaIndex
                           /     \    • Frequency: Once per milestone / final release
                          /───────\   • Duration: ~2 to 2.5 Hours
                         /         \
                        /           \  TIER 2: "Fast-Val Suite" (Promptfoo + Ragas)
                       /             \ • The Honest Critic Pair (Dual-Judge + NLI)
                      /───────────────\• Frequency: Daily dev loop & prompt hill climbing
                     /                 \• Duration: ~10 to 15 Minutes
                    /                   \
                   /                     \ TIER 1: "Deterministic Smoke Test" (0 Tokens)
                  /                       \• IEEE Tag Syntax + Verbatim PDF Fuzzy Matching
                 /                         \• Frequency: Every code edit (pre-commit ./check.sh)
                /───────────────────────────\• Duration: ~2 Seconds
```

### Empirical Rationale for the Tier 2 "Fast-Val" Pairing:
Analysis of empirical benchmark data reveals the distinct behavioral archetypes of the evaluators:
1. **RAGAS (`0.605`) and TruLens (`0.622`) are the "Honest Critics"**: Both break text into atomic claims and perform rigorous sentence-level NLI verification. Their verdicts correlate at $>85\%$. Running both simultaneously during rapid development creates unnecessary computational redundancy.
2. **DeepEval (`1.000`) exhibits Leniency Bias**: DeepEval's G-Eval non-contradiction prompt rarely penalizes subtle extrapolations, giving near-perfect scores on academic texts.
3. **Promptfoo (`0.775` - `0.896`) is the "Solid Anchor"**: Promptfoo directly mirrors the consensus average of the entire panel while evaluating all three core pillars (Faithfulness, Relevancy, Correctness) in parallel.
4. **Conclusion**: Running **Promptfoo + RAGAS (`--fast`)** provides $>90\%$ fidelity to the 5-judge consensus while slashing execution time from **2.5 hours to ~12 minutes**.

---

## 8. Execution CLI Commands

All benchmarks are run headlessly from the project root without launching browsers or frontend servers:

```bash
# 1. Fast-Val Mode (~10 mins) for daily development & prompt hill climbing:
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset qasper --split val --fast --concurrency 2

# 2. Supreme Court Full 6-Framework Run (~30 mins) for official release snapshots:
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset qasper --split test --cross-framework --concurrency 2

# 3. 50-Case Comprehensive Multi-Paper Benchmark:
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset full50 --cross-framework --concurrency 2

# 4. Fast smoke-test (first N cases):
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset qasper --split val --limit 3 --fast
```

---

## 9. Artifact Ledger & Reports

Every benchmark run produces persistent, timestamped reports:
- `backend/evaluation/reports/benchmark_cross_framework.md`: Comprehensive two-tier report comparing DeepEval, TruLens, Promptfoo, Ragas, LlamaIndex, and ALCE.
- `backend/evaluation/reports/benchmark_latest.md`: Standard single-track scorecard.
