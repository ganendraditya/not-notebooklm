# NotbookLM

An open-source academic research assistant and document workspace designed to run locally on your own machine. Inspired by tools like Google Notebook (previously NotebookLM), Consensus, and Elicit, NotbookLM bridges conversational AI with verifiable academic literature synthesis.

![NotbookLM Workspace](docs/assets/workspace-preview.png)

Instead of relying on proprietary cloud lock-in, NotbookLM operates locally by default—combining embedded relational storage (SQLite), in-process vector indexing (Qdrant), and local file processing. It streamlines retrieval, filtering, and synthesis of scholarly publications from global academic repositories—including **OpenAlex**, **Crossref**, **arXiv**, **Unpaywall**, and web fallbacks—delivering structured comparative matrices and grounded citations linked directly to source papers.

Internet connectivity is required out-of-the-box for live academic discovery, PDF resolution, and external LLM APIs. If you need a fully offline or private setup for self-uploaded documents, you can manually configure your own local inference stack—such as pointing `LLM_BASE_URL` to a local runner (e.g., Ollama, vLLM) and caching embedding weights locally.

### Highlights

* **Automated Literature Discovery:** Queries global academic registries (OpenAlex, Crossref, and web fallbacks) with iterative candidate pool retrieval, language-aware filtering, and DOI/title deduplication.
* **Full-Text PDF & Metadata Resolution:** Locates and downloads open-access PDFs via concurrent resolvers (arXiv, Unpaywall, OpenAlex) while enriching paper records with journal quartiles and citation counts.
* **Grounded Synthesis & Matrix Tables:** Produces comparative literature review matrices with cell-level citation tagging, mitigating hallucinations by grounding claims directly in retrieved excerpts.
* **Interactive Document Reader:** Split-pane interface featuring bidirectional citation navigation—click any citation badge to jump to and highlight the exact passage in the source PDF or document.
* **Local-First Architecture:** Runs on your local machine with zero mandatory cloud accounts. Supports bring-your-own local models (e.g., Ollama) or any OpenAI-compatible API endpoint, with optional S3 storage (Cloudflare R2, MinIO).

---

## Workflow & Core Capabilities

### 1. Literature Discovery & Paper Retrieval
Search across OpenAlex, Crossref, and academic sources. NotbookLM filters candidates based on relevance screening and presents actionable cards containing titles, publication years, DOI links, and abstract previews. Users can select and batch-import papers directly into the workspace.

![Literature Discovery](docs/assets/literature-discovery.png)

### 2. Intelligent Source Management (PDF vs. Metadata)
Imported papers appear in the right-hand **Sources** panel with permanent numeric citation indices (`1.`, `2.`, ...):
* **`PDF` badge:** The open-access full-text PDF was successfully located and downloaded via concurrent resolvers (arXiv, Unpaywall, OpenAlex).
* **`TXT` badge:** Full-text PDF was behind paywalls or unavailable; NotbookLM indexed verified metadata and abstracts to maintain comprehensive coverage.

### 3. Integrated Document & PDF Viewer
Inspect full manuscripts directly within the workspace. The built-in document reader provides a dual-view experience: stream and read the authentic publication PDF, or switch to the extracted full-text view for citation navigation and quick reading.

### 4. Grounded Synthesis & Bidirectional Citation Highlighting
Synthesize multiple papers into comparative review matrices. Each finding is tagged with traceable citation badges (`[6]`, `[7]`, `[8]`). Clicking any citation opens the document reader and automatically scrolls to highlight the exact supporting sentence in the source text.

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

#### 1. Backend Setup (FastAPI)
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit backend/.env with your configuration

uvicorn main:app --reload --port 8000
```

#### 2. Frontend Setup (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

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
The application reads configuration through standard environment variables. If you prefer managing credentials without plaintext `.env` files, `./start.sh` also supports injecting secrets via external secret managers such as [Doppler](https://www.doppler.com) (`doppler run -- ./start.sh`) or [Infisical](https://infisical.com).

---

## Architecture & Tech Stack

* **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS, Zustand State Management, Base UI.
* **Backend:** FastAPI, SQLAlchemy (SQLite), LlamaIndex.
* **Storage:** Unified Storage Adapter supporting Local Disk and S3-compatible Object Storage (Cloudflare R2, MinIO, AWS S3).
* **Vector Store:** Qdrant (supports remote Docker instance or embedded local disk fallback).
* **Embeddings:** Local multilingual embeddings (`intfloat/multilingual-e5-small`) or Google Gemini embeddings.
* **LLM Engine:** OpenAI-compatible adapter (`OpenAILike`) with tiered model roles and automatic error fallback.

---

## License

This project is licensed under the [MIT License](LICENSE).
