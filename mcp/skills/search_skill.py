import os
import re
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Dict, List, Optional, Tuple


_DEFAULT_TRAILS: List[str] = [
    "Triund",
    "Kedarkantha",
    "Valley of Flowers",
    "Kalsubai",
    "Hampta Pass",
]


_TRAIL_VARIATIONS: Dict[str, List[str]] = {
    "Kedarkantha": ["kedarkantha", "kedarkanta", "kedar kantha"],
    "Valley of Flowers": ["valley of flowers", "vof", "pushp ghati"],
    "Triund": ["triund", "truind", "mcleod ganj trek"],
    "Kalsubai": ["kalsubai", "kalsu bai", "highest peak maharashtra"],
    "Hampta Pass": ["hampta", "hamta pass", "manali trek"],
}


_MONTHS: Dict[str, str] = {
    "jan": "January",
    "january": "January",
    "feb": "February",
    "february": "February",
    "mar": "March",
    "march": "March",
    "apr": "April",
    "april": "April",
    "may": "May",
    "jun": "June",
    "june": "June",
    "jul": "July",
    "july": "July",
    "aug": "August",
    "august": "August",
    "sep": "September",
    "sept": "September",
    "september": "September",
    "oct": "October",
    "october": "October",
    "nov": "November",
    "november": "November",
    "dec": "December",
    "december": "December",
}


_SEASONS: Dict[str, List[str]] = {
    "winter": ["december", "january", "february"],
    "summer": ["april", "may", "june"],
    "monsoon": ["july", "august", "september"],
    "spring": ["march", "april"],
    "autumn": ["october", "november"],
}


_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "safety": ["safe", "safety", "risk", "hazard", "avalanche", "snow", "conditions"],
    "permits": ["permit", "permits", "permission", "entry pass"],
    "weather": ["weather", "forecast", "rain", "snowfall", "temperature", "wind"],
    "accommodation": ["stay", "accommodation", "hotel", "guesthouse", "camp", "camping"],
    "difficulty": ["difficulty", "hard", "easy", "moderate", "elevation", "gain", "distance"],
}


@dataclass
class SearchEntities:
    trail: Optional[str]
    matched_alias: Optional[str]
    time_period: Optional[str]
    months: List[str]
    intent: str
    sources: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "trail": self.trail,
            "matched_alias": self.matched_alias,
            "time_period": self.time_period,
            "months": self.months,
            "intent": self.intent,
            "sources": self.sources,
        }


