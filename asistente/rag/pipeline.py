"""Ingesta: parte el corpus de marbetes en chunks, los embebe y los sube a Chroma.

Chunking v1 (deliberadamente simple, ver CLAUDE.md de este subproyecto para el
por que): RecursiveCharacterTextSplitter generico, pero a cada chunk se le
antepone un encabezado fijo (producto + marca comercial + uso + cultivos) para
que, aun si el splitter corta una tabla de dosis a la mitad, el chunk resultante
siga sabiendo de que producto se trataba. Mejorar esto a chunking por secciones
del marbete (Informacion General / Restricciones de uso / etc.) es la mejora de
v2 prevista desde el arranque; reemplaza solo esta funcion, no el resto del
pipeline (embeddings/store/generacion no cambian).
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.embeddings import embed_passages, embed_queries, load_embedder
from rag.store import get_collection

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300


def _build_header(metadata: dict) -> str:
    """Encabezado fijo que se repite en cada chunk de un mismo marbete."""
    cultivos = ", ".join(metadata.get("cultivos", [])) or "no especificados"
    marcas = metadata.get("marcas_comerciales") or "no especificadas"
    return (
        f"Producto: {metadata['producto']}\n"
        f"Marcas comerciales: {marcas}\n"
        f"Uso: {metadata.get('uso', 'no especificado')}\n"
        f"Cultivos mencionados: {cultivos}\n"
        f"---\n"
    )


def chunk_documents(docs: list[dict]) -> list[dict]:
    """Parte cada doc {"page_content", "metadata"} en chunks con header inyectado."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = []
    for doc in docs:
        header = _build_header(doc["metadata"])
        parts = splitter.split_text(doc["page_content"])
        for i, part in enumerate(parts):
            chunk_metadata = dict(doc["metadata"])
            chunk_metadata["id"] = f"{doc['metadata']['id']}_chunk_{i}"
            chunk_metadata["cultivos"] = ", ".join(doc["metadata"].get("cultivos", []))
            chunks.append({"page_content": header + part, "metadata": chunk_metadata})
    return chunks


def build_index(docs: list[dict], collection_name: str = "marbetes") -> None:
    """Chunkea, embebe y sube todo el corpus a la coleccion Chroma indicada."""
    chunks = chunk_documents(docs)
    print(f"{len(docs)} marbetes -> {len(chunks)} chunks")
    model = load_embedder()
    texts = [c["page_content"] for c in chunks]
    ids = [c["metadata"]["id"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    embeddings = embed_passages(model, texts)
    collection = get_collection(name=collection_name)
    batch = 200
    for start in range(0, len(chunks), batch):
        end = start + batch
        collection.upsert(
            documents=texts[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end],
        )
    print(f"indexados {len(chunks)} chunks en la coleccion '{collection_name}'")


def query_index(query: str, model, n_results: int = 5, collection_name: str = "marbetes"):
    """Embebe la consulta y busca los n_results chunks mas cercanos."""
    collection = get_collection(name=collection_name)
    query_embedding = embed_queries(model, [query])
    return collection.query(query_embeddings=query_embedding, n_results=n_results)
