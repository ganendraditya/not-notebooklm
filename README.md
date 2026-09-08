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

### Quick Setup Presets

Copy and paste the template that matches your preferred AI provider:

#### Preset A: 9Router or Local AI Gateway (Default)
```env
LLM_BASE_URL=http://localhost:20128/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=ag/gemini-3.7-flash-high
LLM_FAST_MODEL=ag/gemini-3.8-flash-low
LLM_FALLBACK_MODEL=ag/gemini-pro-agent
```

#### Preset B: Local Offline via Ollama (No API Key Required)
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.3:70b
LLM_FAST_MODEL=llama3.2:3b
```

#### Preset C: OpenRouter (Claude, DeepSeek, Llama)
```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=anthropic/claude-3.5-sonnet
LLM_FAST_MODEL=anthropic/claude-3.5-haiku
LLM_FALLBACK_MODEL=deepseek/deepseek-chat
```

#### Preset D: Official OpenAI
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o
LLM_FAST_MODEL=gpt-4o-mini
LLM_FALLBACK_MODEL=gpt-4o-mini
```

#### Preset E: Single-Model Mode (Super Simple)
If you only have or want to use **one model**, you only need to specify `LLM_MODEL`. The system will automatically use it for both heavy reasoning and fast triage tasks:
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o
```

---

## Architecture & Tech Stack

* **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS, Zustand State Management, Base UI.
* **Backend:** FastAPI, SQLAlchemy (SQLite), LlamaIndex.
* **Vector Store:** Qdrant (supports remote Docker instance or embedded local disk fallback).
* **Embeddings:** Local offline multilingual embeddings (`intfloat/multilingual-e5-small`) with automatic local caching, or Google Gemini embeddings.
* **LLM Engine:** Vendor-neutral OpenAI-compatible adapter (`OpenAILike`) with dynamic multi-tier routing and cascading fallback.

---

## License

This project is licensed under the [MIT License](LICENSE).
