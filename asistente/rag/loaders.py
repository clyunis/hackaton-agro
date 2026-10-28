"""Persistencia generica de documentos como JSON Lines, por id (upsert)."""

import json
from pathlib import Path


def save_documents_jsonl(docs: list[dict], path: str) -> None:
    """Guarda docs ({"page_content", "metadata"}) en JSONL, upsertando por metadata["id"]."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined: dict[str, dict] = {}
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    doc_dict = json.loads(line)
                    combined[doc_dict["metadata"]["id"]] = doc_dict
    for doc in docs:
        combined[doc["metadata"]["id"]] = doc
    with open(out_path, "w", encoding="utf-8") as f:
        for doc_dict in combined.values():
            f.write(json.dumps(doc_dict, ensure_ascii=False) + "\n")


def load_documents_jsonl(path: str) -> list[dict]:
    """Carga docs previamente guardados con save_documents_jsonl."""
    in_path = Path(path)
    if not in_path.exists():
        return []
    docs = []
    with open(in_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(json.loads(line))
    return docs
