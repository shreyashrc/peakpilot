from typing import Any, Dict, List

from llm.gemini_client import GeminiClient
from rag.vector_store import VectorStore


class RAGSkill:
    """RAG pipeline coordinator: embed -> store -> retrieve -> generate."""

    def __init__(self) -> None:
        self.vs = VectorStore()
        self.llm = GeminiClient()

    def process_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Add documents to the vector store with embeddings.

        Each document is expected to contain keys: text, source, trail_name, section_type, url.
        """
        # Session-scoped behavior: clear previous question's docs to avoid cross-trail bleed
        try:
            self.vs.clear_session()
        except Exception:
            # ignore if clear fails; we'll upsert anyway
            pass
        texts: List[str] = []
        metas: List[Dict[str, Any]] = []
        for doc in documents:
            text = doc.get("text") or doc.get("content") or ""
            if not text:
                continue
            meta = {
                "source": doc.get("source", "unknown"),
                "trail_name": doc.get("trail_name", "unknown"),
                "section_type": doc.get("section_type", "unknown"),
                "url": doc.get("url", ""),
            }
            texts.append(text)
            metas.append(meta)
        if not texts:
            return []
        return self.vs.add_documents(texts, metas)

    def retrieve_context(self, question: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for the most relevant chunks for the question."""
        return self.vs.search(question, k=k)

    def generate_answer(self, question: str, context: List[Dict[str, Any]]) -> str:
        """Create a prompt from top-k context and ask the LLM to answer."""
        ctx_lines: List[str] = []
        for item in context:
            meta = item.get("metadata", {})
            src = meta.get("source", "")
            name = meta.get("trail_name", "")
            url = meta.get("url", "")
            line = f"[{src}] {name} | {url}\n{item.get('text', '')}"
            ctx_lines.append(line)
        ctx_text = "\n\n".join(ctx_lines) if ctx_lines else "(no context)"
        return self.llm.generate_answer(ctx_text, question)

