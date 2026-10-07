<!-- antislop:start -->
## antislop
For UI, copy, people, mobile layout, or code comments work:
1. Read `DESIGN.md` for visual direction, typography, color palette, and dials.
2. Load the corresponding antislop skill as the quality filter:
   - Core filter, always on: `antislop`
   - UI / visual: `antislop-ui`
   - Copy & text: `antislop-copywriting`
   - People: `antislop-human`
   - Mobile / responsive: `antislop-layoutmobile`
   - Code comments: `antislop-code`
Before starting, ask the user when antislop applies: during the work, or after it is done.
<!-- antislop:end -->

## Core Software Engineering Principles (Architecture & Code Quality)
Core software engineering and architectural standards that MUST be upheld when reading, designing, modifying, or refactoring code across this repository:

### 1. SOLID Principles
- **S (Single Responsibility):** Every file, module, and class must have only one single reason to change. Decouple business/calculation logic, persistence/database abstractions, and network/transport layers into independent modules.
- **O (Open/Closed):** Open for extension, closed for modification on core orchestration pipelines. Introduce new external providers, models, or format adapters via isolated interfaces without rewriting the primary execution pipeline.
- **L (Liskov Substitution):** Concrete implementations must be substitutable by mock or in-memory equivalents (e.g. in-memory DB session, mock model callables, mock vector client) without altering functional execution flows or breaking test suites.
- **I (Interface Segregation):** Segregate interface contracts and payload schemas granularly. Avoid monolithic request models or callback interfaces that force consumers to implement unused methods.
- **D (Dependency Inversion):** High-level domain logic and workflow orchestration must never depend directly on rigid, low-level concrete implementations. Both must rely on explicit contracts, interfaces, or dependency injection.

### 2. Composition over Inheritance
Avoid deep, fragile class inheritance hierarchies. Compose complex functionality through modular objects, isolated utilities, and composable stateless functions.

### 3. Encapsulate What Varies
Identify system components that mutate frequently or depend on external vendors (e.g. vendor metadata formats, third-party response schemas, dynamic rate limits) and encapsulate them within isolated adapters or lookup layers to protect core stability.

### 4. Program against Abstractions, Not Implementations
Declare dependencies, parameters, and payloads using strict, typed data contracts (Pydantic models in Python/backend, TypeScript interfaces in frontend) rather than loosely passing raw unstructured dictionaries.

### 5. Hollywood Principle ("Don't Call Us, We'll Call You" / IoC)
Control application lifecycle and initialization from top-level composition roots. Processing modules and pipelines receive dependencies and event callbacks (e.g. listeners, streaming emitters) from callers without needing internal knowledge of the final transport layer.

### 6. DRY (Don't Repeat Yourself)
Eliminate duplicated business logic, calculation formulas, or contract definitions. Every representation of domain knowledge and validation rule must have an authoritative single source of truth.

### 7. YAGNI (You Aren't Gonna Need It)
Do not build speculative configurations, hypothetical abstraction layers, or over-engineered features before an actual, tangible requirement emerges. Prioritize modular solutions that directly solve immediate engineering goals.

### 8. Orthogonality
Design modules to operate independently without hidden side-effects. UI styling changes must never alter API payloads; benchmark harness updates must never perturb runtime serving behavior; internal refactoring in one module must not regress neighboring subsystems.

### 9. Reversibility
Every state mutation, database schema migration, and conversational flow must maintain a clean rollback or recovery path. Retain audit trails for critical data and implement safe fallback mechanisms for unexpected downstream failures.

### 10. Tell, Don't Ask
Instruct objects and services to execute domain operations on their own encapsulated data, rather than querying internal states and imperatively mutating them outside the service boundary.

### 11. Law of Demeter (Principle of Least Knowledge)
Components must only interact with their immediate dependencies. Avoid multi-hop access chains that inspect internal structures of distant objects; expose direct helper methods or interfaces instead.

### 12. Clean Code & Surgical Edits
Write concise, explicitly typed functions with intentional naming. Every code modification must be executed with surgical precision—touching only lines directly relevant to the assigned task without gratuitous reformatting or unsolicited refactoring of adjacent code.

## AI & RAG System Design Laws (Empirical Rules & Operational Bounds)
Empirical laws, heuristics, and operational bounds that must be understood when designing, optimizing, or refactoring RAG pipelines in this repository:

