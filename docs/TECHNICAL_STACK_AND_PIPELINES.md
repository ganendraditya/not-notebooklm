# Not-NotebookLM — Technical Stack, Architecture & Pipeline Specification

Dokumen spesifikasi teknis komprehensif untuk sistem **Not-NotebookLM**: platform AI Workspace & Research Assistant berbasis RAG (Retrieval-Augmented Generation) ilmiah. Dokumen ini mendokumentasikan seluruh arsitektur sistem, komponen tech stack, alur kerja orkestrasi (ingestion, discovery, retrieval, synthesis), tugas Fast LLM, mekanisme storage/database, hingga guardrails evaluasi.

---

## 1. High-Level Architecture Overview

Not-NotebookLM dibangun dengan arsitektur decoupled (Client-Server terpisah, headless Vector Database, dan pluggable Hybrid Object Storage):

```
+-----------------------------------------------------------------------------------------+
|                                FRONTEND (Next.js 16 + React 19)                         |
|  - Split-Pane Reader (PDF / Markdown / KaTeX Math)                                      |
|  - Interactive Verbatim Citation Jump-to-Highlight                                      |
|  - Real-time SSE Token Streamer (smoothStreamer.ts)                                     |
|  - 33-Language i18n Localization Engine                                                 |
+--------------------------------------------+--------------------------------------------+
                                             | HTTP REST / Server-Sent Events (SSE)
                                             v
+-----------------------------------------------------------------------------------------+
|                                  BACKEND (FastAPI + Python 3.11+)                       |
|  Routers: /chats, /messages, /documents, /papers, /settings, /storage                   |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                             LLM Gateway & Cascading Factory                       |  |
|  |  - Primary / Heavy LLM (LLM_MODEL, 16k context, 120s timeout)                      |  |
|  |  - Fast / Lite LLM (LLM_FAST_MODEL, 4k context, 45s timeout)                       |  |
|  |  - Fallback LLM (LLM_FALLBACK_MODEL, automatic failover)                          |  |
|  +-----------------------------------------------------------------------------------+  |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                            Core Orchestration Pipelines                           |  |
|  |  1. Semantic Intent Classifier (4-Class triage + micro-dialogue context)           |  |
|  |  2. Document Ingestion & Section Chunker (9 Academic Canonical Centroids)          |  |
|  |  3. Multi-Engine Literature Discovery (OpenAlex, Crossref, Europe PMC, DDG)       |  |
|  |  4. Parallel PDF Racing Resolver (arXiv, Unpaywall, OpenAlex, Scrapers)            |  |
|  |  5. Dual-Mode RAG Engine (Direct Context Packing vs Dense + Cross-Encoder Rerank)  |  |
|  |  6. Declarative Research Profile Memory (Constraints, Hardware, Objectives)       |  |
|  |  7. Verbatim Citation Highlighter & Evidence Verifier (Princeton ALCE compliance)  |  |
|  +-----------------------------------------------------------------------------------+  |
+-------------------+--------------------+--------------------+-----------------------+
                    |                    |                    |
                    v                    v                    v
         +--------------------+ +------------------+ +------------------+
         |    SQLITE (WAL)    | |   QDRANT VDB     | |  OBJECT STORAGE  |
         |  Relational DB     | | Dense Vectors    | | Local Uploads /  |
         |  Metadata, Chats,  | | E5 Multilingual/ | | S3 / MinIO /     |
         |  Citations, Memory | | Google Gemini    | | Cloudflare R2    |
         +--------------------+ +------------------+ +------------------+
```

---

## 2. Complete Technology Stack Matrix

