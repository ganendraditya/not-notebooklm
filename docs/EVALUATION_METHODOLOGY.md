# Not-NotebookLM RAG Evaluation & Benchmarking Methodology
*A Rigorous, Multi-Framework Scientific Evaluation Standard for Academic AI Research Assistants*

---

## 1. Executive Overview & Core Philosophy

In traditional Machine Learning (ML), models are evaluated on numerical labels or structured classifications using metrics such as Precision, Recall, F1-Score, or RMSE. In contrast, Retrieval-Augmented Generation (RAG) produces open-ended natural language, where identical semantic facts can be phrased in countless ways, and where subtle word changes can introduce subtle hallucinations.

To avoid subjective qualitative spot-checks ("eyeball engineering") and prevent **LLM Self-Preference Bias**, Not-NotebookLM establishes a formal **Dual-Track, Multi-Framework Scientific Evaluation Methodology**.

### Core Evaluation Invariants:
1. **No Cherry-Picking**: Evaluation questions and document contexts are sourced sequentially from peer-reviewed scientific datasets (AllenAI QASPER, AllenAI SciFact, Princeton ALCE) without manual curation of favorable cases.
2. **Multi-Judge Consensus**: No single AI model or framework has absolute authority. Groundedness and Relevancy are audited concurrently across multiple industry-standard evaluation engines.
3. **Strict Scale Separation**: Discrete binary (0/1) gatekeepers are segregated from continuous (0.000–1.000) metrics to avoid severe mathematical distortion.
4. **Comprehensive Academic Research Corpus**: Evaluates across a 75-case benchmark balancing four distinct academic modalities: Single-Paper Deep Comprehension (25 unique arXiv papers), Biomedical Claim Verification (25 unique PubMed papers), Multi-Paper Comparative Synthesis (15 workspaces with 2, 3, and 4 documents), and Negative Abstention Traps (10 unanswerable queries). All 50 underlying documents are unique with zero paper reuse.

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
| **Low Correctness on Metrics** | Model reports relative deltas (`+1.5% F1`) but omits absolute values (`94.2% F1`) | Inject strict quantitative extraction rules: *"When reporting empirical performance, ALWAYS provide exact absolute metric scores alongside relative gains."* |
| **Hallucination on Negative Tests** | Model invents numbers when data is absent | Strengthen negative abstention directives: *"If a requested parameter or metric is not explicitly reported in the text, explicitly state that it is absent without inventing numbers."* |

---

## 6. Dataset Topology & Scientific Modalities

The 75-case benchmark (`--dataset full75` or `--dataset full50`) rigorously balances four authentic, peer-reviewed scientific modalities across 50 unique physical papers:

```text
                       75-CASE SCIENTIFIC BENCHMARK
                                     │
     ┌───────────────────┬───────────┴───────┬───────────────────┐
     ▼                   ▼                   ▼                   ▼
[SINGLE-PAPER DEEP]  [BIOMEDICAL AUDIT]  [MULTI-PAPER REVIEW]  [ABSTENTION TRAPS]
• 25 Cases (QASPER)  • 25 Cases (SciFact)• 15 Cases (MUL)     • 10 Cases (Traps)
• 25 Unique arXiv    • 25 Unique PubMed  • 2, 3, & 4 Papers  • Authentic Unans
• Tables & methods   • Lab evidence NLI  • Matrix Synthesis  • Zero Hallucination
```

### Modality Breakdown:
1. **Single-Paper Deep Comprehension (25 Cases)**: 25 distinct full-text arXiv papers from AllenAI QASPER covering sequence labeling, NMT, entity linking, and speech.
2. **Biomedical Scientific Fact-Checking (25 Cases)**: 25 distinct PubMed medical papers from AllenAI SciFact auditing claims against lab evidence (13 `SUPPORT`, 12 `CONTRADICT`).
3. **Multi-Paper Comparative Synthesis (15 Cases)**: Workspaces varying across document volumes—9 cases with 2 papers, 4 cases with 3 papers, and 2 cases with 4 papers—verifying cross-paper matrix tables and isolated citation tags (`[1]`, `[2]`, `[3]`, `[4]`).
4. **Negative Abstention & False Premises (10 Cases)**: Authentic unanswerable research inquiries from AllenAI annotators verifying that the system cleanly abstains rather than fabricating numbers.

### Production Quality Acceptance Criteria:
1. **Consensus Groundedness**: $\ge 0.850$ (Continuous 4-Judge: DeepEval, TruLens, Promptfoo, Ragas)
2. **Consensus Relevancy**: $\ge 0.850$ (Continuous 4-Judge)
3. **Ground-Truth Correctness**: $\ge 0.800$ (Dual-Judge: LlamaIndex + Promptfoo)
4. **Princeton ALCE Quality**: Citation Recall $\ge 0.800$, Citation Precision $\ge 0.750$
5. **Interactive Citation Fidelity**: $\ge 90.0\%$ (PDF verbatim match)
6. **Negative Abstention Honesty**: 1.000 (Zero fabricated numbers or mechanisms on absent data)