### 1. Spolsky's Law of Leaky Abstractions (Mitigating Vector & PDF Illusions)
- **RAG Reality:** Abstractions are never completely watertight. Cosine similarity in vector databases is not synonymous with semantic truth (vulnerable to out-of-domain embeddings and semantic drift), and raw PDF text extraction is not a lossless spatial representation.
- **Project Implementation:** Never treat vector databases or PDF parsers as infallible black boxes. Maintain defense-in-depth: hybrid dense + sparse lexical retrieval, cross-encoder reranking, and deterministic citation verification (verbatim PDF substring matching) before presenting answers.

### 2. Hyrum's Law (LLM Interface Contracts for Downstream UI/Tools)
- **RAG Reality:** Every observable detail of LLM output formatting (spacing, citation bracket style `[^1]`, JSON schemas, Markdown markers) inevitably becomes an implicit dependency for downstream parsers (document reader, UI highlighter, downstream summarizers).
- **Project Implementation:** Enforce strict schema validation (Pydantic in backend, Zod/TypeScript in frontend). Never introduce ad-hoc prompt formatting changes without updating parser schemas and validating visual compatibility in the UI reader.

### 3. Goodhart's Law (Evaluation Benchmark Integrity vs Human UX)
- **RAG Reality:** *"When a measure becomes a target, it ceases to be a good measure."* Aggressively over-optimizing prompts solely to maximize synthetic benchmark scores risks producing rigid, robotic answers or excessive abstention on valid user queries.
- **Project Implementation:** Treat multi-framework benchmarks as regression guardrails rather than singular targets. Balance strict factual attribution (*faithfulness*) with natural, clear scientific synthesis (*answer relevancy & clarity*).

### 4. Postel's Law / Robustness Principle (Tolerant Ingestion, Strict Emission)
- **RAG Reality:** *"Be conservative in what you send, liberal in what you accept."* Raw scientific PDF text and streaming LLM tokens frequently contain defects: broken LaTeX, truncated Markdown blocks, and interrupted token streams.
- **Project Implementation:** Internal ingestion parsers (chunker, token cleaner, regex highlighter) must be designed to be forgiving and resilient against messy inputs, whereas API payloads emitted to the frontend or database must be strictly sanitized and typed.

### 5. Wirth's & Amdahl's Laws (Pipeline Efficiency vs Inference Latency)
- **RAG Reality:** Software slows down faster than hardware accelerates, and end-to-end latency is bound by the slowest sequential component. Excessive sequential LLM round-trips drastically degrade user experience.
- **Project Implementation:** Keep pipelines lean. Avoid adding sequential agentic reflection loops without measurable benchmark justification. Maintain responsive first-token streaming (Time-to-First-Token < 3 seconds).

### 6. Zipf's Law (Document Caching & Embedding Reuse)
- **RAG Reality:** Academic query distributions follow Pareto/Zipf patterns: ~20% of core paper sections (Abstract, Methodology, Key Findings) absorb ~80% of user access frequency.
- **Project Implementation:** Implement intelligent dual-tier caching across embeddings and document metadata for frequently accessed papers to eliminate redundant retrieval latency and unnecessary API compute.

### 7. Gall's Law (Complex Systems Evolve from Simple Foundations)
- **RAG Reality:** A complex system that works invariably evolves from a simple system that worked. Attempting to design autonomous dynamic multi-agent graphs before stabilizing deterministic retrieval pipelines leads to fragile failure modes.
- **Project Implementation:** Solidify foundational chunking accuracy, hybrid retrieval, and deterministic citation before adding intricate multi-hop query decomposition.

### 8. Operational Boundaries / Out-of-Scope (YAGNI Guardrail)
- **CAP Theorem & Raw Distributed Sharding:** Current architecture is built upon FastAPI + SQLite (`not_notebooklm.db`) + single-node Qdrant. Do not introduce speculative distributed consensus protocols before a proven multi-region operational requirement exists.
- **Cluster VRAM Scheduling:** This repository acts as an API consumer to upstream model providers. Concurrency management focuses on async semaphores, connection pooling, and rate-limiting (RPM/TPM) rather than low-level GPU KV-cache allocation.

## Agent Guardrails & Dialectical Operating Rules (Anti-Sycophancy, Zero Assumption & Strict Code Review)
Mandatory interaction and engineering guardrails between user and agent that must be strictly followed without compromise:

