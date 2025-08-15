from typing import Any, Dict, Optional

from mcp.skills.base_skill import BaseSkill, ProgressCallback
from crawler.weather_crawler import WeatherCrawler


class WeatherSkill(BaseSkill):
    def __init__(self) -> None:
        self.crawler = WeatherCrawler()

    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        entities = context.get("entities", {}) or {}
        intent = entities.get("intent")
        trail = entities.get("trail")

        needs_weather = intent in {"weather", "safety"}
        if not needs_weather or not trail:
            return context

        if callback:
            await callback("☁️ Fetching weather forecast...")

        try:
            weather = await self.crawler.fetch_weather(str(trail))
            context["weather"] = weather
            context.setdefault("debug_logs", []).append({
                "ts": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                "stage": "weather",
                "message": f"weather_source={weather.get('source_url')}",
            })
        except Exception as exc:  # noqa: BLE001
            if callback:
                await callback(f"Weather fetch failed: {exc}")
        return context