| Lapisan / Domain | Teknologi / Framework | Versi / Detail Spesifik | Fungsi & Alasan Pemilihan |
| :--- | :--- | :--- | :--- |
| **Backend Runtime** | Python | `>= 3.11` | Runtime ekosistem AI/ML modern, kompatibilitas typing, async/await native. |
| **Backend Web API** | FastAPI | `0.141.1` | Asynchronous REST server, validation otomatis via Pydantic v2, streaming SSE native. |
| **ASGI Server** | Uvicorn | `0.52.4` | Production-grade lightweight ASGI web server. |
| **Frontend Framework**| Next.js | `16.3.1` (App Router) | Server-side rendering, bundle splitting, React Server Components. |
| **UI Library** | React | `19.2.8` | Client-side reactive rendering, hooks modern. |
| **Styling & Design** | Tailwind CSS | `v4` (`@tailwindcss/postcss`) | Atomic CSS layout modern, tokenisasi desain kustom, zero-runtime bloat. |
| **State Management** | Zustand | `5.0.15` | State management client-side ringan, non-boilerplate untuk dokumen, status chat, dan UI. |
| **Scientific Math** | KaTeX + Remark/Rehype | `katex 0.18`, `remark-math 6`, `rehype-katex 7` | Render formula matematika dan rumus ilmiah LaTeX di reader dan chat. |
| **Markdown Engine** | react-markdown | `10.1.0` + `remark-gfm` | Rendering GitHub Flavored Markdown, tabel, checklist, dan blockquote. |
| **RAG Orchestrator** | LlamaIndex Core | `>= 0.11.0` | Abstraksi document, vector store index, retriever node, dynamic chat messages. |
| **LLM Gateway Client**| `llama-index-llms-openai-like` | `>= 0.2.0` | Menghubungkan ke gateway OpenAI-compatible (9Router, LiteLLM, Ollama, OpenRouter). |
| **Vector Database** | Qdrant Client | `>= 1.12.0` | Vector database berkecepatan tinggi, kompatibel remote server atau embedded disk persistence. |
| **Embedding Model** | Multilingual E5 Small | `intfloat/multilingual-e5-small` (384 dim) | Default local offline embeddings (93+ bahasa), zero external API cost. |
| **Alternative Embedding** | Google GenAI | `models/text-embedding-004` (768 dim) | High-accuracy Google cloud embedding via `llama-index-embeddings-google-genai`. |
| **Cross-Encoder Reranker** | FlashRank | `0.2.10` (`ms-marco-TinyBERT-L-2-v2`) | Cross-encoder ultra-cepat (<10ms) berbasis ONNX/in-memory singleton tanpa dependency GPU berat. |
| **Relational Database** | SQLite (WAL Mode) | SQLite3 via SQLAlchemy `2.0.52` | Penyimpanan persisten metadata dokumen, sesi chat, pesan, citations, dan memory profile. |
| **Object Storage Adapter**| Boto3 S3 Client | `>= 1.34.0` | Adapter terpadu untuk Cloudflare R2, MinIO self-hosted, atau AWS S3 dengan fallback disk. |
| **PDF Extraction Engine**| PyMuPDF4LLM | `1.28.2` | Multi-column reading order aware academic parser, mempertahankan tabel & format teks ilmiah. |
| **DOCX Extraction** | python-docx | `1.2.0` | Parser dokumen Microsoft Word DOCX menjadi clean structured text. |
| **Search Engines** | DuckDuckGo Search | `>= 7.0.0` | Fallback web crawler jika DOI/Open Access registry eksternal tidak menemukan paper. |
| **Token Budgeting** | Tiktoken | `>= 0.7.0` | Token counting presisi per model keluarga OpenAI/compatible untuk alokasi dynamic context. |
| **Code Hygiene** | Ruff | `>= 0.8.0` | Linter & formatter berkecepatan tinggi untuk standar kode Python. |
| **Testing Harness** | Pytest + Vitest | `pytest 9.1`, `vitest 4.1` | Testing terisolasi backend (asyncio) dan frontend UI components. |

---

## 3. Storage & Database Architecture

Sistem menggunakan pendekatan **Tri-Layer Storage** yang menjamin persistensi, performa kueri, dan portabilitas cloud:

```
+------------------------------------------------------------------------------------+
|                               STORAGE & PERSISTENCE                                |
+----------------------------+-----------------------------+-------------------------+
| 1. SQLite Relational DB    | 2. Qdrant Vector DB         | 3. File & Media Storage |
|    (backend/not_notebooklm.db)|    (backend/qdrant_data/)   |    (Local / S3 / R2)    |
| - ChatSessions             | - not_notebooklm_e5         | - Original PDF / DOCX   |
| - Documents (metadata)     | - not_notebooklm_gemini     | - Chat Media / Images   |
| - ChatMessages (variants)  | - Dense Vector Embeddings   | - .parsed_cache/ (MD)   |
| - CitationHighlights       | - Metadata filters:         | - temp_zips/ (Export)   |
| - ResearchProfiles (Memory)|   chat_id, filename, section|                         |
+----------------------------+-----------------------------+-------------------------+
```

