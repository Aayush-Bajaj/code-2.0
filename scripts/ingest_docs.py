"""
scripts/ingest_docs.py — CLI ingestion script.

Loads PDFs and text from data/rag_docs/, chunks about 800 tokens with 100 overlap,
keeps metadata {doc, page, url}, embeds locally with sentence-transformers all-MiniLM-L6-v2,
and stores in ChromaDB at data/chroma/.
"""
import sys
from pathlib import Path

# Ensure root dir is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.rag.indexer import ingest_documents, RAG_DOCS_DIR, CHROMA_DIR


def main():
    print(f"[*] Ingesting regulatory documents from: {RAG_DOCS_DIR}", flush=True)
    print(f"[*] Chroma database location: {CHROMA_DIR}", flush=True)
    count = ingest_documents()
    print(f"[+] Successfully indexed {count} document chunks into ChromaDB at {CHROMA_DIR}", flush=True)



if __name__ == "__main__":
    main()
