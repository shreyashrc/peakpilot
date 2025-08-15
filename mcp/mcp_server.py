import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from mcp.skills.base_skill import BaseSkill, ProgressCallback
from mcp.skills.search_skill import SearchSkill as _SearchSkill
from rag.rag_skill import RAGSkill as _RAGSkill
from mcp.skills.weather_skill import WeatherSkill as _WeatherSkill
from mcp.skills.gpx_skill import GPXSkill as _GPXSkill
from crawler.search_aggregator import SearchAggregator
from crawler.indiahikes_crawler import IndiahikesCrawler
from utils.config import get_source_order, is_enabled


class SearchSkill(BaseSkill):
    def __init__(self) -> None:
        self.impl = _SearchSkill()

    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        question = context.get("question", "")
        if callback:
            await callback("Identifying trail locations...")
        entities = self.impl.extract_entities(question)
        context["entities"] = entities
        # Debug and logs
        context.setdefault("debug_logs", []).append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": "search",
            "message": f"entities={entities}",
        })
        logging.getLogger("peakpilot.mcp").info("SearchSkill: entities=%s", entities)
        return context


class CrawlerSkill(BaseSkill):
    def __init__(self) -> None:
        self.web = SearchAggregator(max_results=5)
        self.ih = IndiahikesCrawler(max_results=3)
        self.source_order = get_source_order()

    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        entities = context.get("entities", {})
        sources: List[str] = entities.get("sources", []) if isinstance(entities, dict) else []
        trail = entities.get("trail") if isinstance(entities, dict) else None
        if not trail:
            if callback:
                await callback("No trail detected; skipping crawl")
            logging.getLogger("peakpilot.mcp").info("CrawlerSkill: no trail detected")
            context.setdefault("documents", [])
            return context
        docs: List[Dict[str, Any]] = []

        # Configurable source order and toggles
        sources_to_try: List[str] = []
        for s in self.source_order:
            if is_enabled(s):
                sources_to_try.append(s)

        for src in sources_to_try:
            if src == "indiahikes":
                if callback:
                    await callback("Fetching content from Indiahikes...")
                try:
                    docs.extend(await self.ih.fetch(str(trail)))
                except Exception as exc:
                    if callback:
                        await callback(f"Indiahikes fetch failed: {exc}")
            elif src == "web":
                if callback:
                    await callback("Searching the web for reliable sources...")
                try:
                    docs.extend(await self.web.search(str(trail), intent=entities.get("intent")))
                except Exception as exc:
                    if callback:
                        await callback(f"Web search failed: {exc}")
            # Wikipedia/Wikivoyage permanently removed from pipeline

        # If docs still empty, try Wikipedia as a fallback (use 'Lake' suffix if needed)
        if not docs and trail:
            if callback:
                await callback("Trying Wikipedia as a fallback...")
            try:
                query = str(trail)
                html, url = await self.wp.fetch_page(query)
                if not html and " " in query:
                    # Try appending 'Lake' for alpine lakes like Tso Moriri
                    html, url = await self.wp.fetch_page(query + " Lake")
                if html:
                    sections = self.wp.extract_content(html)
                    for section, text in (sections or {}).items():
                        docs.append({
                            "text": text,
                            "source": "wikipedia",
                            "trail_name": str(trail),
                            "section_type": section,
                            "url": url or "",
                        })
            except Exception as exc:  # noqa: BLE001
                if callback:
                    await callback(f"Wikipedia fallback failed: {exc}")

        # Prefer Indiahikes if still empty (high-quality trek-specific content)
        if not docs and trail:
            if callback:
                await callback("Fetching content from Indiahikes...")
            try:
                ih_docs = await self.ih.fetch(str(trail))
                docs.extend(ih_docs)
            except Exception as exc:  # noqa: BLE001
                if callback:
                    await callback(f"Indiahikes fetch failed: {exc}")

        # If still empty, perform a web meta-search and extract content
        if not docs and trail:
            if callback:
                await callback("Searching the web for reliable sources...")
            try:
                web_docs = await self.web.search(str(trail), intent=entities.get("intent"))
                docs.extend(web_docs)
            except Exception as exc:  # noqa: BLE001
                if callback:
                    await callback(f"Web search failed: {exc}")

        context.setdefault("documents", docs)
        if callback:
            await callback(f"Collected documents: {len(docs)}")
        context.setdefault("debug_logs", []).append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": "crawler",
            "message": f"documents_collected={len(docs)}",
        })
        return context


class RAGSkill(BaseSkill):
    def __init__(self, impl: Optional[_RAGSkill] = None) -> None:
        self.impl = impl or _RAGSkill()

    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        docs: List[Dict[str, Any]] = context.get("documents", [])
        if callback:
            await callback("Generating embeddings...")
        try:
            self.impl.process_documents(docs)
            if callback:
                await callback(f"Indexed documents: {len(docs)}")
            context.setdefault("debug_logs", []).append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "stage": "rag",
                "message": f"indexed_docs={len(docs)}",
            })
            logging.getLogger("peakpilot.mcp").info("RAGSkill: indexed_docs=%d", len(docs))
        except Exception as exc:  # noqa: BLE001
            if callback:
                await callback(f"RAG ingestion failed: {exc}")
            logging.getLogger("peakpilot.mcp").warning("RAGSkill failed: %s", exc)
        return context


class AnswerSkill(BaseSkill):
    def __init__(self, impl: Optional[_RAGSkill] = None) -> None:
        self.impl = impl or _RAGSkill()

    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        question: str = context.get("question", "")
        if callback:
            await callback("Preparing comprehensive answer...")
        try:
            ctx = self.impl.retrieve_context(question, k=5)
            answer = self.impl.generate_answer(question, ctx)
            if callback:
                await callback(f"Retrieved context chunks: {len(ctx)}")
            context.setdefault("debug_logs", []).append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "stage": "answer",
                "message": f"retrieved_context={len(ctx)}",
            })
            logging.getLogger("peakpilot.mcp").info("AnswerSkill: context_chunks=%d", len(ctx))
        except Exception as exc:  # noqa: BLE001
            if callback:
                await callback(f"Answer generation failed: {exc}")
            answer = "Could not generate an answer at this time."
            ctx = []
            logging.getLogger("peakpilot.mcp").warning("AnswerSkill failed: %s", exc)
        context["answer"] = answer
        context["retrieved_context"] = ctx
        return context


class MCPOchestrator:
    def __init__(self) -> None:
        shared_rag = _RAGSkill()
        self.pipeline: List[BaseSkill] = [
            SearchSkill(),
            CrawlerSkill(),
            _WeatherSkill(),
            _GPXSkill(),
            RAGSkill(shared_rag),
            AnswerSkill(shared_rag),
        ]

    async def run(self, question: str, callback: ProgressCallback = None) -> Dict[str, Any]:
        context: Dict[str, Any] = {"question": question}
        for skill in self.pipeline:
            try:
                context = await skill.execute(context, callback)
            except Exception as exc:  # noqa: BLE001
                # Continue with partial context
                if callback:
                    await callback(f"{skill.__class__.__name__} failed: {exc}")
        return context

