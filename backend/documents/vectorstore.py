"""ChromaDB persistence for document chunks.

Collection uses cosine distance (hnsw:space=cosine).
With cosine distance, Chroma returns distance = 1 - cosine_similarity,
range [0, 2]; lower means more similar. We do not apply a threshold —
the LLM decides relevance from the retrieved context.
"""

from __future__ import annotations

from pathlib import Path

import chromadb

from backend.config import settings

COLLECTION_NAME = "retail_documents"

_client: chromadb.PersistentClient | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=settings.chroma_path)
    return _client


def _get_collection() -> chromadb.Collection:
    return _get_client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def ingest_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
    document_id: int,
) -> None:
    """Store chunks and their embeddings in ChromaDB.

    Each chunk dict must have: text, page, source, chunk_idx.
    IDs are scoped to document_id so re-ingesting a new version of
    a file does not collide with other documents.
    """
    collection = _get_collection()
    ids = [
        f"doc{document_id}_p{c['page']}_c{c['chunk_idx']}" for c in chunks
    ]
    metadatas = [
        {
            "source": c["source"],
            "page": c["page"],
            "chunk_idx": c["chunk_idx"],
            "document_id": document_id,
        }
        for c in chunks
    ]
    texts = [c["text"] for c in chunks]
    collection.add(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)


def query(question_embedding: list[float], top_k: int) -> list[dict]:
    """Return top_k chunks closest to question_embedding.

    Each result dict has: text, source, page, chunk_idx, document_id, distance.
    Returns an empty list if the collection has no documents.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=min(top_k, collection.count()),
    )
    output = []
    for text, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append(
            {
                "text": text,
                "source": meta["source"],
                "page": meta["page"],
                "chunk_idx": meta["chunk_idx"],
                "document_id": meta["document_id"],
                "distance": distance,
            }
        )
    return output
