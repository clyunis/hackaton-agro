"""Coleccion Chroma persistente local para los chunks indexados."""

from chromadb import PersistentClient

CHROMA_PATH = "./chroma_db/"
COLLECTION_NAME = "marbetes"


def get_collection(path: str = CHROMA_PATH, name: str = COLLECTION_NAME):
    """Abre (o crea) la coleccion Chroma persistente en disco."""
    client = PersistentClient(path=path)
    return client.get_or_create_collection(
        name,
        embedding_function=None,
        configuration={"space": "cosine", "ef_construction": 200, "max_neighbors": 64},
    )
