"""Embeddings locales con nvidia/Nemotron-3-Embed-1B-BF16, corriendo en GPU.

Mismo patron que RAG-project/rag/embeddings.py (tutorial previo). Este modelo
espera que las consultas y los documentos se distingan con un prefijo
("query: " / "passage: ") -- sin eso el retrieval empeora bastante, segun la
propia ficha del modelo en HuggingFace.
"""

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "nvidia/Nemotron-3-Embed-1B-BF16"


def load_embedder() -> SentenceTransformer:
    """Carga el modelo de embeddings en GPU, en bfloat16."""
    return SentenceTransformer(
        MODEL_NAME,
        device="cuda",
        model_kwargs={"torch_dtype": torch.bfloat16},
    )


def embed_queries(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    """Embebe texto del lado consulta (prefijo query:)."""
    return model.encode([f"query: {t}" for t in texts], normalize_embeddings=True)


def embed_passages(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    """Embebe texto del lado documento/chunk (prefijo passage:)."""
    return model.encode([f"passage: {t}" for t in texts], normalize_embeddings=True)