### 1. Zero Hallucination & Anti-Sycophancy (Egalitarian & Fact-Based)
- **No Sycophancy:** The relationship between user and agent is that of an **egalitarian and dialectical** technical peer. Never reflexively apologize, flatter, or concede a technical point simply because the user challenges or questions a finding.
- **Show, Don't Just Tell (Empirical Proof):**
  - Never claim a bug, third-party API limitation (Google, OpenAI, Anthropic), or system failure based on memory or training assumptions alone.
  - Verify hypotheses directly via minimal reproduction scripts, terminal execution, or live scraping/fetching of official documentation.
  - If a user assertion is technically incorrect, present polite, evidence-backed arguments explaining the concrete failure mechanism.
  - If the agent is mistaken, acknowledge it objectively based on technical evidence without defensive rhetoric.
- **Distinguish Issue Severity:** Clearly categorize findings between **Hard Blockers / Fatal Bugs** (demonstrated reproduction failure/crash) vs **Architectural / Optimization Suggestions** (style, clean code, maintainability).

### 2. Don't Make Assumptions — Stop & Clarify Gaps
- **Prohibit Execution on Unverified Assumptions:** If user requirements define steps A through Y but leave step Z ambiguous (e.g. legacy data migration strategy, offline fallbacks, breaking schema implications), **DO NOT guess and execute unilaterally**.
- **Proactive Clarification:** Stop, identify the unaddressed architectural trade-off or gap, and ask the user for direction using structured options (utilizing the interactive `question` tool when applicable).
- **Confirmation on Irreversible Actions:** Never delete files, modify default models that cause dimension mismatches, overwrite production benchmark baselines, or alter major dependencies without explicit user authorization.

### 3. Strict Git Invariant: FORBIDDEN AUTO-COMMIT / AUTO-PUSH
- **Strict User Authorization Gate:** The agent is **STRICTLY FORBIDDEN** from running `git commit`, `git push`, creating tags, or merging branches autonomously without an **explicit instruction** from the user ("commit now", "push now", "ok commit", etc.).
- **Mandatory Pull Request Lifecycle (No Naked Merges into `main`):**
  - Every non-trivial feature, refactor, or bugfix **MUST** transition through a formal GitHub Pull Request (`gh pr create`) before being merged into `main`. Direct or naked branch merges into `main` without an associated PR are strictly forbidden.
  - **Standard Engineering Lifecycle:**
    1. **Branch & Implement:** Develop on an isolated branch (`feat/<name>-#<id>`, `fix/<name>-#<id>`).
    2. **Local Verification:** Run test suites (`vitest`, `pytest`, `npm run build`, `ruff check`).
    3. **Push & Open PR:** Push the feature branch and open a PR via `gh pr create` linking the relevant issue (`Closes #<id>`).
    4. **AI Code Review on PR:** Execute `ocr review --audience agent --from main --to <branch>` to review the PR diff cleanly.
    5. **Dialectical Verification & Scorecard:** Present findings to the user (Confirmed Bugs vs False Positives). Apply verified fixes surgically.
    6. **User Authorization Gate:** Present the clean PR status and await explicit user instruction to merge.
    7. **Merge & Release:** Merge via `gh pr merge --merge`, create SemVer tag (`vX.Y.Z`), synchronize `docs/TECHNICAL_STACK_AND_PIPELINES.md`, and publish GitHub Release.
- **Report Status First:** Upon task completion, present a concise summary of changes, test suite results, and linter status, and await user instruction. Inquiring for confirmation ("Would you like to commit?") is permitted, but executing commit/push without explicit confirmation is prohibited.
- **Living Architecture Specification Synchronization:** Whenever system architecture, engine dependencies, or core operational workflows are committed or merged into `main`, `docs/TECHNICAL_STACK_AND_PIPELINES.md` **MUST BE SYNCHRONIZED** within the same commit so the documentation remains an accurate reference for continuous study.
- **Strict English Consistency Across Repository Artefacts:** All documentation files (`*.md`), technical specifications, GitHub Issues, Pull Request descriptions, Git commit messages, and GitHub Release notes **MUST BE WRITTEN EXCLUSIVELY IN CLEAR, CONCISE ENGLISH**. Maintain strict language consistency across all repository artefacts for international open-source parity.
- **System Versioning & Release Discipline (SemVer `vX.Y.Z`):**
  - Increment version whenever functional, architectural, or system capabilities are modified:
    - **Major (`X`, e.g. `1.x -> 2.0.0`):** Fundamental architectural rewrites, new binary runtimes, breaking CLI changes, or major platform eras.
    - **Minor (`Y`, e.g. `1.9.1 -> 1.10.0`):** Significant new features, new administrative planes, or system pipeline additions that are backwards-compatible.
    - **Patch (`Z`, e.g. `1.9.0 -> 1.9.1`):** Bug fixes, security patches, dependency modernizations, or minor optimizations.
  - **No Version Bump on Documentation:** Pure documentation edits, typo fixes, or evaluation dataset curation do not trigger a version bump.
  - **UI Version Synchronization:** When bumping the version, synchronize `frontend/package.json` and ensure the Left Sidebar footer (`vX.Y.Z`) accurately reflects the current active release.
  - **Release Publication:** Publish GitHub releases with concise English release notes, tagging the commit corresponding to the merge on `main`.

