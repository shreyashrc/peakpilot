import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup


class WeatherCrawler:
    def __init__(self, rate_delay_seconds: float = 0.4, ttl_minutes: Optional[int] = None) -> None:
        self.base = os.getenv("MOUNTAIN_FORECAST_BASE", "https://www.mountain-forecast.com/peaks/")
        self.rate_delay_seconds = rate_delay_seconds
        self.ttl_minutes = int(os.getenv("WEATHER_CACHE_TTL_MINUTES", "60")) if ttl_minutes is None else ttl_minutes
        self._cache: Dict[str, Dict[str, Any]] = {}

        self.trail_to_peak: Dict[str, str] = {
            "Kedarkantha": "Kedarkantha",
            "Kalsubai": "Kalsubai",
            # Use a nearby notable peak for Valley of Flowers (Uttarakhand region)
            "Valley of Flowers": "Trisul",
        }

    async def _try_fetch(self, url: str) -> Tuple[Optional[str], str]:
        timeout = aiohttp.ClientTimeout(total=20)
        await asyncio.sleep(self.rate_delay_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": "PeakPilotBot/0.1"}) as resp:
                    if resp.status == 404:
                        return None, url
                    resp.raise_for_status()
                    return await resp.text(), str(resp.url)
        except asyncio.TimeoutError:
            return None, url
        except aiohttp.ClientError:
            return None, url

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if entry["expires_at"] < datetime.now(timezone.utc):
            self._cache.pop(key, None)
            return None
        return entry["data"]

    def _cache_set(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = {
            "data": data,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=self.ttl_minutes),
        }

    def _peak_url(self, trail: str) -> Optional[str]:
        peak = self.trail_to_peak.get(trail)
        if not peak:
            return None
        return f"{self.base}{peak}/forecasts"

    def _extract_summary(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else ""

    def _extract_elevation_blocks(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        results: Dict[str, Dict[str, str]] = {}

        # Heuristic parsing: look for elements that hint at elevations
        headings = soup.find_all(["h2", "h3"])
        for hd in headings:
            title = hd.get_text(" ", strip=True).lower()
            if any(k in title for k in ["summit", "mid", "base"]):
                buf = []
                for sib in hd.next_siblings:
                    if getattr(sib, "name", None) in {"h2", "h3"}:
                        break
                    if getattr(sib, "name", None) == "p":
                        buf.append(sib.get_text(" ", strip=True))
                block = " ".join(buf)
                if "summit" in title:
                    results["summit"] = {"temp": "", "conditions": block}
                elif "mid" in title:
                    results["mid"] = {"temp": "", "conditions": block}
                elif "base" in title:
                    results["base"] = {"temp": "", "conditions": block}

        # If nothing found, try a simplified extraction from tables
        if not results:
            table = soup.find("table")
            if table:
                txt = table.get_text(" ", strip=True)[:400]
                results["summary"] = {"temp": "", "conditions": txt}
        return results

    async def fetch_weather(self, trail: str) -> Dict[str, Any]:
        key = f"weather:{trail}"
        cached = self._cache_get(key)
        if cached:
            return cached

        url = self._peak_url(trail)
        if not url:
            data = {
                "trail": trail,
                "elevations": {},
                "forecast_date": datetime.now(timezone.utc).date().isoformat(),
                "warnings": ["No mapped peak for this trail"],
                "source_url": None,
                "summary": "",
            }
            self._cache_set(key, data)
            return data

        html, final_url = await self._try_fetch(url)
        if not html:
            data = {
                "trail": trail,
                "elevations": {},
                "forecast_date": datetime.now(timezone.utc).date().isoformat(),
                "warnings": ["Unable to fetch mountain-forecast page"],
                "source_url": url,
                "summary": "",
            }
            self._cache_set(key, data)
            return data

        soup = BeautifulSoup(html, "html.parser")
        summary = self._extract_summary(soup)
        blocks = self._extract_elevation_blocks(soup)

        elevs: Dict[str, Dict[str, str]] = {}
        # Map to requested elevation keys if possible
        if "base" in blocks:
            elevs["base"] = blocks["base"]
        if "mid" in blocks:
            elevs["mid"] = blocks["mid"]
        if "summit" in blocks:
            elevs["summit"] = blocks["summit"]
        if not elevs and "summary" in blocks:
            elevs["summary"] = blocks["summary"]

        data = {
            "trail": trail,
            "elevations": elevs,
            "forecast_date": datetime.now(timezone.utc).date().isoformat(),
            "warnings": [],
            "source_url": final_url,
            "summary": summary,
        }
        self._cache_set(key, data)
        return data

