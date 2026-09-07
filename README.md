# NotbookLM

A customizable AI research and document workspace inspired by Google Notebook (formerly NotebookLM), Consensus AI, and Elicit. Built with FastAPI, Next.js, LlamaIndex, and Qdrant vector database.

---

## Quickstart

You can run this project in two ways:

### Option 1: Quickstart via Docker (Recommended for Users)
No need to install Python, Node.js, or local dependencies.

1. **Clone repository:**
   ```bash
   git clone https://github.com/ganendraditya/not-notebooklm.git
   cd not-notebooklm
   ```

2. **Setup environment variables:**
   ```bash
   cp backend/.env.example backend/.env
   ```
   *Edit `backend/.env` with your preferred AI provider API key and model gateway endpoint (e.g., 9Router, OpenAI-compatible proxy, or direct API keys).*

3. **Start all services with Docker Compose:**
   ```bash
   docker compose up -d
   ```

4. Open in browser:
   * **Frontend Web App:** [http://localhost:3000](http://localhost:3000)
   * **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   * **Qdrant Vector Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

### Option 2: Local Development (Bare-Metal)
For active development without running Docker.

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
# Edit .env with your API credentials

uvicorn main:app --reload --port 8000
```

#### 2. Frontend Setup (Next.js)
```bash
cd frontend
npm install
npm run dev
```

---

## Architecture & Tech Stack

* **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS, Zustand State Management.
* **Backend:** FastAPI, SQLAlchemy (SQLite), LlamaIndex.
* **Vector Store:** Qdrant (supports remote Docker instance or embedded local disk fallback).
* **AI Architecture:** Two-Tier LLM Gateway (Primary Heavy Synthesizer for deep multi-document literature reasoning & Fast Lite Worker for rapid intent triage, query planning, and academic paper auditing). Any OpenAI-compatible endpoint or model gateway can be configured.
