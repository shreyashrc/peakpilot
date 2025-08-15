import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from llm.gemini import embed_texts


class VectorStore:
    """Simple ChromaDB wrapper for session-scoped storage.

    - Uses persistent storage at ./chroma_db by default
    - Creates/gets collection named "hiking_assistant_session"
    - Cosine similarity via HNSW space
    - Stores and searches with explicit embeddings (Gemini-based)
    """

    def __init__(self, persist_directory: Optional[str] = None, collection_name: str = "hiking_assistant_session") -> None:
        self.persist_directory = persist_directory or os.path.join(os.getcwd(), "chroma_db")
        os.makedirs(self.persist_directory, exist_ok=True)
        self.collection_name = collection_name
        self._client: Optional[chromadb.Client] = None
        self._collection = None

    def _get_client(self) -> chromadb.Client:
        if self._client is None:
            # Use PersistentClient to avoid shared-system conflicts across different settings
            try:
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(anonymized_telemetry=False, allow_reset=True),
                )
            except Exception:
                # Fallback to in-memory client if persistent init fails
                self._client = chromadb.Client(
                    Settings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                    )
                )
        return self._client

    def get_or_create_collection(self):
        if self._collection is None:
            client = self._get_client()
            # Use cosine distance space
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def clear_session(self) -> None:
        client = self._get_client()
        # Robust clear: drop if exists, then re-create lazily on next get
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = None

    def _hash_id(self, text: str, metadata: Dict[str, Any]) -> str:
        payload = {"text": text, "metadata": metadata}
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> List[str]:
        if len(texts) != len(metadatas):
            raise ValueError("texts and metadatas must have the same length")
        collection = self.get_or_create_collection()

        unique_texts: List[str] = []
        unique_metas: List[Dict[str, Any]] = []
        unique_ids: List[str] = []
        seen_ids: Dict[str, int] = {}
        seen_payloads: set = set()

        for t, m in zip(texts, metadatas):
            base_id = self._hash_id(t, m)
            payload_key = base_id
            if payload_key in seen_payloads:
                continue
            seen_payloads.add(payload_key)

            if base_id in seen_ids:
                seen_ids[base_id] += 1
                uid = f"{base_id}-{seen_ids[base_id]}"
            else:
                seen_ids[base_id] = 0
                uid = base_id

            unique_ids.append(uid)
            unique_texts.append(t)
            unique_metas.append(m)

        # Generate embeddings via Gemini; will fallback to zero-vectors if no API key set
        embeddings = embed_texts(unique_texts)
        if not embeddings or len(embeddings) != len(unique_texts):
            embeddings = [[0.0] * 10 for _ in unique_texts]

        if unique_texts:
            collection.upsert(ids=unique_ids, documents=unique_texts, metadatas=unique_metas, embeddings=embeddings)
        return unique_ids

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        collection = self.get_or_create_collection()
        query_embeds = embed_texts([query])
        if not query_embeds or len(query_embeds[0]) == 0:
            query_embeds = [[0.0] * 10]
        query_embedding = query_embeds[0]
        # Limit to this session's collection only; results are just from newly upserted docs
        res = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "distances", "metadatas"],
        )
        # Chroma returns lists per query; we query once
        docs = res.get("documents", [[]])[0]
        dists = res.get("distances", [[]])[0]
        metas = res.get("metadatas", [[]])[0]

        results: List[Dict[str, Any]] = []
        for doc, dist, meta in zip(docs, dists, metas):
            # cosine distance: similarity ~= 1 - distance
            try:
                score = max(0.0, min(1.0, 1.0 - float(dist)))
            except Exception:
                score = 0.0
            results.append({
                "text": doc,
                "metadata": meta,
                "score": score,
                "distance": dist,
            })
        return results

