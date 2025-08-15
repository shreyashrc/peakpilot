import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
import hashlib
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from mcp.orchestrator import run_pipeline

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("peakpilot.api")

app = FastAPI(title="PeakPilot: Hiking Assistant with FastMCP & RAG")

# CORS for local frontend
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


# Simple TTL cache for answers
class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    def _now(self) -> float:
        return asyncio.get_event_loop().time()

    def get(self, key: str) -> Any:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry["expires_at"] < self._now():
            self._store.pop(key, None)
            return None
        return entry["value"]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = {"value": value, "expires_at": self._now() + self.ttl_seconds}


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_key(question: str) -> str:
    normalized = (question or "").strip().lower()
    schema_ver = os.getenv("CACHE_SCHEMA_VERSION", "1")
    to_hash = f"v{schema_ver}|{normalized}"
    return hashlib.sha256(to_hash.encode("utf-8")).hexdigest()


_CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "5"))
_WS_TIMEOUT_SECONDS = int(os.getenv("WS_TIMEOUT_SECONDS", "30"))
answer_cache = TTLCache(ttl_seconds=_CACHE_TTL_MINUTES * 60)


@app.get("/health")
def health() -> Any:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> Any:
    return {"status": "ok"}


@app.get("/")
def index() -> Any:
    base_dir = Path(__file__).resolve().parent.parent
    frontend_dir = base_dir / "frontend"
    index_file = frontend_dir / "index.html"
    if not index_file.exists():
        return JSONResponse({"message": "Frontend not found"}, status_code=404)
    return FileResponse(str(index_file))


base_dir = Path(__file__).resolve().parent.parent
frontend_dir = base_dir / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.max_connections: int = int(os.getenv("WS_MAX_CONNECTIONS", "10"))

    async def connect(self, websocket: WebSocket) -> None:
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1013)
            logger.warning("WS connection refused: capacity reached")
            return
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WS connected: %s (active=%d)", id(websocket), len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WS disconnected: %s (active=%d)", id(websocket), len(self.active_connections))

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        await websocket.send_json(message)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001
                self.disconnect(connection)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    if websocket not in manager.active_connections:
        return

    try:
        await manager.send_personal_message({"type": "welcome", "message": "Connected to PeakPilot WebSocket", "timestamp": _now_ts()}, websocket)

        # Receive question with timeout
        try:
            received = await asyncio.wait_for(websocket.receive_text(), timeout=_WS_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await manager.send_personal_message({"type": "error", "message": "Timed out waiting for question.", "timestamp": _now_ts()}, websocket)
            await websocket.close()
            return

        question = received
        cache_key = _cache_key(question)
        cached = answer_cache.get(cache_key)
        if cached:
            await manager.send_personal_message({"type": "progress", "message": "Returning cached answer.", "timestamp": _now_ts()}, websocket)
            await manager.send_personal_message({"type": "answer", "data": {**cached, "cached": True}, "timestamp": _now_ts()}, websocket)
            await websocket.close()
            return

        async def on_progress(message: str) -> None:
            await manager.send_personal_message({"type": "progress", "message": message, "timestamp": _now_ts()}, websocket)

        try:
            result = await run_pipeline(question, on_progress)
            answer_cache.set(cache_key, result)
            await manager.send_personal_message({"type": "answer", "data": {**result, "cached": False}, "timestamp": _now_ts()}, websocket)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error in pipeline: %s", exc)
            await manager.send_personal_message({"type": "error", "message": str(exc), "timestamp": _now_ts()}, websocket)
        finally:
            await websocket.close()
    except WebSocketDisconnect:
        logger.info("WS client disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.exception("WS unexpected error: %s", exc)
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        manager.disconnect(websocket)


@app.post("/api/ask")
async def api_ask(payload: AskRequest) -> Any:
    try:
        cache_key = _cache_key(payload.question)
        cached = answer_cache.get(cache_key)
        if cached:
            return {"ok": True, "data": {**cached, "cached": True}, "logs": []}

        logs: List[str] = []

        async def on_progress(message: str) -> None:
            logs.append(f"{_now_ts()} {message}")

        result = await run_pipeline(payload.question, on_progress)
        answer_cache.set(cache_key, result)
        return {"ok": True, "data": {**result, "cached": False}, "logs": logs}
    except Exception as exc:  # noqa: BLE001
        logger.exception("/api/ask error: %s", exc)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})

