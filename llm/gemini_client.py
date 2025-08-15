import os
import time
from typing import Any, List, Optional

import google.generativeai as genai
import logging


class GeminiClient:
    """Lightweight wrapper around google-generativeai with retries and fallbacks."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-004",
        generation_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        max_retries: int = 3,
        backoff_seconds: float = 0.8,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

        if self.api_key:
            genai.configure(api_key=self.api_key)

    def _ensure_configured(self) -> bool:
        """Ensure the Google GenAI client is configured with the latest API key.

        Re-reads GEMINI_API_KEY from environment at call-time so the client works
        even if the key was added after process startup.
        """
        env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if env_key and env_key != self.api_key:
            self.api_key = env_key
            try:
                genai.configure(api_key=self.api_key)
            except Exception:
                pass
        return bool(self.api_key)

    def generate_embedding(self, text: str) -> List[float]:
        """Return a single embedding vector for the given text.

        Falls back to a small zero-vector if API key isn't configured or on failure.
        """
        if not self._ensure_configured():
            return [0.0] * 10

        attempt = 0
        while True:
            try:
                resp: Any = genai.embed_content(model=self.embedding_model, content=text)
                if isinstance(resp, dict) and "embedding" in resp:
                    # Some versions may return a single embedding
                    values = resp.get("embedding", {}).get("values") or resp.get("embedding")
                    if isinstance(values, list):
                        return values
                if isinstance(resp, dict) and "embeddings" in resp:
                    emb = resp["embeddings"][0]
                    values = emb.get("values", [])
                    return values
                if hasattr(resp, "embeddings"):
                    return resp.embeddings[0].values  # type: ignore[attr-defined]
                return [0.0] * 10
            except Exception as exc:
                logging.getLogger("peakpilot.llm").warning("Gemini embed failed: %s", exc)
                attempt += 1
                if attempt >= self.max_retries:
                    return [0.0] * 10
                time.sleep(self.backoff_seconds * attempt)

    def generate_answer(self, context: str, question: str) -> str:
        """Generate an answer using the provided context and question.

        Returns a helpful text answer; falls back to an informative message if API key not configured.
        """
        # Natural, helpful default prompt with RAG, without forcing "based on context" phrasing
        prompt = (
            "You are PeakPilot, a helpful hiking assistant for Indian treks.\n"
            "You have some relevant notes below. Use them when helpful, but speak naturally and answer directly.\n"
            "If something is uncertain or missing, say so briefly and suggest how to verify.\n\n"
            "Notes (may be partial):\n" + context + "\n\n"
            "User question: " + question + "\n\n"
            "Instructions:\n"
            "- Give a concise, accurate answer first.\n"
            "- Include trek specifics (distance, elevation gain, difficulty, best time, permits) when relevant.\n"
            "- If you cite, use [Source: domain or name].\n"
            "- If asked about current weather/conditions, note that real-time checks may be required.\n"
        )

        if not self._ensure_configured():
            return (
                "LLM not configured (missing GEMINI_API_KEY). Context-aware generation is disabled for now.\n\n"
                + prompt
            )

        attempt = 0
        tried_flash = False
        while True:
            try:
                model_name = self.generation_model if not tried_flash else "gemini-2.5-flash"
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                return getattr(resp, "text", "") or ""
            except Exception as exc:
                logging.getLogger("peakpilot.llm").warning("Gemini generate failed (model=%s): %s", self.generation_model, exc)
                if not tried_flash:
                    # Try a faster, more available model as fallback
                    tried_flash = True
                    continue
                attempt += 1
                if attempt >= self.max_retries:
                    return "Failed to generate answer at this time. Please try again later."
                time.sleep(self.backoff_seconds * attempt)

