# Technical Stack, Data Stores & System Pipeline Specification

Comprehensive technical specification document for **Not-NotebookLM**: an academic AI Workspace & Research Assistant powered by verifiable scientific Retrieval-Augmented Generation (RAG). This document details the system architecture, core technology stack components, orchestration pipelines (ingestion, discovery, retrieval, synthesis), Fast LLM micro-tasks, storage and database mechanics, and evaluation guardrails.

---

## 1. High-Level System Architecture

Not-NotebookLM is built on a decoupled architecture (separated Client-Server, headless Vector Database, and pluggable Hybrid Object Storage):

```
+-----------------------------------------------------------------------------------+
|                        FRONTEND CLIENT (Next.js 16 + Tailwind v4)                 |
|  - Split-Pane Reader: PDF / DOCX / Markdown view with dynamic citation jump       |
|  - Real-time SSE Chat: Token-by-token streaming, Markdown math, interactive badges|
|  - Literature Discovery Modal: Search, triage, bulk ingest, racing download logs  |
|  - Research Profile Manager: Active constraints, objectives, and domain memory    |
+-----------------------------------------+-----------------------------------------+
                                          |
                        HTTP / SSE Events | JSON Payload
                                          v
+-----------------------------------------------------------------------------------+
|                           BACKEND API (FastAPI + Pydantic v2)                     |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                        LLM Gateway & Cascading Factory                      |  |
|  |  - Primary / Heavy LLM (LLM_MODEL, max 16k output tokens, 120s timeout)     |  |
|  |  - Fast / Lite LLM (LLM_FAST_MODEL, max 4k output tokens, 45s timeout)      |  |
|  |  - Fallback LLM (LLM_FALLBACK_MODEL, automatic failover)                    |  |
|  |  * Input context window is dynamic & auto-detected via token_budget.py      |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                          Core Orchestration Pipelines                       |  |
|  |  1. Semantic Intent Classifier (4-Class triage + micro-dialogue context)     |  |
|  |  2. Document Ingestion & Section Chunker (9 Academic Canonical Centroids)    |  |
|  |  3. Multi-Engine Literature Discovery (OpenAlex, Crossref, Europe PMC, DDG) |  |
|  |  4. Parallel PDF Racing Resolver (arXiv, Unpaywall, OpenAlex, Scrapers)      |  |
|  |  5. Dual-Mode RAG Engine (Direct Context Packing vs Dense + BM25 Hybrid)    |  |
|  |  6. Declarative Research Profile Memory (Constraints, Hardware, Objectives) |  |
|  |  7. Verbatim Citation Highlighter & Evidence Verifier (ALCE compliance)     |  |
|  +-----------------------------------------------------------------------------+  |
+-------------------+--------------------+--------------------+---------------------+
                    |                    |                    |
                    v                    v                    v
         +---------------------+ +------------------+ +-------------------+
         | Relational Database | | Vector Database  | |  Object Storage   |
         |  SQLite3 (WAL Mode) | | Qdrant (Hybrid)  | | Local Disk / S3 / |
         |  Citations, Memory  | | Dense + BM25 RRF | | Cloudflare R2     |
         +---------------------+ +------------------+ +-------------------+
```

---

## 2. Core Technology Stack Matrix

