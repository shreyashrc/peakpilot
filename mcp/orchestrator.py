from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List

from mcp.mcp_server import MCPOchestrator


ProgressCallback = Callable[[str], Awaitable[None]]


class Orchestrator:
    def __init__(self) -> None:
        self._orch = MCPOchestrator()

    async def process_question(self, question: str, progress_callback: ProgressCallback) -> Dict[str, Any]:
        await progress_callback("🔍 Analyzing your question...")
        # Delegate full pipeline execution to MCPOchestrator so all skills (including weather & gpx) run
        context: Dict[str, Any] = await self._orch.run(question, progress_callback)

        # Normalize response keys for API contract
        result = {
            "question": question,
            "timestamp": context.get("timestamp"),
            "entities": context.get("entities", {}),
            "sources": (context.get("entities", {}) or {}).get("sources", []),
            "raw_documents": context.get("documents", []),
            "embedded_documents": "stored",  # stored in vector DB
            "retrieved_context": context.get("retrieved_context", []),
            "final_answer": context.get("answer", "Sorry, I couldn't find enough information."),
            "weather": context.get("weather"),
            "gpx_data": context.get("gpx_data"),
            "trail_map_url": context.get("trail_map_url"),
            "alltrails_url": context.get("alltrails_url"),
            "debug_logs": context.get("debug_logs", []),
        }

        # Graceful degradation messaging
        if not result["raw_documents"] and not result["retrieved_context"]:
            await progress_callback("⚠️ Not enough data found; responding with a general answer.")

        return result


_global_orchestrator = Orchestrator()


async def run_pipeline(question: str, on_progress: ProgressCallback) -> Dict[str, Any]:
    return await _global_orchestrator.process_question(question, on_progress)
