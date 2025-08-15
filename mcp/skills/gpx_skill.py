import os
from typing import Any, Dict, Optional

from mcp.skills.base_skill import BaseSkill, ProgressCallback
from utils.alltrails import resolve_alltrails_url


TRAIL_GPX_DATA: Dict[str, Dict[str, str]] = {
    "Triund": {
        "distance": "14 km",
        "elevation_gain": "1100 m",
        "duration": "4-6 hours",
        "difficulty": "Moderate",
    },
    "Kedarkantha": {
        "distance": "24 km",
        "elevation_gain": "1250 m",
        "duration": "2-3 days",
        "difficulty": "Moderate",
    },
    "Valley of Flowers": {
        "distance": "17 km",
        "elevation_gain": "600 m",
        "duration": "1 day",
        "difficulty": "Moderate",
    },
    "Kalsubai": {
        "distance": "6 km",
        "elevation_gain": "800 m",
        "duration": "3-5 hours",
        "difficulty": "Moderate",
    },
    "Hampta Pass": {
        "distance": "35 km",
        "elevation_gain": "1500 m",
        "duration": "4-5 days",
        "difficulty": "Moderate-Difficult",
    },
}


def _estimate_duration(distance_km: float, elevation_gain_m: float) -> str:
    # Naismith's rule: 5 km/h + 600 m ascent/hour
    if distance_km <= 0:
        return "-"
    hours = (distance_km / 5.0) + (elevation_gain_m / 600.0)
    if hours <= 1.5:
        return "1-2 hours"
    if hours <= 3.5:
        return "2-4 hours"
    if hours <= 6.0:
        return "4-6 hours"
    if hours <= 10.0:
        return "6-10 hours"
    days = max(1, round(hours / 8.0))
    return f"{days}-{max(days, days+1)} days"


def _parse_km(text: str) -> float:
    try:
        t = text.lower().replace("km", "").strip()
        return float(t)
    except Exception:
        return 0.0


def _parse_m(text: str) -> float:
    try:
        t = text.lower().replace("m", "").strip()
        return float(t)
    except Exception:
        return 0.0


class GPXSkill(BaseSkill):
    def __init__(self) -> None:
        self.osm_wiki_base = os.getenv("OSM_WIKI_BASE", "https://wiki.openstreetmap.org/wiki/")

    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        entities = context.get("entities", {}) or {}
        trail: Optional[str] = entities.get("trail")
        if not trail:
            return context

        if callback:
            await callback("🗺️ Fetching GPX and trail stats...")

        # Prefer hardcoded stats for known trails
        stats = TRAIL_GPX_DATA.get(trail)
        if stats:
            # Compute duration estimate if missing
            distance_km = _parse_km(stats.get("distance", "0"))
            gain_m = _parse_m(stats.get("elevation_gain", "0"))
            if not stats.get("duration"):
                stats["duration"] = _estimate_duration(distance_km, gain_m)
            trail_map_url = f"https://www.openstreetmap.org/search?query={trail.replace(' ', '+')}"
            alltrails_url = resolve_alltrails_url(trail) or f"https://www.alltrails.com/search?q={trail.replace(' ', '+')}"
            context["gpx_data"] = {**stats}
            context["trail_map_url"] = trail_map_url
            context["alltrails_url"] = alltrails_url
            context.setdefault("debug_logs", []).append({
                "ts": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                "stage": "gpx",
                "message": f"gpx_hardcoded=true trail={trail}",
            })
            return context

        # Fallback: basic OSM page link for unknown trails
        context["gpx_data"] = {
            "distance": "-",
            "elevation_gain": "-",
            "duration": "-",
            "difficulty": "-",
        }
        context["trail_map_url"] = f"https://www.openstreetmap.org/search?query={trail.replace(' ', '+')}"
        context["alltrails_url"] = resolve_alltrails_url(trail) or f"https://www.alltrails.com/search?q={trail.replace(' ', '+')}"
        if callback:
            await callback("No GPX data available; linked map search instead.")
        context.setdefault("debug_logs", []).append({
            "ts": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            "stage": "gpx",
            "message": f"gpx_hardcoded=false trail={trail}",
        })
        return context

