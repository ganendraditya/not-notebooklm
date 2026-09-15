# NotbookLM

An open-source academic research assistant and document workspace designed to run locally on your own machine. Inspired by tools like Google Notebook / Gemini Notebook (previously NotebookLM), Consensus, and Elicit—NotbookLM bridges conversational AI with verifiable academic literature synthesis.

![NotbookLM Workspace](docs/assets/workspace-preview.png)

Instead of relying on proprietary cloud lock-in, NotbookLM operates locally by default—combining embedded relational storage (SQLite), in-process vector indexing (Qdrant), and local file processing. It streamlines retrieval, filtering, and synthesis of scholarly publications from global academic repositories—including **OpenAlex**, **Crossref**, and **Europe PMC**, with **DuckDuckGo** scholarly web search fallback, and full-text PDF resolution via **arXiv** and **Unpaywall**—delivering structured comparative matrices and grounded citations linked directly to source papers.

Internet connectivity is required out-of-the-box for live academic discovery, PDF resolution, and external LLM APIs. If you need a fully offline or private setup for self-uploaded documents, you can manually configure your own local inference stack—such as pointing `LLM_BASE_URL` to a local runner (e.g., Ollama, vLLM) and caching embedding weights locally.

### Highlights

* **Deterministic Workspace Citation Indexing:** Every document retains a fixed, immutable citation number (`1.`, `2.`, `3.`) across all turns of the conversation based on a deterministic ID-ascending contract. When a document is removed, the system cleanly rearranges remaining indices without numeric fragmentation.
* **Automated Literature Discovery & Web Fallback:** Queries global academic registries (**OpenAlex**, **Crossref**, and **Europe PMC**) with automatic **DuckDuckGo** web search fallback when academic registries yield sparse results, iterative candidate pool retrieval, language-aware filtering, and DOI/title deduplication.
* **Full-Text PDF & Metadata Resolution:** Locates and downloads open-access PDFs via concurrent racing resolvers (**arXiv**, **Unpaywall**, **OpenAlex**, **Europe PMC**) with in-memory title verification, while enriching paper records with journal quartiles and citation counts.
* **Multi-Format Ingestion & Bibliography Splitting:** Ingests PDF, DOCX, TXT, and Markdown files. Multi-entry BibTeX (`.bib`) and RIS (`.ris`) collections are automatically disassembled on upload into standalone workspace documents with optimistic loading spinners and real-time open-access PDF resolution.
* **Asynchronous Auto-Grounding & SQLite Persistence:** Citation grounding runs asynchronously after generation via Fast LLM and is persisted in SQLite (`citation_highlights`). A 4-tier matching engine (exact verbatim, n-gram intersection, fallback span, and multi-bullet context cursor) accurately highlights supporting passages in the document reader.
* **Cell-Level Citation Matrices & Markdown Export:** Synthesizes literature into structured comparative review matrices with verifiable citations embedded directly in individual table cells, accompanied by 1-click Markdown table copy and native KaTeX math equation rendering.
* **Interactive Split-Pane Reader & Jump-to-Highlight:** Bidirectional citation navigation—clicking any citation badge in a response or table cell automatically opens the document reader, scrolls to the page, and highlights the exact supporting passage.
* **Targeted Document Focus:** One-click "Ask about this document" mode focuses questions exclusively on an individual paper without deselecting other workspace files.
* **7-Format Citation Generator & Bulk ZIP Export:** Instant generation of verified academic citations in APA 7th, IEEE, Harvard, MLA 9th, Chicago, BibTeX, and RIS formats, alongside one-click bulk ZIP bundling for entire workspaces.
* **3-Tier Hybrid Metadata Extractor:** Handles user-uploaded documents (PDF, Word, Markdown, Text) via DOI auto-resolution, Crossref title matching, and an AI Document Inspector tailored for theses, dissertations, and institutional reports without fabricating false citations.
* **Local-First & Multi-Role LLM Architecture:** Runs locally with embedded SQLite and Qdrant. Connects to any OpenAI-compatible API (Ollama, vLLM, DeepSeek, GPT-4o) with tiered primary, fast, and auto-fallback model roles, plus optional S3 storage (Cloudflare R2, MinIO).

---

## Workflow & Core Capabilities

### 1. Literature Discovery & Granular Ingestion
Search across OpenAlex, Crossref, Europe PMC, with intelligent **DuckDuckGo** scholarly web search fallback for niche topics and recent preprints. NotbookLM screens candidate publications and presents actionable cards containing titles, publication years, DOI links, and abstract previews. Users can select candidates with tri-state selection controls, batch-import with live progress tracking (`Adding x/y...`), and cancel individual downloads granularly from the sidebar without leaving orphan files.

![Literature Discovery](docs/assets/literature-discovery.png)

