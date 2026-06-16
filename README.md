markdown# ⚡ Multi-Agent Dev Assistant

An autonomous AI system that takes a GitHub issue → retrieves relevant codebase context → generates a code fix → reviews it → and opens a Pull Request automatically.

Built with LangGraph, LangChain, Groq (Llama 3.1), ChromaDB, FastAPI, and Next.js.

## Demo

> Issue opened: "Add Pinterest as a supported platform"
> 
> 34 seconds later: PR opened automatically with the correct code change.

**Live PRs opened by the agent:** [github.com/VT-2004/social-dash/pulls](https://github.com/VT-2004/social-dash/pulls)

## Results

- Agents resolved **6/8 in-scope issues (75%)** automatically
- Average time-to-PR: **34 seconds**
- Severity classifier correctly skipped **2/2 out-of-scope issues** in under 3 seconds
- Zero crashes across 10-issue batch test

## Architecture
GitHub Issue → Severity Classifier (attempt/skip?)

↓

Context Agent (RAG on codebase via ChromaDB)

↓

Code Agent (Groq Llama 3.1 — generates targeted edits)

↓

Review Agent (checks for bugs/security issues)

↓ (retry loop if review fails, max 2 retries)

GitHub PR via REST API

↓

Next.js Dashboard (live agent reasoning log via WebSocket)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent orchestration | LangGraph (StateGraph with conditional edges) |
| LLM | Groq — Llama 3.1 8B Instant |
| RAG / Vector store | ChromaDB + sentence-transformers (all-MiniLM-L6-v2) |
| Backend | FastAPI + async background tasks + WebSockets |
| GitHub integration | PyGithub (PR creation, branch management) |
| Frontend | Next.js 15 + TypeScript + Tailwind CSS |

## How It Works

1. **Severity Classifier** — reads the issue title/body and decides whether to attempt or skip (skips vague/large-scope issues immediately)
2. **Context Agent** — uses RAG to retrieve the most relevant code chunks from the target repo
3. **Code Agent** — sends the issue + retrieved context to Groq Llama 3.1, which generates a targeted JSON edit (search/replace format)
4. **Review Agent** — reviews the diff for bugs, security issues, and whether it actually addresses the issue
5. **Retry Loop** — if review fails, routes back to Code Agent with feedback (max 2 retries)
6. **PR Creation** — creates a branch, commits the change, opens a PR with the full agent reasoning log

## Project Structure
multi-agent-dev-assistant/

├── backend/

│   ├── app/

│   │   ├── agents/          # LangGraph nodes (severity, context, code, review)

│   │   ├── core/            # Config, state schema, job store, pipeline runner

│   │   ├── rag/             # Chunker, embeddings, ChromaDB vectorstore, retriever

│   │   ├── github_integration/  # PR creation, webhook handler

│   │   ├── websocket/       # WebSocket connection manager

│   │   ├── api/             # FastAPI routes

│   │   └── main.py          # FastAPI app entry point

│   ├── data/

│   │   ├── chroma_db/       # Vector store (gitignored)

│   │   └── repos/           # Cloned target repos (gitignored)

│   ├── requirements.txt

│   └── .env.example

├── frontend/

│   ├── app/                 # Next.js App Router

│   ├── lib/                 # API client + types

│   └── package.json

├── docker-compose.yml

└── README.md

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API key (free at [console.groq.com](https://console.groq.com))
- GitHub Personal Access Token (repo scope)

### 1. Clone the repo

```bash
git clone https://github.com/VT-2004/multi-agent-dev-assistant.git
cd multi-agent-dev-assistant
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Fill in your GROQ_API_KEY and GITHUB_TOKEN in .env
```

### 3. Index your target repo

```bash
python -m app.rag.ingest https://github.com/<owner>/<repo>.git <repo-name>
python -m app.rag.vectorstore ./data/repos/<repo-name> <repo-name>
```

### 4. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Frontend setup

```bash
cd ../frontend
npm install
npm run dev
```

### 6. Open the dashboard

Visit `http://localhost:3000` — fill in the trigger form with an issue from your target repo and click **▶ Run Pipeline**.

## Docker (Self-Hosted)

```bash
cp backend/.env.example backend/.env
# Fill in your keys in backend/.env
docker-compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for Llama 3.1 |
| `GITHUB_TOKEN` | GitHub PAT with repo scope |
| `GITHUB_WEBHOOK_SECRET` | Secret for webhook verification |
| `TARGET_REPO_OWNER` | Default repo owner |
| `TARGET_REPO_NAME` | Default repo name |
| `CHROMA_DB_PATH` | Path for ChromaDB persistence |
| `REPO_CLONE_PATH` | Path for cloned repos |

## Extending to Other Repos

Index any GitHub repo in two commands:

```bash
python -m app.rag.ingest https://github.com/<owner>/<repo>.git <repo-name>
python -m app.rag.vectorstore ./data/repos/<repo-name> <repo-name>
```

Then use `<repo-name>` as the repo name in the dashboard trigger form.

## Resume Metrics

- **75% autonomous resolution rate** on well-scoped issues
- **34 second average time-to-PR** on resolved issues  
- **RAG retrieval** over 500+ code chunks with sub-2s latency
- **Multi-agent coordination** using LangGraph StateGraph with conditional edges and retry loops

## License

MIT