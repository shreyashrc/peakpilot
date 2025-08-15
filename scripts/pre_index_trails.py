import asyncio
import json
import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

from crawler.indiahikes_crawler import IndiahikesCrawler
from crawler.search_aggregator import SearchAggregator
from rag.vector_store import VectorStore


DEFAULT_TRAILS: List[str] = [
    "Triund",
    "Kedarkantha",
    "Valley of Flowers",
    "Kalsubai",
    "Hampta Pass",
]


TRAIL_DATA: Dict[str, Dict[str, Any]] = {
    "Triund": {
        "best_months": ["March", "April", "May", "September", "October"],
        "permits": "No special permits; check local forest rules.",
        "difficulty": "Moderate",
        "base_camp": "McLeod Ganj / Dharamkot",
        "highlights": ["Dhauladhar views", "Sunset point", "Campable meadows"],
    },
    "Kedarkantha": {
        "best_months": ["December", "January", "February", "March"],
        "permits": "Entry permit required from Forest Department",
        "difficulty": "Easy-Moderate",
        "base_camp": "Sankri village",
        "highlights": ["360° Himalayan views", "Snow trekking", "Pine forests"],
    },
    "Valley of Flowers": {
        "best_months": ["July", "August", "September"],
        "permits": "Daily entry permit at Govindghat/Ghangaria",
        "difficulty": "Moderate",
        "base_camp": "Ghangaria",
        "highlights": ["UNESCO World Heritage Site", "Alpine flora", "Photogenic valley"],
    },
    "Kalsubai": {
        "best_months": ["October", "November", "December", "January", "February", "March"],
        "permits": "No permits required",
        "difficulty": "Moderate",
        "base_camp": "Bari village",
        "highlights": ["Highest peak in Maharashtra", "Iron ladders", "Temple at summit"],
    },
    "Hampta Pass": {
        "best_months": ["June", "July", "August", "September"],
        "permits": "Forest permits via trek operator/local office",
        "difficulty": "Moderate-Difficult",
        "base_camp": "Jobra / Manali",
        "highlights": ["Crossover to Lahaul", "Rani Nallah", "Chandratal (detour)"],
    },
}


def _structured_doc_text(trail: str, data: Dict[str, Any]) -> str:
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    return f"Structured trail data for {trail}:\n{pretty}"


async def preindex_trail(trail: str, vs: VectorStore, ih: IndiahikesCrawler, web: SearchAggregator) -> int:
    texts: List[str] = []
    metas: List[Dict[str, Any]] = []

    # Prefer Indiahikes content
    try:
        ih_docs = await ih.fetch(trail)
        for d in ih_docs:
            texts.append(d.get("text", ""))
            metas.append({
                "source": d.get("source", "indiahikes"),
                "trail_name": trail,
                "section_type": d.get("section_type", "webpage"),
                "url": d.get("url", ""),
                "pre_indexed": True,
            })
    except Exception as exc:  # noqa: BLE001
        logging.warning("Preindex Indiahikes failed for %s: %s", trail, exc)

    # Add a couple of web sources for variety
    if len(texts) < 2:
        try:
            web_docs = await web.search(trail, intent="general")
            for d in web_docs[: 2]:
                texts.append(d.get("text", ""))
                metas.append({
                    "source": d.get("source", "web"),
                    "trail_name": trail,
                    "section_type": d.get("section_type", "webpage"),
                    "url": d.get("url", ""),
                    "pre_indexed": True,
                })
        except Exception as exc:  # noqa: BLE001
            logging.warning("Preindex web search failed for %s: %s", trail, exc)

    # Add structured data doc if available
    if trail in TRAIL_DATA:
        texts.append(_structured_doc_text(trail, TRAIL_DATA[trail]))
        metas.append({
            "source": "preindex",
            "trail_name": trail,
            "section_type": "structured",
            "url": "",
            "pre_indexed": True,
        })

    if not texts:
        return 0

    ids = vs.add_documents(texts, metas)
    return len(ids)


async def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    trails_env = os.getenv("INDEXED_TRAILS")
    trails = [t.strip() for t in trails_env.split(",")] if trails_env else DEFAULT_TRAILS

    vs = VectorStore()
    ih = IndiahikesCrawler(max_results=3)
    web = SearchAggregator(max_results=5)

    total = 0
    for trail in trails:
        logging.info("Pre-indexing: %s", trail)
        count = await preindex_trail(trail, vs, ih, web)
        logging.info("Indexed %d docs for %s", count, trail)
        total += count

    logging.info("Pre-indexing completed. Total documents: %d", total)


if __name__ == "__main__":
    asyncio.run(main())

