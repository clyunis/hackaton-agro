"""Fase 1 de ingesta: carga los marbetes CASAFE y los persiste como JSONL.

Separado de la indexacion (chunking + embeddings + Chroma, ver scripts/index_marbetes.py)
para poder re-correr el chunking/embedding sin tener que volver a leer los 606 PDFs cada vez.
"""

from rag.loaders import save_documents_jsonl
from rag.marbetes_loader import CORPUS_PATH, load_marbetes


def main():
    docs = load_marbetes(solo_relevante_tandil=True)
    print(f"cargados {len(docs)} marbetes relevantes para la zona de Tandil")
    save_documents_jsonl(docs, CORPUS_PATH)
    print(f"guardado en {CORPUS_PATH}")


if __name__ == "__main__":
    main()