### 4. Code Review Scientific Verification Protocol (Anti-Hallucinated Findings)
When conducting AI Code Reviews (via `ocr review`, dual LLM evaluations, or manual review), the agent **MUST NOT ACCEPT REVIEWER FINDINGS AT FACE VALUE OR ACT AS A SYCOPHANT TO REVIEW BOTS**. Follow a mandatory, evidence-backed verification protocol before touching any code:

- **Mandatory User Presentation Before Applying Changes:**
  - The agent is **STRICTLY FORBIDDEN** from unilaterally modifying code, committing, or merging fixes immediately after receiving automated review comments without first presenting the findings dialectically to the user.
  - Present a structured scorecard: categorize items into **Hard Blockers / Confirmed Bugs** vs **False Positives / Rejected Claims** vs **Architectural Optimizations**, complete with reproduction proof.

- **Step 1: Problem Validity Verification (Is this a genuine defect or a hallucination/misunderstanding?):**
  - **Never Assume Validity:** Treat reviewer comments with healthy skepticism. LLM reviewers frequently misread token-truncated code, misunderstand project conventions, or flag stylistic non-issues as critical bugs.
  - **Define the Concrete Failure Scenario:** *"Under what exact inputs, network conditions, or concurrency state does this failure occur, and what is the exact stack trace or measurable impact?"*
  - **Execute an Empirical Reproduction Script:** Run a minimal terminal script, curl command, or test assertion to test the failure hypothesis.
  - **Classification:**
    - If reproduction confirms an actual error, crash, security loophole, or measurable regression: classify as **CONFIRMED REAL ISSUE** with log/terminal evidence.
    - If reproduction passes cleanly, or the claim is based on truncated files, obsolete syntax, or false assumptions: reject the finding dialectically with proof as **FALSE POSITIVE / REJECTED**. Do not modify code for rejected items.

- **Step 2: Solution Validity & Orthogonality Verification:**
  - **Never Blindly Apply Suggested Diff:** Review bot fix suggestions are often naive, incomplete, or break neighboring invariants. Critically evaluate whether the suggested fix genuinely addresses the root cause or just silences a linter.
  - **Surgical Implementation:** Apply the verified solution with minimal footprint.
  - **Dual Verification:**
    1. Re-run the reproduction script from Step 1 to verify the defect is genuinely eliminated.
    2. Run full test suites (`pytest`, `vitest`, `ruff check`, and build commands) to verify zero regressions across neighboring systems.

### 5. Execution & Timeout Vigilance (Heavy Workflows)
- Heavy CLI tasks (multi-framework benchmarks, full test suites, `ocr review`) must explicitly specify sufficient timeouts (minimum `timeout: 300000` / 5 minutes) or be directed to persistent log files to prevent mid-execution truncation.

### 6. Developer Environment & Frontend Tooling Runtime (Bun & Node.js)
- **Local macOS Optimization (Bun):** When `bun` is available on the local environment (`which bun`), developers and AI agents SHOULD prefer using `bun` for local frontend operations (`bun run dev`, `bun run test`, `bun run lint`, `bun run type-check`, `bun run build`) due to its significantly lower idle memory, instant startup, and battery efficiency on Apple Silicon.
- **Test Runner Protocol:** Always invoke frontend test suites via `bun run test` (or `npm test`) so that `vitest run` is executed. Do NOT invoke raw `bun test` directly, as Bun's internal standalone test runner lacks the DOM environment (`jsdom`) configured for component testing.
- **Universal Git & CI Parity:** `frontend/package-lock.json` remains the strict, authoritative package lockfile in version control to guarantee deterministic builds in GitHub Actions CI (`.github/workflows/ci.yml`) and across all contributor environments. Do not commit alternative lockfiles (`bun.lock` / `bun.lockb`).

