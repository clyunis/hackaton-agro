"""Fase 2 de ingesta: chunkea, embebe y sube el corpus persistido a Chroma.

Requiere haber corrido scripts/ingest_marbetes.py antes (lee data/marbetes_corpus.jsonl).
"""

from rag.loaders import load_documents_jsonl
from rag.marbetes_loader import CORPUS_PATH
from rag.pipeline import build_index


def main():
    docs = load_documents_jsonl(CORPUS_PATH)
    if not docs:
        raise SystemExit(f"No hay documentos en {CORPUS_PATH}. Corre scripts/ingest_marbetes.py primero.")
    build_index(docs)


if __name__ == "__main__":
    main()
