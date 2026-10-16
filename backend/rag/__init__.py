"""
backend/rag — Regulatory document retrieval, factual report generation, and PDF export.

Public API:
  - generate_report: Main pipeline orchestrator (RAG + Facts + LLM + Validator + Fallback)
  - build_report_pdf: ReportLab PDF generator with headers, table, and disclaimer footer
  - ingest_documents: ChromaDB indexing of regulatory PDFs and text
  - retrieve_relevant_chunks: Vector retrieval with citations [doc p.X]
  - validate_report_numbers: Numerical audit checking 100% evidence traceability
"""

from backend.rag.generator import generate_report
from backend.rag.pdf import build_report_pdf, build_report_pdf_bytes
from backend.rag.indexer import ingest_documents
from backend.rag.retriever import retrieve_relevant_chunks
from backend.rag.validator import validate_report_numbers
from backend.rag.facts import build_facts_registry

__all__ = [
    "generate_report",
    "build_report_pdf",
    "build_report_pdf_bytes",
    "ingest_documents",
    "retrieve_relevant_chunks",
    "validate_report_numbers",
    "build_facts_registry",
]
