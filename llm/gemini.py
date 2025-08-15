import os
from typing import Any, Dict, List

import google.generativeai as genai


def _configure() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)


def embed_texts(texts: List[str], model: str = "text-embedding-004") -> List[List[float]]:
    _configure()
    if not os.getenv("GEMINI_API_KEY"):
        return [[0.0] * 10 for _ in texts]
    resp = genai.embed_content(model=model, content=texts)
    # genai SDK may return different envelope shapes based on version
    if isinstance(resp, dict) and "embeddings" in resp:
        return [e.get("values", []) for e in resp["embeddings"]]
    if hasattr(resp, "embeddings"):
        return [e.values for e in resp.embeddings]  # type: ignore[attr-defined]
    return []


def generate_answer(prompt: str, model: str = "gemini-1.5-pro") -> str:
    _configure()
    if not os.getenv("GEMINI_API_KEY"):
        return "LLM not configured. Provide GEMINI_API_KEY to enable generation."
    llm = genai.GenerativeModel(model)
    resp = llm.generate_content(prompt)
    return getattr(resp, "text", "")
