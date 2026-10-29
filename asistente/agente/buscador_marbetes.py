"""Adaptador entre la tool buscar_marbetes y el indice Chroma existente (rag/).

Separado del orquestador para que los tests no carguen torch ni el modelo de embeddings.
"""

import threading

from rag.embeddings import load_embedder
from rag.pipeline import query_index
from scripts.ask import filter_relevant_chunks, unpack_results

CANTIDAD_RESULTADOS = 6


class BuscadorMarbetes:
    """Busqueda semantica sobre los marbetes indexados, con el embedder cargado una sola vez."""

    def __init__(self, cantidad_resultados: int = CANTIDAD_RESULTADOS):
        self.embedder = load_embedder()
        self.cantidad_resultados = cantidad_resultados
        # El bot atiende varios chats en threads; el embedder en GPU se usa de a uno.
        self.candado = threading.Lock()

    def buscar(self, consulta: str) -> list[dict]:
        """Devuelve fragmentos {id, producto, archivo, contenido, distancia} bajo el umbral de distancia."""
        with self.candado:
            resultados_crudos = query_index(consulta, self.embedder, n_results=self.cantidad_resultados)
        fragmentos = filter_relevant_chunks(unpack_results(resultados_crudos))
        return [
            {
                "id": fragmento["metadata"].get("id", ""),
                "producto": fragmento["metadata"].get("producto", "?"),
                "archivo": fragmento["metadata"].get("source", "?"),
                "contenido": fragmento["content"],
                "distancia": fragmento["distance"],
            }
            for fragmento in fragmentos
        ]
