# NotbookLM

A customizable AI research and document workspace inspired by Google Notebook (formerly NotebookLM), Consensus AI, and Elicit. Built with FastAPI, Next.js, LlamaIndex, and Qdrant vector database.

---

## Quickstart

You can run this project in two ways:

### Option 1: Quickstart via Docker
No need to install Python, Node.js, or local database dependencies.

1. **Clone repository:**
   ```bash
   git clone https://github.com/ganendraditya/not-notebooklm.git
   cd not-notebooklm
   ```

2. **Setup environment variables:**
   ```bash
   cp backend/.env.example backend/.env
   ```
   *Open `backend/.env` and insert your API key and model configuration (see [LLM Configuration](#-llm-configuration) below).*

3. **Start all services with Docker Compose:**
   ```bash
   docker compose up -d
   ```

4. **Open in browser:**
   * **Frontend Web App:** [http://localhost:3000](http://localhost:3000)
   * **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   * **Qdrant Vector Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

### Option 2: Local Development (Bare-Metal)
For active development without running Docker.

> **💡 Understanding the Bare-Metal Default Stack:**
> By default in bare-metal mode, NotbookLM operates on an **embedded, zero-setup local stack**:
> * **Relational DB:** SQLite (`backend/not_notebooklm.db`)
> * **Object Storage:** Local file system (`uploads/` and `uploads/chat_media/`)
> * **Vector Engine:** Embedded in-process Qdrant (`backend/qdrant_data/`)
>
> *Why this default?* It allows instant development on any machine without installing Docker or external database servers.
>
> **⚡ Upgrading to the Optimal / Production Stack:**
> If you plan to deploy to a server or want optimal multi-user performance and cloud persistence:
> 1. **S3 Object Storage:** Switch `STORAGE_TYPE=s3` in `backend/.env` and connect to **Cloudflare R2** (recommended, 10GB free cloud storage with zero egress fees) or **MinIO**. This ensures research PDFs and in-chat attachments persist permanently across server redeployments without disk bloat.
> 2. **Dedicated Vector Server:** Start a standalone Qdrant container (`docker run -d -p 6333:6333 qdrant/qdrant`) and configure `QDRANT_URL=http://localhost:6333` in `backend/.env` for faster HNSW vector indexing and lower Python process memory consumption.
> 3. **Or run via Docker Compose (Option 1):** Orchestrates all optimal services automatically out of the box.

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
# Edit .env with your API credentials (see section below)

uvicorn main:app --reload --port 8000
```

#### 2. Frontend Setup (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## LLM Configuration

NotbookLM is **100% vendor-neutral**. You never need to touch Python code or factory files to switch providers or models. Everything is controlled entirely through your `backend/.env` file using the standard OpenAI-compatible protocol.

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

### Understanding the Model Roles

| Variable | Role | Necessity | Description |
| :--- | :--- | :--- | :--- |
| **`LLM_MODEL`** | Primary / Heavy Model | **Required** | Handles complex, reasoning-heavy tasks: multi-document synthesis, literature reviews, grounded verbatim citations, and workspace analysis. |
| **`LLM_FAST_MODEL`** | Fast / Lite Model | *Optional* | Handles rapid micro-tasks: query planning, user intent triage, paper relevance screening, and smart title generation.<br> *If omitted or left empty, the system automatically uses `LLM_MODEL`.* |
| **`LLM_FALLBACK_MODEL`** | Safety Fallback Model | *Optional* | Automatically kicks in if the primary model hits rate limits (HTTP 429), timeouts, or provider downtime. |

---

## Storage Configuration (Local Disk & S3 Object Storage)

NotbookLM supports a **hybrid decoupled storage architecture**. You can run purely on local disk (zero setup, 100% offline) or seamlessly sync with any S3-compatible Object Storage (**Cloudflare R2**, **MinIO**, or **AWS S3**) so your research PDFs and media attachments persist across cloud deployments and server restarts.

### Configuration (`backend/.env`)

#### Option 1: Local Disk Storage (Default - Zero Setup)
```env
STORAGE_TYPE=local
```
*Files are stored directly in `uploads/` and `uploads/chat_media/` on your machine. Best for personal laptops and offline research.*

#### Option 2: Cloudflare R2 (Recommended Cloud Provider - 10GB Free, $0 Egress)
```env
STORAGE_TYPE=s3
S3_ENDPOINT_URL=https://<your_account_id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=your_r2_access_key_id
S3_SECRET_ACCESS_KEY=your_r2_secret_access_key
S3_BUCKET_NAME=not-notebooklm
S3_REGION=auto
```
*How to obtain credentials:*
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → **R2 Object Storage** → **Create bucket** (e.g. `not-notebooklm`, standard storage class).
2. Go to **Manage R2 API Tokens** → **Create API token** with **Object Read & Write** permissions.
3. Copy your Account ID endpoint URL, Access Key ID, and Secret Access Key.

#### Option 3: MinIO (Self-Hosted S3 for Homelabs / Intranets)
```env
STORAGE_TYPE=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=not-notebooklm
S3_REGION=us-east-1
```
*Run MinIO locally via Docker:*
```bash
docker run -d -p 9000:9000 -p 9001:9001 minio/minio server /data --console-address ":9001"
```

---

## Secret Management (Environment Variables & Zero-Disk-Secrets)

NotbookLM supports three flexible tiers of secret management, scaling from effortless local development to enterprise security compliance:

| Tier | Provider | Best For | Storage on Disk | Command |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Default)** | Conventional `.env` | Solo development, offline, zero-setup | Stored in `backend/.env` (git-ignored) | `./start.sh` |
| **Tier 2 (Cloud)** | **Doppler** | Teams, startups, cloud deployments | **Zero** secrets stored on disk (injected directly to RAM) | `doppler run -- ./start.sh` |
| **Tier 3 (Self-Hosted)** | **Infisical** | Air-gapped homelabs & strict compliance | **Zero** secrets stored on disk (self-hosted vault) | `infisical run -- ./start.sh` |

### Using Doppler (Zero Secrets on Disk)
1. **Install Doppler CLI:**
   ```bash
   brew install dopplerhq/cli/doppler
   doppler login
   ```
2. **Link the repository:**
   ```bash
   doppler setup
   ```
   *(Select project `not-notebooklm` and config `dev`)*.
3. **Upload your secrets (one-time):**
   ```bash
   doppler secrets upload backend/.env
   ```
4. **Run NotbookLM:**
   ```bash
   doppler run -- ./start.sh
   ```
   *Note: `./start.sh` is intelligent: if `backend/.env` is absent, it will automatically fallback to Doppler secret injection if configured.*

---

## Architecture & Tech Stack

* **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS, Zustand State Management, Base UI.
* **Backend:** FastAPI, SQLAlchemy (SQLite), LlamaIndex.
* **Storage:** Unified Storage Adapter supporting Local Disk, Cloudflare R2, MinIO, and AWS S3.
* **Vector Store:** Qdrant (supports remote Docker instance or embedded local disk fallback).
* **Embeddings:** Local offline multilingual embeddings (`intfloat/multilingual-e5-small`) with automatic local caching, or Google Gemini embeddings.
* **LLM Engine:** Vendor-neutral OpenAI-compatible adapter (`OpenAILike`) with dynamic multi-tier routing and cascading fallback.

---

## License

This project is licensed under the [MIT License](LICENSE).
