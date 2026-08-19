# Not-NotebookLM

An open-source, customizable AI research and document workspace inspired by NotebookLM. Powered by FastAPI, Next.js, LlamaIndex, and Qdrant vector database.

---

## 🚀 Quickstart

You can run this project in two ways:

### Option 1: Quickstart via Docker (Recommended for Users)
No need to install Python, Node.js, or local dependencies.

1. **Clone repository:**
   ```bash
   git clone https://github.com/your-username/not-notebooklm.git
   cd not-notebooklm
   ```

2. **Setup environment variables:**
   ```bash
   cp backend/.env.example backend/.env
   ```
   *Edit `backend/.env` and add your LLM API keys (e.g., Gemini, Groq, or FreeLLMAPI).*

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
# Edit .env with your API keys

uvicorn main:app --reload --port 8000
```

#### 2. Frontend Setup (Next.js)
```bash
cd frontend
npm install
npm run dev
```

---

## ⚙️ Architecture & Tech Stack

* **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS.
* **Backend:** FastAPI, SQLAlchemy (SQLite), LlamaIndex.
* **Vector Store:** Qdrant (supports remote Docker instance or embedded local disk fallback).
* **LLM Providers:** Google Gemini, Groq, FreeLLMAPI, 9Router.
