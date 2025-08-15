import hashlib
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional


# Default TTLs (minutes)
DEFAULT_QUESTION_TTL_MIN = int(os.getenv("CACHE_TTL_MINUTES", "5"))
DEFAULT_WEATHER_TTL_MIN = int(os.getenv("WEATHER_CACHE_TTL_MINUTES", "60"))
DEFAULT_TRAIL_INFO_TTL_MIN = 24 * 60


QUESTION_CACHE = "question"
WEATHER_CACHE = "weather"
TRAIL_INFO_CACHE = "trail_info"
SESSION_CACHE = "session"


@dataclass
class CacheEntry:
    value: Any
    expires_at: float  # monotonic time when entry expires
    last_access: float


class CacheManager:
    """In-memory TTL cache with simple LRU eviction per cache type.

    - Multiple named caches: question, weather, trail_info, session
    - TTL-based expiry using monotonic clock
    - LRU eviction when cache exceeds max_entries
    - Key generation helper for normalized questions
    """

    def __init__(self, max_entries: int = 100) -> None:
        self.max_entries = max_entries
        self._caches: Dict[str, OrderedDict[str, CacheEntry]] = {}

    # -------------------- helpers --------------------
    @staticmethod
    def generate_key_from_question(question: str) -> str:
        normalized = (question or "").strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _now(self) -> float:
        return time.monotonic()

    def _get_cache(self, cache_type: str) -> OrderedDict:
        if cache_type not in self._caches:
            self._caches[cache_type] = OrderedDict()
        return self._caches[cache_type]

    def _prune_expired(self, cache_type: Optional[str] = None) -> None:
        if cache_type:
            caches = [cache_type]
        else:
            caches = list(self._caches.keys())
        now = self._now()
        for ctype in caches:
            cache = self._get_cache(ctype)
            to_delete = [k for k, entry in cache.items() if entry.expires_at <= now]
            for k in to_delete:
                cache.pop(k, None)

    def _evict_if_needed(self, cache_type: str) -> None:
        cache = self._get_cache(cache_type)
        while len(cache) > self.max_entries:
            cache.popitem(last=False)  # evict least recently used

    # -------------------- public API --------------------
    def get(self, key: str, cache_type: str = QUESTION_CACHE) -> Any:
        self._prune_expired(cache_type)
        cache = self._get_cache(cache_type)
        entry = cache.get(key)
        if not entry:
            return None
        # refresh LRU and access time
        entry.last_access = self._now()
        cache.move_to_end(key, last=True)
        return entry.value

    def set(self, key: str, value: Any, ttl_minutes: int, cache_type: str = QUESTION_CACHE) -> None:
        self._prune_expired(cache_type)
        cache = self._get_cache(cache_type)
        expires_at = self._now() + (ttl_minutes * 60)
        cache[key] = CacheEntry(value=value, expires_at=expires_at, last_access=self._now())
        cache.move_to_end(key, last=True)
        self._evict_if_needed(cache_type)

    def invalidate(self, pattern: Optional[str] = None, cache_type: Optional[str] = None) -> int:
        """Invalidate entries by substring/regex pattern. Returns number removed.

        If cache_type is None, applies to all caches. If pattern is None, clears the cache(s).
        """
        removed = 0
        targets = [cache_type] if cache_type else list(self._caches.keys())
        if not targets:
            return 0

        if pattern is None:
            for ctype in targets:
                removed += len(self._get_cache(ctype))
                self._caches[ctype] = OrderedDict()
            return removed

        # try regex
        try:
            regex = re.compile(pattern)
            matcher = lambda k: bool(regex.search(k))  # noqa: E731
        except re.error:
            substr = pattern
            matcher = lambda k: substr in k  # noqa: E731

        for ctype in targets:
            cache = self._get_cache(ctype)
            keys = list(cache.keys())
            for k in keys:
                if matcher(k):
                    cache.pop(k, None)
                    removed += 1
        return removed

    def clear_cache(self, cache_type: str) -> None:
        self._caches[cache_type] = OrderedDict()

    # -------------------- convenience --------------------
    def cache_answer(self, question: str, value: Any) -> None:
        key = self.generate_key_from_question(question)
        self.set(key, value, ttl_minutes=DEFAULT_QUESTION_TTL_MIN, cache_type=QUESTION_CACHE)

    def get_cached_answer(self, question: str) -> Any:
        key = self.generate_key_from_question(question)
        return self.get(key, cache_type=QUESTION_CACHE)

    def cache_weather(self, trail: str, value: Any) -> None:
        self.set(trail, value, ttl_minutes=DEFAULT_WEATHER_TTL_MIN, cache_type=WEATHER_CACHE)

    def get_cached_weather(self, trail: str) -> Any:
        return self.get(trail, cache_type=WEATHER_CACHE)

    def cache_trail_info(self, trail: str, value: Any) -> None:
        self.set(trail, value, ttl_minutes=DEFAULT_TRAIL_INFO_TTL_MIN, cache_type=TRAIL_INFO_CACHE)

    def get_cached_trail_info(self, trail: str) -> Any:
        return self.get(trail, cache_type=TRAIL_INFO_CACHE)

