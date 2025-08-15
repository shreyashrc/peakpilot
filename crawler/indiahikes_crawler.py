import asyncio
from typing import Any, Dict, List

import trafilatura
from ddgs import DDGS


class IndiahikesCrawler:
    """Fetch trek pages from Indiahikes and extract readable content.

    Uses DuckDuckGo site search to find relevant Indiahikes pages, then
    extracts text with trafilatura. Returns a small set of docs.
    """

    def __init__(self, max_results: int = 3, rate_delay_seconds: float = 0.2) -> None:
        self.max_results = max_results
        self.rate_delay_seconds = rate_delay_seconds

    async def fetch(self, trail: str) -> List[Dict[str, Any]]:
        queries = [
            f"site:indiahikes.com {trail} trek",
            f"site:indiahikes.com {trail} difficulty distance itinerary",
            f"site:indiahikes.com best time {trail}",
        ]
        hits: List[Dict[str, str]] = []
        with DDGS() as ddgs:
            for q in queries:
                res = ddgs.text(q, max_results=self.max_results)
                for r in res or []:
                    url = r.get("href") or r.get("link") or r.get("url")
                    if not url or "indiahikes.com" not in (url or ""):
                        continue
                    hits.append({"title": r.get("title", ""), "url": url})

        # Fetch content concurrently
        tasks = [self._fetch_one(h) for h in hits]
        docs: List[Dict[str, Any]] = []
        for coro in asyncio.as_completed(tasks):
            doc = await coro
            if doc:
                docs.append(doc)
        return docs

    async def _fetch_one(self, hit: Dict[str, str]) -> Dict[str, Any] | None:
        await asyncio.sleep(self.rate_delay_seconds)
        url = hit.get("url")
        if not url:
            return None
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None
            text = trafilatura.extract(downloaded)
            if not text:
                return None
            return {
                "text": text[:6000],
                "source": "indiahikes",
                "trail_name": hit.get("title", ""),
                "section_type": "webpage",
                "url": url,
            }
        except Exception:
            return None