### 3.1 Relational Database (`SQLite` via SQLAlchemy 2.0)
- **Path:** `backend/not_notebooklm.db` (dapat diarahkan ke PostgreSQL melalui env `DATABASE_URL`).
- **Mode Konkurensi:** SQLite dijalankan dengan `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, dan `PRAGMA busy_timeout=30000;` (timeout lock 30 detik untuk write concurrency) serta `PRAGMA foreign_keys=ON;`.
- **Tabel Utama:**
  1. `chat_sessions`: `id` (UUID), `title`, `is_pinned`, `created_at`, `updated_at`.
  2. `documents`: `id`, `chat_id`, `filename`, `title`, `authors` (JSON), `year`, `journal`, `journal_metric`, `doi`, `url`, `pdf_url`, `abstract`, `abstract_type`, `is_oa`, `access_status`, `snippet`, `venue`, `citations`, `quality_tier`.
  3. `chat_messages`: `id`, `chat_id`, `role`, `content`, `attachments_json`, `variants_json` (multi-response switching), `active_variant_index`, `created_at`.
  4. `citation_highlights`: `id`, `chat_id`, `doc_id`, `claim_hash` (SHA256 normalized claim), `claim`, `passages_json` (array verbatim quote), `created_at`.
  5. `research_profiles`: `id`, `chat_id`, `category` (constraint, objective, methodology, hardware, venue), `fact_text`, `is_active`, timestamps.
- **Auto-Migration:** Mekanisme `auto_migrate_schema()` di `backend/database.py` memeriksa dan menambahkan kolom yang hilang secara otomatis saat server booting tanpa merusak data lama.

### 3.2 Vector Database (`Qdrant`)
- **Implementasi:** Singleton client di `backend/rag/vector_store.py`.
- **Mode Operasi:**
  - **Embedded Disk (Default):** Menyimpan point vectors di `backend/qdrant_data/` dengan multi-thread safe lock.
  - **Remote Server:** Menggunakan `QDRANT_URL` dan `QDRANT_API_KEY` (Docker atau Qdrant Cloud cluster).
- **Collections:**
  - `not_notebooklm_e5`: Khusus vektor 384 dimensi dari model `multilingual-e5-small`.
  - `not_notebooklm_gemini`: Khusus vektor 768 dimensi dari model Google GenAI.
- **Payload Indexing:** Disaring menggunakan metadata filter `chat_id`, `filename`, dan `canonical_section`.

### 3.3 File System & Object Storage Adapter (`storage_adapter.py`)
- Mendukung dua mode penyimpanan melalui environment variable `STORAGE_TYPE`:
  - `STORAGE_TYPE=local`: File PDF dan attachment disimpan di `backend/uploads/` dan `backend/uploads/chat_media/`.
  - `STORAGE_TYPE=s3`: Menggunakan library `boto3` dengan signature `s3v4` yang kompatibel dengan:
    - **Cloudflare R2:** Egress gratis, latensi rendah global.
    - **MinIO:** Self-hosted S3 untuk homelab atau server lokal terisolasi.
    - **AWS S3:** Standar enterprise cloud.
- **Dual-Tier Cache Dokumen:**
  1. Memory Cache: `OrderedDict` bounded LRU (200 item markdown).
  2. Persistent Disk Cache: `.parsed_cache/{sha256_hash}.parsed.md` untuk pembacaan instan (<5ms) tanpa re-parsing dokumen berukuran besar.

---

## 4. Multi-Tier LLM Gateway & Factory

Sistem menerapkan prinsip **Tiered Model Routing** via `backend/rag/llm_factory.py` untuk mengoptimalkan efisiensi, latensi, dan ketahanan terhadap rate-limit:

```
                      +---------------------------------------+
                      |         LLM Gateway Request           |
                      +-------------------+-------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
        v                                                                   v
+-----------------------------------+             +-----------------------------------+
|     PRIMARY / HEAVY LLM           |             |       FAST / LITE LLM             |
|  Env: LLM_MODEL (e.g. gpt-4o)     |             |  Env: LLM_FAST_MODEL              |
|  - Max Tokens: 16,384             |             |  - Max Tokens: 4,096              |
|  - Timeout: 120s                  |             |  - Timeout: 45s                   |
|  - Tasks:                         |             |  - Tasks:                         |
|    * Multi-document synthesis     |             |    * Semantic intent triage       |
|    * Comparative reviews          |             |    * Query planning & translation |
|    * Grounded RAG analysis        |             |    * Paper relevance screening    |
|    * Deep academic Q&A            |             |    * Dynamic title generation     |
+-----------------------------------+             |    * Verbatim citation extraction |
                                                  |    * Memory fact extraction       |
                                                  +-----------------+-----------------+
                                                                    | On Error / 429
                                                                    v
                                                  +-----------------------------------+
                                                  |       FALLBACK LLM CASCADE        |
                                                  |  Env: LLM_FALLBACK_MODEL          |
                                                  |  - Automatic fallback handler     |
                                                  |  - Seamless error recovery        |
                                                  +-----------------------------------+