class SearchSkill:
    """Extract entities from a user's question and decide which sources to query."""

    def __init__(self) -> None:
        indexed_env = os.getenv("INDEXED_TRAILS", ",".join(_DEFAULT_TRAILS))
        self.indexed_trails: List[str] = [t.strip() for t in indexed_env.split(",") if t.strip()]

        # Build alias → canonical mapping, seeded with known variations
        self.alias_to_canonical: Dict[str, str] = {}
        for canonical, variations in _TRAIL_VARIATIONS.items():
            for v in variations:
                self.alias_to_canonical[v.lower()] = canonical

        # Ensure all env trails are represented (at least alias equals canonical lower())
        for t in self.indexed_trails:
            self.alias_to_canonical.setdefault(t.lower(), t)

        # Precompute list of aliases for fuzzy matching
        self._all_aliases: List[str] = list(self.alias_to_canonical.keys())

        # Precompile patterns
        month_keys = sorted(_MONTHS.keys(), key=len, reverse=True)
        self._month_pattern = re.compile(r"\b(" + "|".join(map(re.escape, month_keys)) + r")\b", re.I)
        season_keys = sorted(_SEASONS.keys(), key=len, reverse=True)
        self._season_pattern = re.compile(r"\b(" + "|".join(map(re.escape, season_keys)) + r")\b", re.I)

    def extract_entities(self, question: str) -> Dict[str, object]:
        canonical_trail, matched_alias = self.fuzzy_match_trail(question)
        # Fallback: try to guess a proper-noun trail name from the question if no alias matched
        if not canonical_trail:
            guessed = self._guess_trail_from_text(question)
            if guessed:
                canonical_trail = guessed
                matched_alias = guessed.lower()
        time_period, months = self._extract_time_period(question)
        intent = self._extract_intent(question)
        entities = SearchEntities(
            trail=canonical_trail,
            matched_alias=matched_alias,
            time_period=time_period,
            months=months,
            intent=intent,
            sources=[],
        )
        entities.sources = self.determine_sources(entities.to_dict())
        return entities.to_dict()

    def fuzzy_match_trail(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Match a trail name even with minor typos.

        Strategy:
        - Direct substring match against known aliases
        - Fuzzy match using difflib.get_close_matches as a fallback
        """
        lower = text.lower()

        # Direct alias substring search (word-boundary aware)
        for alias in self._all_aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                return self.alias_to_canonical[alias], alias

        # Fuzzy matching: try to get a close alias
        tokens = re.findall(r"[a-zA-Z]+", lower)
        candidates: List[str] = []
        for token in tokens:
            matches = get_close_matches(token, self._all_aliases, n=1, cutoff=0.85)
            if matches:
                candidates.append(matches[0])

        if candidates:
            best = candidates[0]
            return self.alias_to_canonical.get(best) or best.title(), best
        return None, None

    def _guess_trail_from_text(self, text: str) -> Optional[str]:
        # Pick the longest span of capitalized words as a naive entity guess
        # e.g., "Tso Moriri", "Roopkund", "Har Ki Dun"
        tokens = re.findall(r"[A-Za-z][a-z]+|[A-Z]{2,}", text)
        spans: List[str] = []
        current: List[str] = []
        for tok in text.split():
            if re.match(r"^[A-Z][a-zA-Z\-]*$", tok):
                current.append(tok)
            else:
                if current:
                    spans.append(" ".join(current))
                    current = []
        if current:
            spans.append(" ".join(current))
        # Filter out generic words/questions
        blacklist = {"Is", "What", "Best", "Tell", "About", "Can", "You", "Safe", "Monsoon"}
        clean_spans = [s for s in spans if all(w not in blacklist for w in s.split())]
        if clean_spans:
            return max(clean_spans, key=lambda s: len(s))

        # Lowercase heuristic: capture phrase before the word 'trek' or 'trail'
        lower = text.lower()
        m = re.search(r"([a-z][a-z\s\-]{2,})\s+(?:trek|trail)", lower)
        if m:
            guess = m.group(1).strip()
            # Remove common lead-ins
            for lead in ["about ", "tell me about ", "can you tell me about "]:
                if guess.startswith(lead):
                    guess = guess[len(lead):]
            return " ".join(w.capitalize() for w in guess.split())
        return None

    def _extract_time_period(self, text: str) -> Tuple[Optional[str], List[str]]:
        months_found: List[str] = []

        for m in self._month_pattern.findall(text):
            norm = _MONTHS.get(m.lower())
            if norm and norm not in months_found:
                months_found.append(norm)

        season_found: Optional[str] = None
        season_match = self._season_pattern.search(text)
        if season_match:
            season_key = season_match.group(1).lower()
            season_found = season_key.capitalize()
            # Expand season to months if not already found
            for sm in _SEASONS[season_key]:
                norm = _MONTHS.get(sm)
                if norm and norm not in months_found:
                    months_found.append(norm)

        if months_found and season_found:
            return f"{season_found} ({', '.join(months_found)})", months_found
        if months_found:
            return ", ".join(months_found), months_found
        if season_found:
            return season_found, months_found
        return None, months_found

    def _extract_intent(self, text: str) -> str:
        lower = text.lower()
        for intent, keywords in _INTENT_KEYWORDS.items():
            if any(k in lower for k in keywords):
                return intent
        return "general"

    def determine_sources(self, entities: Dict[str, object]) -> List[str]:
        """Return which sources to query based on extracted entities.

        - Wikivoyage: general info, permits, accommodation, difficulty
        - Mountain-Forecast: weather/safety/time-season questions
        - OSM Wiki: GPX, trail stats, coordinates
        """
        intent = str(entities.get("intent", "general"))
        trail_present = entities.get("trail") is not None

        sources: List[str] = []

        # Wikivoyage is broadly useful when a trail is identified or when intent is general/permits/accommodation/difficulty
        if trail_present or intent in {"general", "permits", "accommodation", "difficulty"}:
            sources.append("wikivoyage")

        # Weather and safety lean on Mountain-Forecast; also if a time period is mentioned
        time_period = entities.get("time_period")
        if intent in {"weather", "safety"} or (trail_present and time_period):
            sources.append("mountain_forecast")

        # OSM Wiki is useful for GPX and trail stats/difficulty
        if intent in {"difficulty", "safety", "general"} and trail_present:
            sources.append("osm_wiki")

        # Ensure uniqueness and stable order
        seen: set = set()
        ordered = []
        for s in sources:
            if s not in seen:
                ordered.append(s)
                seen.add(s)
        return ordered

