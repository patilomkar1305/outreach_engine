"""
app/db/vector_store.py
──────────────────────
Thin wrapper around ChromaDB.

Two operations the pipeline uses:
  1.  query_similar_personas(tone_text)  → list of past persona summaries
      called by persona_agent to enrich its prompt with "here is how
      similar people communicate".
  2.  upsert_persona(target_hash, tone_summary, metadata)
      called by the persistence stage after a successful run so the
      next run can benefit.

Embedding model: sentence-transformers/all-MiniLM-L6-v2 (runs fully offline).
"""

from __future__ import annotations
import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model  (loaded once at import time – ~90 MB, fast on CPU)
# ---------------------------------------------------------------------------
_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model: %s", _EMBED_MODEL_NAME)
        _embed_model = SentenceTransformer(_EMBED_MODEL_NAME)
    return _embed_model


# ---------------------------------------------------------------------------
# ChromaDB client  (embedded mode - no server needed)
# ---------------------------------------------------------------------------
_chroma_client: chromadb.PersistentClient | None = None


def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        # Use persistent client (embedded mode) - stores data locally
        _chroma_client = chromadb.PersistentClient(
            path="./chroma_data"  # Local directory for ChromaDB storage
        )
        logger.info(
            "Connected to ChromaDB (embedded mode) at ./chroma_data",
        )
    return _chroma_client


def _get_collection() -> chromadb.Collection:
    """Get (or create) the target collection."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma.collection,
        metadata={"hnsw:space": "cosine"},   # cosine similarity
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query_similar_personas(
    tone_text: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """
    Return the `top_k` most similar past persona tone-summaries.

    Each returned dict has:
        {
            "tone_summary": <str>,          # the text we stored
            "industry":     <str | None>,   # from metadata
            "similarity":   <float>,        # 1 - distance (cosine)
        }
    """
    collection = _get_collection()

    if collection.count() == 0:
        logger.debug("Vector store is empty – returning no similar personas.")
        return []

    embed = _get_embed_model().encode(tone_text).tolist()

    results = collection.query(
        query_embeddings=[embed],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    # ChromaDB returns nested lists (one list per query)
    docs       = results["documents"][0]      if results["documents"]  else []
    metadatas  = results["metadatas"][0]      if results["metadatas"]  else []
    distances  = results["distances"][0]      if results["distances"]  else []

    out: list[dict[str, Any]] = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        out.append({
            "tone_summary": doc,
            "industry":     meta.get("industry"),
            "similarity":   round(1 - dist, 3),   # cosine: sim = 1 - dist
        })
    return out


def upsert_persona(
    target_hash: str,
    tone_summary: str,
    metadata: dict[str, str] | None = None,
) -> None:
    """
    Store (or overwrite) a persona tone-summary so future runs can
    learn from it.

    `metadata`  – small dict of non-PII tags, e.g. {"industry": "SaaS"}
    """
    collection = _get_collection()
    embed = _get_embed_model().encode(tone_summary).tolist()

    collection.upsert(
        ids=[target_hash],                          # idempotent on same target
        embeddings=[embed],
        documents=[tone_summary],
        metadatas=[metadata or {}],
    )
    logger.info("Upserted persona for target_hash=%s", target_hash)


# ---------------------------------------------------------------------------
# Knowledge Base Functions
# ---------------------------------------------------------------------------

def _get_knowledge_collection() -> chromadb.Collection:
    """Get (or create) the knowledge base collection."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=f"{settings.chroma.collection}_knowledge",
        metadata={"hnsw:space": "cosine"},
    )


def add_knowledge_document(
    doc_id: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Add a document to the knowledge base for RAG queries.
    
    Used for:
    - Company information documents
    - Product descriptions
    - Case studies
    - Successful outreach examples
    """
    collection = _get_knowledge_collection()
    embed = _get_embed_model().encode(content).tolist()
    
    collection.upsert(
        ids=[doc_id],
        embeddings=[embed],
        documents=[content],
        metadatas=[metadata or {}],
    )
    logger.info("Added knowledge document: %s", doc_id)


def query_knowledge_base(
    query: str,
    top_k: int = 5,
    filter_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Query the knowledge base for relevant context.
    
    Returns relevant documents that can be used to enrich prompts
    with company-specific information.
    """
    collection = _get_knowledge_collection()
    
    if collection.count() == 0:
        logger.debug("Knowledge base is empty.")
        return []
    
    embed = _get_embed_model().encode(query).tolist()
    
    where_filter = {"type": filter_type} if filter_type else None
    
    results = collection.query(
        query_embeddings=[embed],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
        where=where_filter,
    )
    
    docs = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []
    
    out: list[dict[str, Any]] = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        out.append({
            "content": doc,
            "type": meta.get("type", "unknown"),
            "title": meta.get("title", ""),
            "similarity": round(1 - dist, 3),
        })
    return out


def get_knowledge_stats() -> dict[str, Any]:
    """Get statistics about the knowledge base."""
    try:
        collection = _get_knowledge_collection()
        return {
            "document_count": collection.count(),
            "collection_name": collection.name,
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge stats: {e}")
        return {"document_count": 0, "error": str(e)}