```

### 4.1 Registri Micro-Tasks Fast LLM (`acall_fast_with_fallback`)
Fast LLM diisolasi untuk tugas-tugas mikro berkecepatan tinggi agar alur inferensi utama tidak terbebani latensi:
1. **Semantic Intent Classification:** Mengklasifikasikan prompt ke 4 intent dalam <1 detik (`backend/rag/intent.py`).
2. **Academic Query Planner:** Mengekstrak entity, batasan tahun, target kuantitas, bahasa, dan kuartil Scopus (`backend/services/search/query_planner.py`).
3. **Paper Relevance Judge & Screening:** Menilai abstrak paper dari search engine untuk mengeliminasi false-positive (`backend/services/search/paper_judge.py`).
4. **Rubric Grader:** Memberikan evaluasi metodologi paper terhadap rubrik riset (`backend/services/rubric_grader_service.py`).
5. **Interactive Highlight Evidence Locator:** Mencocokkan klaim sitasi dengan kalimat verbatim dalam dokumen (`backend/services/highlight_service.py`).
6. **Research Memory Extraction & Reconciliation:** Menemukan constraint riset baru serta menganulir aturan yang kontradiktif (`backend/services/memory_service.py`).
7. **Dynamic Title Generation:** Membuat judul obrolan profesional (2–5 kata) berdasarkan percakapan turn pertama (`backend/rag/engine.py`).

---

## 5. End-to-End Orchestration Pipelines

### 5.1 Document Ingestion & Section Chunker Pipeline

```
[Uploaded File (PDF, DOCX, BIB, RIS, TXT)]
                  |
                  v
[Format Router & Parser (backend/rag/parsers.py)]
  ├── PDF: PyMuPDF4LLM (multi-column reading order aware, use_layout=False)
  ├── DOCX: python-docx paragraph/table extractor
  ├── BIB/RIS: Multi-entry splitter (individual entries with auto-enrichment)
  └── Persistent Disk Cache (.parsed_cache/)
                  |
                  v
[Academic Chunker (backend/rag/academic_chunker.py)]
  ├── Regex Header Matcher (Multi-lingual academic terms)
  ├── Semantic Centroid Classifier (Cosine similarity to 9 canonical anchors:
  │   Abstract, Intro, Lit Review, Methods, Results, Discussion, Conclusion, Limitations, Refs)
  └── Hierarchical Breadcrumb Builder ("Methodology > 3.2 Dataset Splitting")
                  |
                  v
[Batch Vector Store Ingestion (backend/rag/vector_store.py)]
  ├── Embeddings: intfloat/multilingual-e5-small or Gemini text-embedding-004
  └── Qdrant Points Ingest (payload: chat_id, filename, section, breadcrumb, canonical_section)
```

### 5.2 Academic Literature Search & Discovery Pipeline

```
[User Search Query (e.g. "Cari 10 paper Scopus Q1 tentang transformer vision 2022-2024")]
                  |
                  v
[Stage 1: LLM Query Planner (backend/services/search/query_planner.py)]
  ├── Multilingual Intent Normalizer (Bahasa Indonesia / English native translation)
  ├── Constraints Extractor (target_count: max 25, year range, open access flag)
  └── Academic Criteria Parser (Scopus Q1-Q4, SINTA S1-S6, min citations)
                  |
                  v
[Stage 2 & 3: Multi-Provider Concurrent Search (backend/providers/academic/)]
  ├── Europe PMC API (Biomedical, life sciences, open access fulltext)
  ├── OpenAlex API (Global multi-disciplinary scholarly registry, citation metrics)
  ├── Crossref API (Official DOI registration agency metadata)
  └── DuckDuckGo Academic Fallback (Web crawl fallback if registries yield zero)
                  |
                  v
[Stage 4: Deduplication Engine (backend/rag/search.py)]
  ├── Exact DOI Normalization & Matching
  └── Fuzzy Title Jaccard Overlap (>= 75% token overlap similarity filter)
                  |
                  v