## Automated RAG Evaluation & Multi-Framework Benchmarking
When modifying or refactoring components under `backend/rag/` (chunking, system prompts, vector search, or synthesis pipelines):
1. **Do not rely solely on qualitative spot-checks.**
2. **Execute the automated benchmark harness** to assess quantitative metrics across datasets and frameworks:
   ```bash
   # Fast-Val daily development loop (25-Case Held-Out Val Suite, ~6-8 mins):
   PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset val25 --fast --concurrency 2

   # 100-Case Comprehensive Scientific Benchmark (Held-Out Test Set / Supreme Court Release Snapshot):
   PYTHONPATH=backend backend/venv/bin/python backend/evaluation/run_benchmark.py --dataset full100 --split test --cross-framework --concurrency 2

   # 100-Case Conversational Memory Benchmark (4 Quadrants: Single-Needle, Multi-Needle, Reasoning, and Negative Abstention):
   PYTHONPATH=backend backend/venv/bin/python backend/evaluation/eval_full50_niah.py --split test --mode both --concurrency 2
   ```
   (Options: `--limit N`, `--split [val|test]`, `--category [single_fact|multi_comparative|negative_unanswerable]`, `--fast`, `--cross-framework`, `--concurrency N`)

3. **CRITICAL METHODOLOGY RULE (Scale Separation & Dual-Judge Correctness):**
   - **NEVER** calculate arithmetic means by mixing binary 0/1 gatekeepers (like LlamaIndex `FaithfulnessEvaluator`) with continuous 0.000–1.000 metrics (DeepEval, TruLens, Promptfoo, Ragas, ALCE).
   - LlamaIndex must remain a standalone binary **Pass/Fail Gatekeeper**.
   - Continuous Consensus Groundedness is strictly computed across continuous judges: **DeepEval + TruLens + Promptfoo + Ragas**.
   - Citation Quality is formally verified across dual layers: **Princeton ALCE Citation Recall/Precision** (semantic entailment) + **Deterministic PDF Substring Matching** (physical reader jump-to-highlight).
   - Ground-Truth Correctness is cross-validated via **Dual-Judge Consensus**: LlamaIndex `CorrectnessEvaluator` + Promptfoo GT Alignment.
   - Percentage metrics (Citation Fidelity) are normalized to 0.000–1.000 (e.g. 100% = 1.000).

4. **Available Scientific Datasets in `backend/evaluation/datasets/`:**
   - `full100_benchmark.json` (100-case comprehensive test suite: 25 QASPER + 25 SciFact + 25 Multi-Paper + 25 Unanswerables)
   - `val25_benchmark.json` (25-case held-out validation suite: 8 QASPER + 8 SciFact + 5 Multi-Paper + 4 Unanswerables)
   - `niah_100_matrix.json` (100-case conversational memory test matrix: 25 Single-Needle + 25 Multi-Needle Tracking + 25 Reasoning & Superseding Rules + 25 Negative Abstention Traps)
   - `niah_val25_matrix.json` (25-case conversational memory validation matrix: 7 Single-Needle + 6 Multi-Needle Tracking + 6 Reasoning & Superseding Rules + 6 Negative Abstention Traps)
   - `scifact/` (AllenAI SciFact - scientific claim verification)
   - `qasper_multi_benchmark.json` (Multi-paper comparative synthesis & cross-document validation)

5. **Production Standards:**
   - **Groundedness Consensus:** >= 0.850
   - **Answer Relevancy Consensus:** >= 0.850
   - **ALCE Citation Recall & Precision:** >= 0.850
   - **Interactive Citation Fidelity (PDF verbatim match):** >= 90.0% (1.000)
   - **Negative Abstention Honesty:** 1.000 (No fabricated numbers/claims on absent data)

6. The runner generates a two-tier scorecard in terminal and updates:
   - `backend/evaluation/reports/benchmark_cross_framework.md` (Multi-framework consensus)
   - `backend/evaluation/reports/benchmark_latest.md` (Standard benchmark run)