| Layer / Domain | Technology Component | Version / Specification | Architectural Purpose & Rationale |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | Next.js (App Router) | `16.3.1` (React 19, Turbopack) | Server-side rendering (SSR), high-performance client state hydration, zero-flicker SSE listeners. |
| **Backend Web API** | FastAPI | `0.141.1` | Asynchronous REST server, automatic validation via Pydantic v2, native SSE streaming. |
| **Styling & Design** | Tailwind CSS | `v4` (`@tailwindcss/postcss`) | Modern atomic CSS layout, custom design tokens, zero-runtime bloat. |
| **State Management** | Zustand | `5.0.15` | Lightweight client-side state management, non-boilerplate for documents, chat state, and UI. |
| **Scientific Math** | KaTeX + Remark/Rehype | `katex 0.18`, `remark-math 6`, `rehype-katex 7` | Renders mathematical formulas and LaTeX scientific equations in reader and chat. |
| **Markdown Engine** | react-markdown | `10.1.0` + `remark-gfm` | Renders GitHub Flavored Markdown, tables, checklists, and blockquotes. |
| **RAG Orchestrator** | LlamaIndex Core | `>= 0.11.0` | Document abstraction, vector store index, retriever nodes, dynamic chat messages. |
| **LLM Gateway Client**| `llama-index-llms-openai-like` | `>= 0.2.0` | Connects to OpenAI-compatible gateways (9Router, LiteLLM, Ollama, OpenRouter). |
| **Vector Database** | Qdrant Client | `>= 1.12.0` | High-performance vector database, compatible with remote servers or embedded disk persistence. |
| **Dense Semantic Embedding** | FastEmbed ONNX | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dim) | Default local offline dense embeddings (50+ languages), zero external API cost, 100% CPU-native via ONNX Runtime (Zero-PyTorch). |
| **Alternative Embedding** | Google GenAI | `models/gemini-embedding-001` (3072 dim) | High-accuracy Google cloud embedding via `llama-index-embeddings-google-genai` (auto-routed to `not_notebooklm_gemini_3072`). |
| **Sparse Lexical BM25** | FastEmbed | `>= 0.8.0, < 0.9.0` (`Qdrant/bm25`) | Ultra-lightweight ONNX tokenizer & sparse embedding generator for exact keyword, DOI, and acronym matching (Issue #9). |
| **Cross-Encoder Reranker** | FlashRank | `0.2.10` (`ms-marco-TinyBERT-L-2-v2`) | Ultra-fast (<10ms) cross-encoder based on ONNX/in-memory singleton without heavy GPU dependencies. |
| **Relational Database** | SQLite (WAL Mode) | SQLite3 via SQLAlchemy `2.0.52` | Persistent storage for document metadata, chat sessions, messages, citations, and memory profiles. |
| **Object Storage Adapter**| Boto3 S3 Client | `>= 1.34.0` | Unified adapter for Cloudflare R2, self-hosted MinIO, or AWS S3 with disk fallback. |
| **PDF Extraction Engine**| PyMuPDF4LLM | `1.28.2` | Multi-column reading order aware academic parser, preserving tables & scientific formatting. |
| **DOCX Extraction** | python-docx | `1.2.0` | Parses Microsoft Word DOCX documents into clean structured text. |
| **Search Engines** | DuckDuckGo Search | `>= 7.0.0` | Fallback web crawler when external academic registries yield sparse results. |
| **Token Budgeting** | Tiktoken | `>= 0.7.0` | Precise token counting per OpenAI/compatible model family for dynamic context allocation. |
| **Code Hygiene** | Ruff | `>= 0.8.0` | High-speed linter & formatter enforcing Python code quality standards. |
| **Testing Harness** | Pytest + Vitest | `pytest 9.1`, `vitest 4.1` | Isolated testing for backend (asyncio) and frontend UI components. |

---

## 3. Storage & Database Architecture

The system employs a **Tri-Layer Storage** approach ensuring persistence, query performance, and cloud portability:

```
+------------------------------------------------------------------------------------+
|                               STORAGE & PERSISTENCE                                |
+----------------------------+-----------------------------+-------------------------+
| 1. SQLite Relational DB    | 2. Qdrant Vector DB         | 3. File & Media Storage |
|    (backend/not_notebooklm.db)|    (backend/qdrant_data/)   |    (Local / S3 / R2)    |
| - ChatSessions             | - not_notebooklm_fastembed  | - Original PDF / DOCX   |
| - Documents (metadata)     | - not_notebooklm_e5 (legacy)| - Chat Media / Images   |
| - ChatMessages (variants)  | - not_notebooklm_gemini_3072| - .parsed_cache/ (MD)   |
| - CitationHighlights       | - not_notebooklm_gemini     | - temp_zips/ (Export)   |
| - ResearchProfiles (Memory)| - Hybrid: Dense + BM25 RRF  |                         |
|                            | - Metadata filters:         |                         |
|                            |   chat_id, filename, section|                         |
+----------------------------+-----------------------------+-------------------------+
```

### 3.1 Relational Database (`SQLite` via SQLAlchemy 2.0)
- **Path:** `backend/not_notebooklm.db` (can be redirected to PostgreSQL via `DATABASE_URL`).
- **Concurrency Mode:** SQLite executes with `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, `PRAGMA busy_timeout=30000;` (30-second lock timeout for write concurrency), and `PRAGMA foreign_keys=ON;`.
- **Primary Tables:**
  1. `chat_sessions`: `id` (UUID), `title`, `is_pinned`, `created_at`, `updated_at`.
  2. `documents`: `id`, `chat_id`, `filename`, `title`, `authors` (JSON), `year`, `journal`, `journal_metric`, `doi`, `url`, `pdf_url`, `abstract`, `abstract_type`, `is_oa`, `access_status`, `snippet`, `venue`, `citations`, `quality_tier`.
  3. `chat_messages`: `id`, `chat_id`, `role`, `content`, `attachments_json`, `variants_json` (multi-response switching), `active_variant_index`, `created_at`.
  4. `citation_highlights`: `id`, `chat_id`, `doc_id`, `claim_hash` (SHA256 normalized claim), `claim`, `passages_json` (verbatim quote array), `created_at`.
  5. `research_profiles`: `id`, `chat_id`, `category` (constraint, objective, methodology, hardware, venue), `fact_text`, `is_active`, timestamps.
- **Auto-Migration:** `auto_migrate_schema()` in `backend/database.py` automatically detects and adds missing columns during server startup without data loss.

### 3.2 Vector Database (`Qdrant`)
- **Implementation:** Singleton client in `backend/rag/vector_store.py`.
- **Operating Modes:**
  - **Embedded Disk (Default):** Persists vector points in `backend/qdrant_data/` with thread-safe locks.
  - **Remote Server:** Configured via `QDRANT_URL` and `QDRANT_API_KEY` (Docker or Qdrant Cloud cluster).
- **Collections:**
  - `not_notebooklm_fastembed`: Default 384-dimensional dense collection generated via FastEmbed ONNX (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) + sparse BM25.
  - `not_notebooklm_e5`: Legacy 384-dimensional dense collection (isolated to prevent vector space collisions).
  - `not_notebooklm_gemini_3072`: Dedicated 3072-dimensional collection for active Google GenAI embeddings (`models/gemini-embedding-001`).
  - `not_notebooklm_gemini`: Legacy 768-dimensional collection for older cloud models.
- **Payload Indexing:** Filtered via metadata keys: `chat_id`, `filename`, and `canonical_section`.

### 3.3 File System & Object Storage Adapter (`storage_adapter.py`)
- Supports two storage backends configured via `STORAGE_TYPE`:
  - `STORAGE_TYPE=local`: Source PDFs and attachments stored under `backend/uploads/` and `backend/uploads/chat_media/`.
  - `STORAGE_TYPE=s3`: Uses `boto3` with `s3v4` signatures compatible with:
    - **Cloudflare R2:** Zero egress fees, low global latency.
    - **MinIO:** Self-hosted S3 for local homelabs and isolated networks.
    - **AWS S3:** Enterprise cloud standard.
- **Dual-Tier Document Cache:**
  1. Memory Cache: `OrderedDict` bounded LRU (200 markdown items).
  2. Persistent Disk Cache: `.parsed_cache/{sha256_hash}.parsed.md` for instant (<5ms) reads without re-parsing large documents.

---

## 4. LLM Factory & Cascading Architecture

The system enforces **Tiered Model Routing** via `backend/rag/llm_factory.py` to balance throughput, latency, and rate-limit resilience:

```
                      [Incoming Processing Request]
                                    |
                    +---------------+---------------+
                    |                               |
                    v (Synthesis / Heavy Turn)      v (Micro-Task / Helper)
           [Primary Heavy LLM]             [Fast / Lite LLM]
           - Max Output: 16k tokens        - Max Output: 4k tokens
           - Timeout: 120 seconds          - Timeout: 45 seconds
           - Temp: 0.2 (RAG) / 0.0 (Eval)  - Temp: 0.1 (JSON parse)
                    |                               |
                    +---------------+---------------+
                                    |
                          (Network / 5xx / 429)
                                    v
                          [Fallback Cascading LLM]
                          - Automatic retry failover
```

### 4.1 Fast LLM Responsibilities
The Fast LLM is strictly decoupled for low-latency auxiliary micro-tasks:
1. **Semantic Intent Classification:** Classifies user query into 4 execution categories (`backend/rag/intent.py`).
2. **Academic Query Planner:** Extracts entities, year boundaries, target quantities, language codes, and Scopus quartile filters (`backend/services/search/query_planner.py`).
3. **Paper Relevance Judge & Screening:** Evaluates candidate abstracts to eliminate false-positives (`backend/services/search/paper_judge.py`).
4. **Early-Draft Conversation Title:** Generates a 3-5 word concise topic title within 1.5 seconds (`backend/services/search/title_generator.py`).
5. **Interactive Highlight Evidence Locator:** Matches synthesized claims against verbatim document sentences (`backend/services/highlight_service.py`).
6. **Research Memory Extraction & Reconciliation:** Discovers new research constraints and supersedes contradictory rules (`backend/services/memory_service.py`).

---

## 5. End-to-End Orchestration Pipelines

### 5.1 Ingestion & Section-Aware Academic Chunker (`academic_chunker.py`)
```
[Raw Document: PDF / DOCX / Markdown / Text]
  │
  ├── PyMuPDF4LLM / python-docx / markdown extractor
  │   └── Clean Markdown Text (preserves tables, LaTeX, and headings)
  │
  ├── Hierarchical Breadcrumb Tracking (Heading Stack H1 -> H2 -> H3)
  │
  ├── 9 Canonical IMRaD Centroids (Regex + Cosine Embedding Anchor):
  │   Abstract, Introduction, Literature Review, Methodology, 
  │   Results, Discussion, Conclusion, Limitations, References
  │
  ├── Embeddings: FastEmbed ONNX Multilingual MiniLM (384 dim) + FastEmbed BM25
  │
  └── Persistence: Upsert to Qdrant (Hybrid vectors + metadata payload)
```

### 5.2 Literature Discovery & PDF Racing Resolver (`search.py`)
```
[User Query: "find recent papers on quantum error mitigation"]
  │
  ├── Query Planner (Extracts clean queries: en_query, id_query, native_query)
  │
  ├── Concurrent Multi-Engine Search:
  │   ├── OpenAlex API (Authoritative open-access catalog)
  │   ├── Crossref API (Global DOI registry)
  │   ├── Europe PMC API (Biomedical & life sciences literature)
  │   └── DuckDuckGo Academic Crawler (Preprints, niche topics, fallback)
  │
  ├── Metadata Auditor & Ranking (Scopus Q1-Q4, SINTA, Citation Velocity)
  │
  ├── Paper Relevance Judge (Fast LLM screens abstracts against research intent)
  │   └── Eliminates out-of-scope papers and predatory spam
  │
  └── Parallel PDF Racing Resolver:
      ├── Race resolvers concurrently: arXiv, Unpaywall, OpenAlex, Europe PMC
      ├── In-Memory PDF Authenticity Check (Verifies title & DOI in first 2 pages)
      └── First valid PDF winner saved to uploads/ while cancelling slower tasks
```

### 5.3 Context-Density Adaptive Workspace Retrieval (`workspace_pipeline.py`)

NotbookLM dynamically adjusts retrieval strategy based on workspace document density:

```
                                  [User RAG Query]
                                          |
                                          v
                      [Inspect Workspace Documents & Density]
                                          |
                  +-----------------------+-----------------------+
                  |                                               |
                  v (Workspace <= 4 Documents)                    v (Workspace > 4 Documents)
      +---------------------------------------+       +---------------------------------------+
      |        DIRECT CONTEXT PACKING         |       |      HYBRID RETRIEVAL & RERANKING     |
      | - Token Budget Inspector              |       | - Build Structured Document Catalog   |
      | - Pack all full-text documents        |       | - Hybrid Qdrant Retrieval (Top-25:    |
      |   directly into prompt headroom       |       |   FastEmbed Dense MiniLM + FastEmbed  |
      | - Maximum fidelity & zero recall loss |       |   BM25 via RRF)                       |
      |                                       |       | - FlashRank Cross-Encoder Rerank      |
      |                                       |       |   (Top-12 most relevant excerpts)     |
      |                                       |       | - Solves Stanford 'Lost in Middle'    |
      +-------------------+-------------------+       +-------------------+-------------------+
                          |                                               |
                          +-----------------------+-----------------------+
                                                  |
                                                  v
                              [Inject Active Research Profile Memory]
                              (Constraints, Hardware, Objectives: <= 250 tokens)
                                                  |
                                                  v
                              [Grounded System Prompt with Full Guardrails]
                                                  |
                                                  v
                              [LLM Synthesis & Citation Map Emission]
```

### 5.4 Two-Tier Verbatim Citation & Reader Highlighting Engine

To enforce scientific rigor and prevent hallucination, the system implements two-tier citation verification:

1. **LLM Output Format:** Citations embedded in generated prose use numerical bracket tags `[^n]` or `[n]` referencing catalog document numbers.
2. **Structured Metadata `<!-- CITATION_MAP -->`:** At the end of every answer, the system emits a machine-readable JSON mapping:
   - `claim`: Synthesized scientific proposition.
   - `doc_id`: Target document ID.
   - `passages`: Exact verbatim quote strings copied directly from source papers.
3. **Database Caching (`citation_highlights`):** Claims are hashed via SHA256 (`claim_hash`) and stored in SQLite for instant 0ms reader lookups.
4. **Interactive Jump-to-Highlight Navigation:**
   - Clicking a citation badge in chat opens the split-pane reader automatically.
   - The reader executes exact verbatim and fuzzy n-gram matching, smoothly scrolling directly to the page and sentence with yellow highlighted text.

### 5.5 Declarative Fact Memory System (`memory_service.py`)

Unlike generic summary buffers that lose granular constraints, NotbookLM maintains **Declarative Research Memory**:
- **5 Canonical Categories:**
  - `constraint`: Negative bounds and strict exclusions (e.g., "Do not use PyTorch").
  - `objective`: Primary research question or hypothesis.
  - `methodology`: Preferred algorithmic architectures or paradigms.
  - `hardware`: Compute constraints (e.g., "16GB Mac, CPU-only").
  - `venue`: Target journal or conference constraints.
- **Reconciliation Lifecycle:**
  1. At every conversation turn, Fast LLM inspects user and assistant messages.
  2. Fast LLM extracts new facts (`inserted`) and detects superseded/invalidated facts (`invalidated`).
  3. Status updates are committed transactionally to `research_profiles`.
  4. Active facts are injected into subsequent System Prompts with a strict 250-token budget.

---

## 6. Evaluation Frameworks & Quality Guardrails

Under `backend/evaluation/`, the repository maintains a multi-framework quantitative evaluation harness:

```
backend/evaluation/
├── datasets/
│   ├── full100_benchmark.json          # 100-Case Held-Out Test Set
│   ├── val25_benchmark.json            # 25-Case Held-Out Validation Suite
│   ├── niah_100_matrix.json            # 100-Case Conversational Memory Matrix
│   └── qasper_papers/                  # Raw academic research papers
├── metrics/
│   ├── standard_evaluator.py           # DeepEval, TruLens, Promptfoo, LlamaIndex
│   ├── ragas_adapter.py                # Multi-statement Atomic NLI Faithfulness
│   └── citation_verifier.py            # Deterministic PDF Substring & Princeton ALCE
├── run_benchmark.py                    # Main RAG benchmark CLI runner
└── eval_full50_niah.py                 # Conversational Memory & Needle CLI runner
```

### Production Quality Thresholds
- **Consensus Groundedness:** `>= 0.850` (DeepEval + TruLens + Promptfoo + Ragas continuous mean)
- **Answer Relevancy:** `>= 0.850`
- **Princeton ALCE Citation Recall & Precision:** `>= 0.850`
- **Deterministic Citation Fidelity (Verbatim PDF Match):** `>= 90.0%`
- **Negative Abstention Honesty:** `1.000` (Strictly declines answering when evidence is absent)
- **Separation of Scale Rule:** Binary 0/1 gatekeepers (LlamaIndex) remain completely isolated from continuous 0.000–1.000 consensus scorecards.

---

## 7. Environment & Configuration Reference

Example configuration for local and cloud environments:

```ini
# Primary Synthesis LLM (Heavy model for grounded responses)
LLM_MODEL=ag/gemini-3.8-flash-high
LLM_BASE_URL=http://localhost:20128/v1
LLM_API_KEY=your_primary_api_key

# Fast Helper LLM (Micro-tasks, intent triage, query planning)
LLM_FAST_MODEL=ag/gemini-3.7-flash-low
LLM_FAST_BASE_URL=http://localhost:20128/v1
LLM_FAST_API_KEY=your_fast_api_key

# Fallback Failover LLM
LLM_FALLBACK_MODEL=ag/gemini-3.7-flash-low
LLM_FALLBACK_BASE_URL=http://localhost:20128/v1
LLM_FALLBACK_API_KEY=your_fallback_api_key

# Embedding Provider (local or gemini)
EMBEDDING_PROVIDER=local
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001

# Vector Database (Leave empty for embedded disk storage in backend/qdrant_data/)
QDRANT_URL=
QDRANT_API_KEY=

# Storage Provider (local or s3)
STORAGE_TYPE=local
S3_BUCKET_NAME=
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
```

---

## 8. Key Module File Directory

For rapid navigation during maintenance and development:
- **FastAPI Application & Endpoints:** `backend/main.py`
- **Vector Database & Embeddings:** `backend/rag/vector_store.py`
- **RAG Engine & Coordinator:** `backend/rag/engine.py`
- **Workspace Retrieval Pipeline:** `backend/rag/pipelines/workspace_pipeline.py`
- **Intent Classifier:** `backend/rag/intent.py`
- **Literature Search & Multi-Engine:** `backend/rag/search.py`
- **PDF Racing Resolvers:** `backend/services/search/pdf_resolver.py`
- **Academic Chunker:** `backend/rag/academic_chunker.py`
- **Document Parsers & Cache:** `backend/rag/parsers.py`
- **Citation Verifier:** `backend/evaluation/metrics/citation_verifier.py`
- **Research Profile Memory:** `backend/services/memory_service.py`
- **Token Budgeting:** `backend/rag/token_budget.py`
- **Next.js Main Chat Interface:** `frontend/src/app/ChatClient.tsx`
- **Document Split Reader:** `frontend/src/components/DocumentReader.tsx`
- **Left Sidebar & Chat Sessions:** `frontend/src/components/LeftSidebar.tsx`
