import asyncio
import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from api.main import app
from mcp.mcp_server import MCPOchestrator
from mcp.skills.search_skill import SearchSkill
from crawler.indiahikes_crawler import IndiahikesCrawler
from rag.rag_skill import RAGSkill
from utils.cache import CacheManager


# ---------------- Unit tests ----------------

def test_search_skill_entity_extraction():
	s = SearchSkill()
	entities = s.extract_entities("Is Kedarkanta safe in December?")
	assert entities["trail"] == "Kedarkantha"
	assert entities["intent"] in {"safety", "weather"}
	assert "December" in entities["months"]


def test_crawler_indiahikes(monkeypatch):
	# Mock Indiahikes fetch to avoid network
	async def fake_fetch(self, trail: str):
		return [{"text": f"{trail} itinerary and difficulty", "source": "indiahikes", "url": "https://indiahikes.com/foo"}]

	monkeypatch.setattr(IndiahikesCrawler, "fetch", fake_fetch)

	ih = IndiahikesCrawler(max_results=1)
	docs = asyncio.run(ih.fetch("Kedarkantha"))
	assert isinstance(docs, list) and len(docs) == 1


def test_rag_skill_retrieval(tmp_path):
	rag = RAGSkill()
	ids = rag.process_documents([
		{"text": "Kedarkantha is a winter trek.", "source": "indiahikes", "trail_name": "Kedarkantha", "section_type": "overview", "url": "https://example.com"},
		{"text": "Triund near Dharamshala is beginner-friendly.", "source": "indiahikes", "trail_name": "Triund", "section_type": "overview", "url": "https://example.com"},
	])
	assert len(ids) == 2
	ctx = rag.retrieve_context("winter trek Kedarkantha", k=2)
	assert isinstance(ctx, list) and len(ctx) >= 1


# ---------------- Integration test ----------------

def test_full_pipeline_kedarkantha(monkeypatch):
	orch = MCPOchestrator()
	ctx = asyncio.run(orch.run("Is Kedarkantha safe in December?"))
	assert "answer" in ctx
	assert isinstance(ctx.get("retrieved_context", []), list)


# ---------------- WebSocket streaming test ----------------

def test_websocket_streaming(monkeypatch):
	client = TestClient(app)
	with client.websocket_connect("/ws") as ws:
		ws.send_text("Is Kedarkantha safe in December?")
		received_progress = False
		received_answer = False
		for _ in range(20):
			try:
				msg = ws.receive_json()
			except Exception:
				break
			if msg.get("type") == "progress":
				received_progress = True
			if msg.get("type") == "answer":
				received_answer = True
				break
		assert received_progress and received_answer


# ---------------- Cache tests ----------------

def test_cache_hit_miss_and_ttl():
	c = CacheManager(max_entries=10)
	# Miss
	assert c.get("missing") is None
	# Hit
	c.set("k", 123, ttl_minutes=1)
	assert c.get("k") == 123
	# Expire immediately with ttl=0
	c.set("x", 999, ttl_minutes=0)
	assert c.get("x") is None


def test_cache_invalidation():
	c = CacheManager(max_entries=10)
	c.set("a-ked", 1, ttl_minutes=10)
	c.set("b-tri", 2, ttl_minutes=10)
	removed = c.invalidate(pattern="ked")
	assert removed == 1
	assert c.get("a-ked") is None


# ---------------- Error handling tests ----------------

def test_error_unavailable_sources(monkeypatch):
	# Simulate an error in one source by monkeypatching IndiahikesCrawler
	async def failing_fetch(self, trail: str):
		raise TimeoutError("simulated timeout")
	monkeypatch.setattr(IndiahikesCrawler, "fetch", failing_fetch)
	orch = MCPOchestrator()
	ctx = asyncio.run(orch.run("Is Kedarkantha safe in December?"))
	# Should still return an answer field
	assert "answer" in ctx


def test_invalid_api_key(monkeypatch):
	# Ensure no API key set so client falls back
	os.environ.pop("GEMINI_API_KEY", None)
	orch = MCPOchestrator()
	ctx = asyncio.run(orch.run("Tell me about Triund"))
	assert isinstance(ctx.get("answer", ""), str)
	assert len(ctx.get("answer", "")) > 0

