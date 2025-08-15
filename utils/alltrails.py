from typing import Optional, Dict, Any

from duckduckgo_search import DDGS

from utils.cache import CacheManager


_KNOWN_SLUGS: Dict[str, str] = {
    # Curated direct links for popular Indian treks
    "Kalsubai": "https://www.alltrails.com/trail/india/maharashtra/kalsubai-peak-trail",
    "Triund": "https://www.alltrails.com/trail/india/himachal-pradesh/triund-trek",
    # "Kedarkantha": "https://www.alltrails.com/trail/india/uttarakhand/kedarkantha-trek",  # Uncomment if verified
}


_cache = CacheManager(max_entries=100)


def resolve_alltrails_url(trail: str) -> Optional[str]:
    if not trail:
        return None
    # Known slugs
    if trail in _KNOWN_SLUGS:
        return _KNOWN_SLUGS[trail]

    # Cached
    cached = _cache.get_cached_trail_info(trail)
    if isinstance(cached, dict) and cached.get("alltrails_url"):
        return cached.get("alltrails_url")

    # Simple brand-aware search: "all trails <trail>"
    queries = [
        f"all trails {trail} india",
        f"all trails {trail} trek",
        f"alltrails {trail} india",
    ]
    url: Optional[str] = None
    with DDGS() as ddgs:
        for q in queries:
            hits = ddgs.text(q, max_results=5, region="in-en", safesearch="moderate")
            for h in hits or []:
                href = h.get("href") or h.get("link") or h.get("url")
                if not href:
                    continue
                if "alltrails.com" in href and "/trail/" in href and "/search" not in href:
                    url = href
                    break
            if url:
                break
    if url:
        _cache.cache_trail_info(trail, {"alltrails_url": url})
    return url

