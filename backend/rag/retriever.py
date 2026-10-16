"""
backend/rag/retriever.py — Semantic document retriever for regulation passages.

Queries ChromaDB vector collection at data/chroma/ using sentence-transformers.
Returns retrieved chunks with citation strings formatted as '[doc p.X]'.
Provides resilient fallback to direct document reading if vector store is uninitialized.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.rag.indexer import (
    CHROMA_DIR,
    COLLECTION_NAME,
    get_chroma_client,
    get_embedding_model,
    RAG_DOCS_DIR,
    extract_chunks_from_file,
)


@dataclass
class RetrievedChunk:
    text: str
    doc: str
    page: int
    url: str
    citation: str  # e.g. "[sebi_brsr_framework.pdf p.1]"
    distance: float = 0.0


def _fallback_keyword_search(query: str, top_k: int = 3) -> List[RetrievedChunk]:
    """
    Direct document search fallback if ChromaDB is unavailable or empty.
    Scans files in data/rag_docs/ and matches keywords.
    """
    chunks: List[RetrievedChunk] = []
    if not RAG_DOCS_DIR.exists():
        return chunks

    query_words = set(query.lower().split())
    candidates = []

    for f in sorted(RAG_DOCS_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in (".txt", ".pdf"):
            extracted = extract_chunks_from_file(f)
            for item in extracted:
                meta = item["metadata"]
                text = item["text"]
                # simple word overlap score
                score = sum(1 for w in query_words if w in text.lower())
                candidates.append((score, text, meta))

    # Sort descending by word overlap
    candidates.sort(key=lambda x: x[0], reverse=True)
    for score, text, meta in candidates[:top_k]:
        doc_name = meta["doc"]
        page_num = meta["page"]
        citation = f"[{doc_name} p.{page_num}]"
        chunks.append(
            RetrievedChunk(
                text=text,
                doc=doc_name,
                page=page_num,
                url=meta.get("url", ""),
                citation=citation,
                distance=1.0 - (score / max(1, len(query_words))),
            )
        )
    return chunks


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 2,
    persist_dir: Optional[Path] = None,
) -> List[RetrievedChunk]:
    """
    Retrieve top-k relevant regulatory passages from ChromaDB for a given topic.
    Returns list of RetrievedChunk objects containing text and citation '[doc p.X]'.
    """
    p_dir = persist_dir or CHROMA_DIR
    try:
        client = get_chroma_client(p_dir)
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        if count == 0:
            return _fallback_keyword_search(query, top_k=top_k)

        # Query embedding
        model = get_embedding_model()
        query_emb = model.encode([query], convert_to_numpy=True).tolist()

        res = collection.query(
            query_embeddings=query_emb,
            n_results=min(top_k, count),
        )

        results: List[RetrievedChunk] = []
        if res and res.get("documents") and res["documents"][0]:
            docs = res["documents"][0]
            metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
            dists = res["distances"][0] if res.get("distances") else [0.0] * len(docs)

            for text, meta, dist in zip(docs, metas, dists):
                doc_name = meta.get("doc", "regulation_doc")
                page_num = meta.get("page", 1)
                citation = f"[{doc_name} p.{page_num}]"
                results.append(
                    RetrievedChunk(
                        text=text,
                        doc=doc_name,
                        page=page_num,
                        url=meta.get("url", ""),
                        citation=citation,
                        distance=float(dist),
                    )
                )
            if results:
                return results

    except Exception:
        pass

    # Graceful fallback to raw files
    return _fallback_keyword_search(query, top_k=top_k)

