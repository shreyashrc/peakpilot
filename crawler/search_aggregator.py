import asyncio
from typing import Any, Dict, List, Optional

import trafilatura
from duckduckgo_search import DDGS


class SearchAggregator:
    """Meta-search + content fetcher for trekking queries.

    - Uses DuckDuckGo to find candidate pages (official tourism, OSM wiki, Wikivoyage/Wikipedia, credible blogs)
    - Fetches and extracts readable text with trafilatura
    - Returns top-N cleaned documents with source metadata
    """

    def __init__(self, max_results: int = 8) -> None:
        self.max_results = max_results
        # Simple domain scoring for credibility
        self.domain_weights = {
            "wikipedia.org": 0.9,
            "wikivoyage.org": 0.5,
            "wiki.openstreetmap.org": 0.8,
            "mountain-forecast.com": 0.85,
            "alltrails.com": 0.6,
        }

    async def search(self, trail: str, intent: Optional[str] = None) -> List[Dict[str, Any]]:
        # Build multiple focused queries
        intent_terms = {
            "permits": "permits entry rules",
            "safety": "safety conditions",
            "weather": "weather mountain-forecast",
            "difficulty": "difficulty elevation distance",
            "accommodation": "accommodation camping guesthouse",
            "general": "trek route details",
        }.get((intent or "general").lower(), "trek route details")

        queries = [
            f"{trail} trek {intent_terms}",
            f"{trail} trek route difficulty distance",
            f"{trail} trek permits",
            f"{trail} trek GPX OSM",
        ]

        seen_urls: set = set()
        ranked: List[Dict[str, Any]] = []
        with DDGS() as ddgs:
            for q in queries:
                hits = ddgs.text(
                    q,
                    max_results=max(2, self.max_results // len(queries)),
                    region="in-en",
                    safesearch="moderate",
                    timelimit=None,
                )
                for h in hits or []:
                    url = h.get("href") or h.get("link") or h.get("url")
                    if not url or url in seen_urls:
                        continue
                    if self._is_blacklisted(url):
                        continue
                    seen_urls.add(url)
                    weight = self._score_url(url)
                    ranked.append({"title": h.get("title", ""), "url": url, "weight": weight})

        # Take top by weight
        ranked.sort(key=lambda x: x["weight"], reverse=True)
        top_hits = ranked[: self.max_results]

        # Fetch content concurrently
        docs: List[Dict[str, Any]] = []
        tasks = [self._fetch_and_extract(r) for r in top_hits]
        for coro in asyncio.as_completed(tasks):
            doc = await coro
            if doc:
                docs.append(doc)
        return docs

    async def _fetch_and_extract(self, hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = hit.get("url")
        if not url:
            return None
        try:
            # trafilatura fetches and extracts readable text
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None
            text = trafilatura.extract(downloaded)
            if not text:
                return None
            # Basic language/quality filters: prefer English/ASCII-heavy and trekking keywords
            if self._ascii_ratio(text) < 0.7:
                return None
            if not self._looks_like_trek_content(hit.get("title", ""), text):
                return None
            return {
                "text": text[:4000],
                "source": self._source_from_url(url),
                "trail_name": hit.get("title", ""),
                "section_type": "webpage",
                "url": url,
            }
        except Exception:
            return None

    def _score_url(self, url: str) -> float:
        try:
            from urllib.parse import urlparse

            netloc = urlparse(url).netloc.lower()
            # Prefer official .gov.in tourism pages
            if netloc.endswith(".gov.in"):
                return 1.0
            for dom, w in self.domain_weights.items():
                if dom in netloc:
                    return w
        except Exception:
            return 0.1
        return 0.3

    def _source_from_url(self, url: str) -> str:
        try:
            from urllib.parse import urlparse

            host = urlparse(url).netloc.lower()
            if host.endswith(".gov.in"):
                return "gov.in"
            if "wikipedia.org" in host:
                return "wikipedia"
            if "wikivoyage.org" in host:
                return "wikivoyage"
            if "mountain-forecast.com" in host:
                return "mountain-forecast"
            if "openstreetmap.org" in host:
                return "osm"
        except Exception:
            pass
        return "web"

    def _is_blacklisted(self, url: str) -> bool:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower()
        blacklist = [
            "baidu.com",
            "zhihu.com",
            "reddit.com",
            "youtube.com",
            "bilibili.com",
            "fandom.com",
        ]
        return any(b in host for b in blacklist)

    def _ascii_ratio(self, text: str) -> float:
        if not text:
            return 0.0
        ascii_chars = sum(1 for ch in text if ord(ch) < 128)
        return ascii_chars / max(1, len(text))

    def _looks_like_trek_content(self, title: str, text: str) -> bool:
        t = (title + "\n" + text).lower()
        must_any = ["trek", "trail", "hike", "itinerary", "altitude", "permit", "distance", "elevation"]
        india_terms = ["india", "uttarakhand", "ladakh", "himachal", "maharashtra", "kashmir", "sikkim"]
        return any(k in t for k in must_any) and any(k in t for k in india_terms)