### 2. Deterministic Source Management & Multi-Format Ingestion
Imported and uploaded sources appear in the right-hand **Sources** panel with permanent numeric citation indices (`1.`, `2.`, ...):
* **Format Badges & Document Status:** Visual tags reflect source state—`PDF` (red) indicates an authentic manuscript PDF acquired via open-access resolvers, while `TXT` (gray) represents structured publication briefs with abstracts for paywalled references or uploaded text notes. Additional tags identify uploaded document formats like `DOC` (Word) and `MD` (Markdown).
* **Automated Bibliography Disassembly:** Uploading multi-entry `.bib` or `.ris` files automatically splits each reference into an individual workspace entry. Client-side title extraction creates instant optimistic loading cards with spinners while concurrent background racing attempts to resolve full open-access PDFs via DOI before falling back to structured publication briefs.
* **Deterministic Indices & Auto-Reindex:** A source's citation number remains consistent throughout the entire conversation. Deleting a source automatically compacts and shifts remaining document indices cleanly.
* **Verified Paper vs. Local Manuscript:** Authentic journal publications retain official publisher metadata, while local documents (such as theses, student projects, or CVs) are cleanly cataloged without artificial journal labels.
* **Bulk ZIP Export:** Download original documents individually or bundle multiple selected sources into a single organized ZIP package.

### 3. Integrated Document Reader & Targeted Focus
Inspect full manuscripts directly within the workspace:
* **Dual-View Inspection:** Stream authentic publication PDFs directly in the browser or switch to extracted full-text for citation navigation.
* **Ask About This Document:** Focus queries exclusively on a single source with one click, bypassing manual workspace deselection.
* **Multi-Format Citation Generator:** Export clean, verified academic citations across APA 7th, IEEE, Harvard, MLA 9th, Chicago, BibTeX, and RIS.

### 4. Grounded Synthesis & Bidirectional Citation Highlighting
Synthesize multiple papers into comparative review matrices. Each finding is tagged with traceable citation badges (`[1]`, `[2]`). Clicking any citation opens the document reader and automatically scrolls to highlight the exact supporting sentence in the source text:
* **Cell-Level Evidence:** Citations are anchored to specific table cells for verifiable metric-by-metric comparison.
* **4-Tier Highlight Matching:** Resolves citations using exact verbatim quotes, n-gram token intersection, character span fallback, and context cursors designed specifically for multi-bullet comparison tables.
* **Asynchronous Grounding & Persistence:** Fast LLM grounding runs asynchronously in the background and caches results directly in SQLite (`citation_highlights`), ensuring instant jump-to-highlight on return visits.
* **1-Click Markdown Copy:** Copy sanitized Markdown tables directly into Notion, Obsidian, Typora, or Word.
* **KaTeX Mathematics:** Seamlessly renders mathematical notation, formulas, and matrices ($E = mc^2$, $\sum$, $\int$).

![Grounded Citation Highlighting](docs/assets/citation-grounding.png)

---

## Quickstart

You can run this project in two ways:

### Option 1: Quickstart via Docker
Runs all services in containers without requiring local Python or Node.js installations.

1. **Clone repository:**
   ```bash
   git clone https://github.com/ganendraditya/not-notebooklm.git
   cd not-notebooklm
   ```

2. **Setup environment variables:**
   ```bash
   cp backend/.env.example backend/.env
   ```
   *Configure your API key and model preferences in `backend/.env`.*

3. **Start services with Docker Compose:**
   ```bash
   docker compose up -d
   ```

4. **Access the application:**
   * **Frontend Web App:** `http://localhost:3000`
   * **Backend API Docs:** `http://localhost:8000/docs`
   * **Qdrant Dashboard:** `http://localhost:6333/dashboard`

---

### Option 2: Local Development (Bare-Metal)
For active development directly on your machine.

> **Bare-Metal Default Stack:**
> By default in bare-metal mode, NotbookLM operates on an embedded local stack:
> * **Relational Database:** SQLite (`backend/not_notebooklm.db`)
> * **Object Storage:** Local file system (`uploads/` and `uploads/chat_media/`)
> * **Vector Engine:** Embedded in-process Qdrant (`backend/qdrant_data/`)
>
> This default enables immediate local setup without running external services.
>
> **Production and Multi-User Setup:**
> For server deployments or multi-user environments:
> 1. **S3 Object Storage:** Set `STORAGE_TYPE=s3` in `backend/.env` to connect to Cloudflare R2 or MinIO. This ensures uploaded research papers and chat attachments persist across server restarts.
> 2. **Dedicated Vector Server:** Run a standalone Qdrant container (`docker run -d -p 6333:6333 qdrant/qdrant`) and configure `QDRANT_URL=http://localhost:6333` in `backend/.env` for independent indexing and lower backend memory usage.
> 3. **Docker Compose:** Alternatively, running `docker compose up -d` (Option 1) manages these services automatically.

#### 1. Initial Setup (Dependencies & Configuration)

**Backend:**
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit backend/.env with your LLM configuration
cd ..
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

