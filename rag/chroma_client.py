from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings


def get_client() -> chromadb.Client:
    # Try external server, else default in-process
    try:
        return chromadb.HttpClient(host="chromadb", port=8000, settings=Settings(allow_reset=True))
    except Exception:  # noqa: BLE001
        return chromadb.Client(Settings(anonymized_telemetry=False, allow_reset=True))


def upsert_documents(collection_name: str, docs: List[Dict[str, Any]]) -> None:
    client = get_client()
    collection = client.get_or_create_collection(collection_name)
    ids = [d.get("id") or str(i) for i, d in enumerate(docs)]
    texts = [d.get("text", "") for d in docs]
    metadatas = [d for d in docs]
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas)


def query_similar(collection_name: str, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
    client = get_client()
    collection = client.get_or_create_collection(collection_name)
    return collection.query(query_texts=query_texts, n_results=n_results)