---

## 7. The 3-Tier Evaluation Pyramid (Fast-Val vs. Supreme Court)

Evaluating 75 academic research questions across 6 full frameworks requires **700+ asynchronous LLM API calls**, taking approximately **30 to 40 minutes** under `concurrency=2`.

Inspired by software engineering's classic Test Pyramid, Not-NotebookLM organizes evaluation into a **3-Tier Pyramid**:

```text
                   THE RAG EVALUATION PYRAMID
                              ▲
                             / \      TIER 3: "Supreme Court" (All 6 Frameworks)
                            /   \     • DeepEval + TruLens + Promptfoo + Ragas + LlamaIndex + ALCE
                           /     \    • Frequency: Release snapshots & major pipeline changes
                          /───────\   • Duration: ~30 to 40 Minutes
                         /         \
                        /           \  TIER 2: "Fast-Val Suite" (Promptfoo + Ragas + LlamaIndex)
                       /             \ • The Fast Consensus Triple (Dual-Judge + NLI + Gate)
                      /───────────────\• Frequency: Daily dev loop & prompt hill climbing
                     /                 \• Duration: ~12 to 15 Minutes
                    /                   \
                   /                     \ TIER 1: "Deterministic Smoke Test" (0 Tokens)
                  /                       \• IEEE Tag Syntax + Verbatim PDF Fuzzy Matching
                 /                         \• Frequency: Every code edit (pre-commit ./check.sh)
                /───────────────────────────\• Duration: ~2 Seconds
```

### Empirical Rationale for the Tier 2 "Fast-Val" Pairing:
Analysis of empirical benchmark data reveals the distinct behavioral archetypes of the evaluators:
1. **RAGAS (`0.850`–`0.920`) and TruLens (`0.880`–`0.960`) are the "Honest Critics"**: Both break text into atomic claims and perform rigorous sentence-level NLI verification. Their verdicts correlate at $>85\%$. Running both simultaneously during rapid development creates unnecessary computational redundancy.
2. **DeepEval (`0.980`–`1.000`) exhibits Leniency Bias**: DeepEval's G-Eval non-contradiction prompt rarely penalizes subtle extrapolations, giving near-perfect scores on academic texts.
3. **Promptfoo (`0.890`–`0.960`) is the "Solid Anchor"**: Promptfoo directly mirrors the consensus average of the entire panel while evaluating all three core pillars (Faithfulness, Relevancy, Correctness) in parallel.
4. **Conclusion**: Running **Promptfoo + Ragas + LlamaIndex (`--fast`)** provides $>92\%$ fidelity to the 6-judge consensus while slashing execution time to **~10 minutes**.

---

## 8. Execution CLI Commands

All benchmarks are run headlessly from the project root without launching browsers or frontend servers:

```bash
# 1. 75-Case Comprehensive Scientific Benchmark (All 4 Modalities):
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset full75 --cross-framework --concurrency 2

# 2. Fast-Val Mode (~12 mins) across the 75-case suite:
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset full75 --fast --concurrency 2

# 3. Subsystem Targeted Benchmarks:
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset qasper_multi --cross-framework
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset scifact --cross-framework

# 4. Fast smoke-test (first N cases):
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset full75 --limit 3 --fast
```

---

## 9. Artifact Ledger & Reports

Every benchmark run produces persistent, timestamped reports:
- `backend/evaluation/reports/benchmark_cross_framework.md`: Comprehensive two-tier report comparing DeepEval, TruLens, Promptfoo, Ragas, LlamaIndex, and ALCE.
- `backend/evaluation/reports/benchmark_latest.md`: Standard single-track scorecard.

---

## 10. Evaluator Harness Robustness & Anti-Distortion Defenses

To prevent false penalties and artificial benchmark inflation, Not-NotebookLM's test harness incorporates four defensive invariants:

1. **Unconstrained LlamaIndex Context Flow**:
   - Evaluator context is passed dynamically without arbitrary front-truncation (e.g. `[:4000]`), allowing the LlamaIndex Relevancy evaluator to review full manuscript methodology and empirical tables.
2. **Parallel Statement Chunking & Balanced-Braces JSON Recovery (Princeton ALCE)**:
   - For complex multi-paper comparison tables (20–40 atomic statements), statements are audited in parallel batches of 8.
   - The parser utilizes balanced-braces JSON recovery to preserve all intact statement evaluations even if output tokens truncate the final array bracket, preventing false `0.000 (FAIL)` collapses.
3. **1:1 Sample ID Mapping (Ragas)**:
   - Ragas batch scores are mapped to cross-framework reports via strict `sample_id` key-value pairs rather than positional indices.
   - Unanswerable cases (where Ragas context recall is mathematically undefined) are excluded cleanly without causing off-by-N shifts in subsequent test cases.
4. **Zero Few-Shot Prompt Leakage**:
   - System prompts are sanitized of dataset-specific empirical numbers, enforcing general stylistic precision rather than biased target values.