[Stage 5: Fast LLM Paper Judge & Rubric Qualification (backend/services/search/)]
  ├── Evaluasi abstrak terhadap relevansi kueri & metodologi ilmiah
  └── Eliminasi paper out-of-scope dan non-peer-reviewed spam
                  |
                  v
[Stage 6: Parallel Multi-Threaded PDF Racing Resolver (backend/providers/academic/pdf_racing_resolver.py)]
  ├── Worker 1: arXiv standard resolver (arxiv.org/pdf/{id}.pdf)
  ├── Worker 2: Unpaywall REST API (best_oa_location)
  ├── Worker 3: OpenAlex direct PDF landing
  ├── Worker 4: Europe PMC PDF endpoint
  └── Verification: is_authentic_pdf_bytes (%PDF- magic bytes check)
```

### 5.3 Dual-Mode RAG Synthesis & Retrieval Engine

Not-NotebookLM menerapkan strategi pengambilan kontekstual adaptif berdasarkan kepadatan dokumen di workspace (`backend/rag/pipelines/workspace_pipeline.py`):

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
      | - Pack all full-text documents        |       | - Qdrant Vector Retrieval (Top-25)    |
      |   directly into prompt headroom       |       | - FlashRank Cross-Encoder Rerank      |
      | - Maximum fidelity & zero recall loss |       |   (Top-12 most relevant excerpts)     |
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
                              [Grounded System Prompt with Anti-Sycophancy]
                              (Empirical rules, verbatim quote citation contracts)
                                                  |
                                                  v
                              [Stream Assistant Response (SSE)]
                              (Delivering text chunks + Citation Map + Sources Action)
```

---

## 6. Citation Grounding & Interactive Verification

Untuk mematuhi kaidah ilmiah yang ketat dan mencegah halusinasi LLM, sistem menerapkan sistem sitasi dua lapis:

1. **Format Output LLM:** Sitasi disematkan dalam teks menggunakan tag numerik `[^n]` atau `[n]` yang merujuk pada nomor dokumen dalam katalog.
2. **Metadata Payload `<!-- CITATION_MAP -->`:** Pada akhir jawaban, sistem memancarkan mapping terstruktur yang berisi:
   - `claim`: Klaim atau temuan ilmiah yang disintesis.
   - `doc_id`: ID dokumen sumber.
   - `passages`: Kutipan teks verbatim karakter-demi-karakter dari dokumen sumber.
3. **Database Caching (`citation_highlights`):** Klaim di-hash menggunakan SHA256 (`claim_hash`) dan disimpan di SQLite agar permintaan jump-to-highlight berikutnya berlangsung 0ms.
4. **Interactive Jump-to-Highlight di Frontend:**
   - Pengguna mengklik badge sitasi di chat bubble.
   - Reader panel di sisi kanan terbuka secara otomatis.
   - Sistem melakukan pencarian teks exact match / fuzzy substring dan melompat (*smooth scroll*) langsung ke halaman dan kalimat yang relevan dengan warna highlight kuning.

---

## 7. Declarative Conversational Memory (`ResearchProfile`)

Berbeda dengan sistem memory berbasis ringkasan umum (*summary buffer*) yang sering kali kehilangan instruksi penting, Not-NotebookLM menggunakan **Declarative Fact Memory**:

- **Kategori Fakta:**
  - `constraint`: Batasan riset (misal: "Hanya gunakan dataset berbahasa Indonesia", "Tahun publikasi harus di atas 2021").
  - `objective`: Sasaran utama penelitian pengguna.
  - `methodology`: Pilihan arsitektur atau algoritma yang diinginkan.
  - `hardware`: Batasan komputasi pengguna (misal: "GPU hanya RTX 3060 12GB").
  - `venue`: Target publikasi (misal: "Target konferensi IEEE / jurnal Scopus Q1").
- **Alur Kerja Asinkron:**
  1. Setiap pergantian pesan (*turn*), Fast LLM membaca pesan pengguna dan asisten.
  2. Fast LLM mengekstrak fakta baru (`inserted`) dan mendeteksi apakah ada fakta lama yang dibatalkan/diubah oleh pengguna (`invalidated`).
  3. Status fakta diupdate secara transaksional di tabel `research_profiles`.
  4. Fakta aktif dimasukkan ke dalam System Prompt generasi berikutnya dengan batas token ketat (maksimal 250 token) agar tidak membebani context window RAG.

---

## 8. Automated Evaluation & Benchmarking Harness

Di bawah direktori `backend/evaluation/`, repositori dilengkapi dengan harness pengujian kuantitatif multi-framework:

```
backend/evaluation/
├── datasets/
│   ├── full100_benchmark.json     # 100-Case Comprehensive Scientific Test Suite
│   ├── val25_benchmark.json       # 25-Case Held-Out Validation Suite
│   ├── niah_100_matrix.json       # 100-Case Conversational Memory (Needle-in-a-Haystack)
│   ├── niah_val25_matrix.json     # 25-Case Held-Out Memory Validation
│   ├── loader_qasper.py           # AllenAI QASPER multi-paper dataset loader
│   └── loader_scifact.py          # SciFact scientific claim verification loader
├── metrics/
│   ├── unified_framework_evaluator.py  # Multi-framework consensus aggregator
│   ├── standard_evaluator.py           # DeepEval, TruLens, Promptfoo, Ragas
│   ├── citation_verifier.py            # Deterministic PDF Substring & Princeton ALCE
│   └── alce_adapter.py                 # ALCE Citation Recall & Precision
├── run_benchmark.py               # Main CLI runner untuk evaluasi RAG
└── eval_full50_niah.py            # CLI runner untuk Memory & Needle retrieval
```

### Standar Kualitas Produksi:
- **Consensus Groundedness:** `>= 0.850` (DeepEval + TruLens + Promptfoo + Ragas)
- **Consensus Answer Relevancy:** `>= 0.850`
- **ALCE Citation Recall & Precision:** `>= 0.850`
- **Deterministic Citation Fidelity (Verbatim PDF Match):** `>= 90.0%`
- **Negative Abstention Honesty:** `1.000` (Menolak menjawab secara tegas jika dokumen tidak memuat data yang ditanyakan, anti-halusinasi)
- **Separation of Scale Rule:** Metrik biner 0/1 (seperti gatekeeper LlamaIndex) dipisahkan secara tegas dari continuous mean score 0.000–1.000.

---

## 9. Key Configuration Variables (`.env`)

```ini
# LLM Gateway
LLM_BASE_URL=http://localhost:20128/v1   # OpenAI-compatible API endpoint
LLM_API_KEY=your_api_key_here            # API key / bearer token
LLM_MODEL=gpt-4o                         # Primary / Heavy reasoning model
LLM_FAST_MODEL=gpt-4o-mini               # Fast model for micro-tasks
LLM_FALLBACK_MODEL=gpt-4o-mini           # Cascade fallback model
LLM_TEMPERATURE=0.1                      # Low temperature for factual precision

# Vector Database (Kosongkan untuk disk storage otomatis di backend/qdrant_data/)
QDRANT_URL=
QDRANT_API_KEY=

# Storage Mode (local | s3)
STORAGE_TYPE=local

# S3 Configuration (Wajib hanya jika STORAGE_TYPE=s3)
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=not-notebooklm
S3_REGION=auto

# Security & CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

---

## 10. File & Module Map Reference

Untuk navigasi cepat saat modifikasi dan pemeliharaan:

- **Entrypoint:** `backend/main.py`
- **Database Models & Engine:** `backend/database.py`, `backend/models.py`
- **LLM Factory & Gateway:** `backend/rag/llm_factory.py`
- **RAG Engine & Coordinator:** `backend/rag/engine.py`
- **Pipelines:**
  - Workspace Analysis: `backend/rag/pipelines/workspace_pipeline.py`
  - Search Pipeline: `backend/rag/pipelines/search_pipeline.py`
  - Chat Pipeline: `backend/rag/pipelines/chat_pipeline.py`
  - Source Actions: `backend/rag/pipelines/source_action_pipeline.py`
- **Vector Store & Embeddings:** `backend/rag/vector_store.py`
- **Document Chunking & Parsing:** `backend/rag/academic_chunker.py`, `backend/rag/parsers.py`, `backend/rag/format_parsers.py`
- **Search Services & Providers:** `backend/services/search/`, `backend/providers/academic/`
- **PDF Racing Resolver:** `backend/providers/academic/pdf_racing_resolver.py`
- **Citation Highlights:** `backend/services/highlight_service.py`
- **Research Memory:** `backend/services/memory_service.py`
- **Storage & Object Sync:** `backend/services/storage_service.py`, `backend/services/storage_adapter.py`
- **Frontend App & Reader:** `frontend/src/app/`, `frontend/src/components/RightSidebar/DocumentReader/`
- **Frontend Streaming Client:** `frontend/src/lib/smoothStreamer.ts`, `frontend/src/lib/sse.ts`
