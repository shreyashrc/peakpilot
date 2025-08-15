## 🏔️ PeakPilot: Hiking Assistant (FastMCP + RAG + Gemini)

Agentic web crawler that answers hiking/trekking questions for Indian trails using FastAPI, FastMCP-style skills, Gemini (2.5 Pro), and a RAG pipeline over ChromaDB.

### Features
- FastAPI backend with WebSocket streaming
- FastMCP-style skill orchestration (search → crawl → weather → stats → RAG → answer)
- Gemini for embeddings and completions
- ChromaDB for vector search
- Simple frontend (HTML/JS) using WebSocket
- Docker Compose for app + ChromaDB
 - Intent-aware web crawling with Indiahikes and curated web sources; AllTrails/OSM deep-links

### Quickstart (Local)
1. Create and configure environment:
   - Copy `.env.example` to `.env` and fill `GEMINI_API_KEY` (optional for offline dev)
2. Install dependencies:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
3. Run the app:
   - `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`
4. Open the UI:
   - Visit `http://localhost:8000/` and ask a question

### Quickstart (Docker Compose - Production)
1. Copy `.env.example` to `.env` and set variables
2. Build and start:
   - `docker compose up --build -d`
3. Open `http://localhost:8000/`
4. Data persistence:
   - Vector store persists at `./chroma_db` (bind-mounted)

### Render Deployment

The project is deployed using Render
Visit: `https://peakpilot.onrender.com/`

### Project Structure
```
api/          # FastAPI app, routes, WebSocket
mcp/          # Skills and orchestrator (search, crawl, weather, stats, answer)
crawler/      # Indiahikes crawler, web meta-search (DDG + trafilatura), weather
llm/          # Gemini wrapper and client
rag/          # ChromaDB client + RAG skill
frontend/     # Minimal HTML/JS UI (Tailwind via CDN)
tests/        # Unit & smoke tests
docker/       # Dockerfile and compose
scripts/      # Pre-indexing script
```

### Environment Variables
See `.env.example` for required keys.

### Notes
- The implementation includes safe fallbacks when external APIs are not configured, enabling local development without keys. For meaningful answers, set `GEMINI_API_KEY`.
- The RAG layer uses a persistent local ChromaDB (`./chroma_db`) via compose and falls back to an in-process client if unreachable.
- Source routing:
  - `SOURCE_ORDER` (default: `indiahikes,web`)
- Links: We provide OSM and AllTrails deep-links; users can choose routes and GPX as needed.