#### 2. Start Servers

##### Recommended: One-Click Startup Script
Launch both backend and frontend servers simultaneously with a single command from the project root:

- **Linux / macOS:**
  ```bash
  ./start.sh
  ```
- **Windows (PowerShell):**
  ```powershell
  .\start.ps1
  ```

Both startup scripts include an integrated **Port Guard** that automatically detects and safely terminates orphaned processes on ports 8000 and 3000, preventing `Address already in use` launch errors.

##### Alternative: Manual Startup (Separate Terminals)
If you prefer running services in separate terminal windows for dedicated logs:
- **Backend:** `cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000` (or `.\venv\Scripts\activate` on Windows)
- **Frontend:** `cd frontend && npm run dev`

Open `http://localhost:3000` in your browser.

##### Pre-Flight Verification Script
Mirror the automated GitHub Actions CI pipeline locally before committing or creating pull requests:
```bash
./check.sh
```
Runs frontend linting, unit tests (`vitest`), Next.js production build, backend syntax compilation, and the full pytest suite. Flags: `--frontend` (`-f`) or `--backend` (`-b`) to run targeted checks.

---

## LLM Configuration

NotbookLM integrates with any OpenAI-compatible endpoint or gateway. Providers and models can be changed via environment variables without modifying application code.

### Core Variables (`backend/.env`)

```env
# 1. Endpoint & Authentication
LLM_BASE_URL=http://localhost:20128/v1
LLM_API_KEY=your_api_key_here

# 2. Model Roles
LLM_MODEL=gpt-4o
LLM_FAST_MODEL=gpt-4o-mini
LLM_FALLBACK_MODEL=gpt-4o-mini
```

### Model Roles

| Variable | Role | Necessity | Description |
| :--- | :--- | :--- | :--- |
| **`LLM_MODEL`** | Primary Model | **Required** | Handles complex tasks: multi-document synthesis, literature comparisons, grounded verbatim citations, and workspace analysis. |
| **`LLM_FAST_MODEL`** | Fast Model | *Optional* | Handles quick micro-tasks: query planning, user intent triage, paper relevance screening, and title generation.<br> *If omitted, the system defaults to `LLM_MODEL`.* |
| **`LLM_FALLBACK_MODEL`** | Fallback Model | *Optional* | Engages automatically if the primary model encounters rate limits (HTTP 429), timeouts, or service unavailability. |

---

## Storage Configuration (Local Disk & S3 Object Storage)

Files can be stored directly on the local disk or synced to an S3-compatible Object Storage provider (such as Cloudflare R2, MinIO, or AWS S3).

### Configuration (`backend/.env`)

#### Option 1: Local Disk Storage (Default)
```env
STORAGE_TYPE=local
```
Files are stored directly in `uploads/` and `uploads/chat_media/`.

#### Option 2: S3-Compatible Storage (Cloudflare R2, MinIO, AWS S3)
```env
STORAGE_TYPE=s3
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com  # or http://localhost:9000 for MinIO
S3_ACCESS_KEY_ID=your_access_key_id
S3_SECRET_ACCESS_KEY=your_secret_access_key
S3_BUCKET_NAME=not-notebooklm
S3_REGION=auto  # or us-east-1
```

---

## Secret Management

Populate your credentials into `backend/.env`:
```bash
cp backend/.env.example backend/.env
```
The application reads configuration through standard environment variables. If you prefer managing credentials without plaintext `.env` files, `./start.sh` (Linux/macOS) and `.\start.ps1` (Windows) feature automatic CLI detection and parity for both [Doppler](https://www.doppler.com) and [Infisical](https://infisical.com) (auto-detects active vault sessions or supports explicit wrappers like `doppler run -- ./start.sh` or `infisical run -- ./start.sh`).

---

## Architecture & Tech Stack

* **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS, Zustand State Management, Base UI.
* **Backend:** FastAPI, SQLAlchemy (SQLite with WAL mode for chat sessions & citation persistence), LlamaIndex.
* **Literature Discovery:** Multi-engine scholarly search via **OpenAlex**, **Crossref**, **Europe PMC**, and **DuckDuckGo** web search fallback.
* **PDF Resolvers:** Concurrent racing resolvers across **arXiv**, **Unpaywall**, **OpenAlex**, and **Europe PMC** with in-memory title verification.
* **Storage:** Unified Storage Adapter supporting Local Disk and S3-compatible Object Storage (Cloudflare R2, MinIO, AWS S3).
* **Vector Store:** Qdrant (supports remote Docker instance or embedded local disk fallback).
* **Embeddings:** Local multilingual embeddings (`intfloat/multilingual-e5-small`) or Google Gemini embeddings.
* **LLM Engine:** OpenAI-compatible adapter (`OpenAILike`) with tiered model roles (Primary, Fast, Fallback) and automated error recovery.

---

## License

This project is licensed under the [MIT License](LICENSE).
