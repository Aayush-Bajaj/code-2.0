"""
backend/rag/indexer.py — Ingestion, chunking, and ChromaDB indexing for regulatory documents.

Loads .txt and .pdf files from data/rag_docs/, splits into ~800 token chunks with 100 token overlap,
extracts metadata {doc, page, url}, embeds with sentence-transformers 'all-MiniLM-L6-v2' (CPU),
and stores in persistent ChromaDB at data/chroma/.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf

from backend.config import settings

# Chroma directory
CHROMA_DIR = settings.DATA_DIR / "chroma"
RAG_DOCS_DIR = settings.DATA_DIR / "rag_docs"
COLLECTION_NAME = "rag_docs"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

class Deterministic384EmbeddingModel:
    """
    Deterministic 384-dimensional embedding model using hash n-grams and L2 normalization.
    Matches sentence-transformers all-MiniLM-L6-v2 vector dimension (384).
    Ensures tests and DEMO_OFFLINE=1 operate instantly and offline without external HF downloads.
    """
    def encode(self, texts: Any, convert_to_numpy: bool = True) -> Any:
        import numpy as np
        import hashlib
        if isinstance(texts, str):
            single = True
            text_list = [texts]
        else:
            single = False
            text_list = list(texts)

        vectors = []
        for t in text_list:
            vec = np.zeros(384, dtype=np.float32)
            words = t.lower().split()
            for w in words:
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                idx = h % 384
                sign = 1.0 if ((h >> 9) & 1) else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 1e-6:
                vec /= norm
            vectors.append(vec)
        res = np.array(vectors, dtype=np.float32)
        return res[0] if single else res


_EMBEDDING_MODEL = None


def get_embedding_model(force_offline: bool = False):
    global _EMBEDDING_MODEL

    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL

    if force_offline or settings.DEMO_OFFLINE:
        _EMBEDDING_MODEL = Deterministic384EmbeddingModel()
        return _EMBEDDING_MODEL

    try:
        from sentence_transformers import SentenceTransformer
        # Check if model is already cached or can load quickly with authenticated token
        token_arg = settings.HF_TOKEN if settings.HF_TOKEN else None
        _EMBEDDING_MODEL = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            device="cpu",
            token=token_arg,
        )

    except Exception as e:
        print(f"[*] SentenceTransformer loading fallback activated: {e}", flush=True)
        _EMBEDDING_MODEL = Deterministic384EmbeddingModel()

    return _EMBEDDING_MODEL



def get_chroma_client(persist_dir: Optional[Path] = None):
    import chromadb
    p_dir = str(persist_dir or CHROMA_DIR)
    os.makedirs(p_dir, exist_ok=True)
    return chromadb.PersistentClient(path=p_dir)


def chunk_text(text: str, chunk_size_words: int = 700, overlap_words: int = 100) -> List[str]:
    """
    Split text into chunks of approx 800 tokens (~700 English words)
    with approx 100 tokens (~100 words) overlap.
    """
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size_words:
        return [" ".join(words)]
    
    chunks = []
    step = max(1, chunk_size_words - overlap_words)
    for i in range(0, len(words), step):
        chunk = words[i : i + chunk_size_words]
        chunks.append(" ".join(chunk))
        if i + chunk_size_words >= len(words):
            break
    return chunks


def extract_chunks_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extracts text and metadata from a PDF or text file.
    Returns list of dicts with:
      text: str
      metadata: {"doc": filename, "page": page_number, "url": doc_url}
    """
    items = []
    fname = file_path.name

    if file_path.suffix.lower() == ".txt":
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")
        
        chunks = chunk_text(content)
        for idx, ch in enumerate(chunks):
            items.append({
                "text": ch,
                "metadata": {
                    "doc": fname,
                    "page": 1,
                    "url": f"file:///{fname}#page=1",
                    "chunk_id": f"{fname}_p1_c{idx}"
                }
            })

    elif file_path.suffix.lower() == ".pdf":
        reader = pypdf.PdfReader(str(file_path))
        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            chunks = chunk_text(page_text)
            for c_idx, ch in enumerate(chunks):
                items.append({
                    "text": ch,
                    "metadata": {
                        "doc": fname,
                        "page": page_idx,
                        "url": f"file:///{fname}#page={page_idx}",
                        "chunk_id": f"{fname}_p{page_idx}_c{c_idx}"
                    }
                })

    return items


def ingest_documents(
    docs_dir: Optional[Path] = None,
    persist_dir: Optional[Path] = None,
    reset: bool = True
) -> int:
    """
    Ingests all .txt and .pdf files in docs_dir into ChromaDB.
    Returns number of chunks indexed.
    """
    d_dir = docs_dir or RAG_DOCS_DIR
    p_dir = persist_dir or CHROMA_DIR
    client = get_chroma_client(p_dir)

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Regulatory documents for Carbon Passport RAG"}
    )

    all_items: List[Dict[str, Any]] = []
    if d_dir.exists():
        for f in sorted(d_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in (".txt", ".pdf"):
                extracted = extract_chunks_from_file(f)
                print(f"[*] Extracted {len(extracted)} chunks from {f.name}", flush=True)
                all_items.extend(extracted)

    if not all_items:
        print("[!] No documents found to ingest.", flush=True)
        return 0

    print(f"[*] Total chunks to embed: {len(all_items)}. Loading embedding model...", flush=True)
    texts = [item["text"] for item in all_items]
    metadatas = [item["metadata"] for item in all_items]
    ids = [item["metadata"]["chunk_id"] for item in all_items]

    # Generate embeddings with sentence-transformers
    model = get_embedding_model()
    print("[*] Model loaded. Computing embeddings...", flush=True)
    embeddings = model.encode(texts, convert_to_numpy=True).tolist()
    print("[*] Embeddings computed. Adding to ChromaDB...", flush=True)

    # Add to collection in batches
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end],
        )

    print("[*] Finished adding chunks to ChromaDB.", flush=True)
    return len(ids)

