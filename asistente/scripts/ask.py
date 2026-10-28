"""Cierra el loop de RAG: retrieval filtrado + prompt con citas + Claude.

Mismo patron que RAG-project/scripts/ask.py (tutorial previo), adaptado a
marbetes: el prompt fuerza a citar producto+archivo por cada afirmacion, a
separar lo que viene del marbete de cualquier interpretacion propia, y a decir
explicitamente que no hay evidencia suficiente en vez de inventar -- es
requisito del desafio, no un nice-to-have.
"""

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from rag.embeddings import load_embedder
from rag.pipeline import query_index

load_dotenv()

# Distancia coseno (0 = identico, 2 = opuesto). Chunks mas lejos que esto de la
# consulta se tratan como ruido y se descartan antes de llegar al prompt.
# TODO: recalibrar con casos reales de marbetes (el 1.4 viene del tutorial con
# otro corpus/otro dataset de prueba; medir aca que distancia separa relevante
# de no relevante antes de confiar en este numero).
DISTANCE_THRESHOLD = 1.4

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """Sos un asistente tecnico para ingenieros agronomos de la zona de Tandil
y partidos vecinos (agricultura extensiva). Respondes preguntas sobre productos
fitosanitarios usando EXCLUSIVAMENTE los marbetes (fragmentos de la Guia CASAFE) que
se te pasan como contexto.

Reglas estrictas:
1. Toda afirmacion tecnica (dosis, cultivo habilitado, restriccion, principio activo)
   tiene que citar el producto y el archivo de origen entre parentesis, ej: (ACETOCLOR,
   0014_acetoclor.pdf).
2. Si agregas una interpretacion propia que no esta literalmente en el marbete (por
   ejemplo, comparar dos productos o sugerir una alternativa), marcala explicitamente
   como "Interpretacion propia:" separada de lo que dice el marbete.
3. Si el contexto no alcanza para responder con confianza, decilo explicitamente
   ("No tengo evidencia suficiente en los marbetes disponibles para responder esto con
   certeza") en vez de inventar una respuesta. No asumas dosis ni restricciones que no
   esten en el contexto.
4. Respondes siempre en espanol rioplatense, de forma concisa y tecnica.
5. No uses formato Markdown (nada de **negrita**, ## encabezados, backticks). El texto se
   muestra tal cual en un chat de Telegram; usa texto plano y guiones "-" para listas."""


def unpack_results(results: dict) -> list[dict]:
    """Aplana el resultado anidado de Chroma en una lista de {content, metadata, distance}."""
    out = []
    for document, metadata, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        out.append({"content": document, "metadata": metadata, "distance": distance})
    return out


def filter_relevant_chunks(chunks: list[dict], threshold: float = DISTANCE_THRESHOLD) -> list[dict]:
    """Descarta chunks cuya distancia coseno a la consulta supera el umbral."""
    return [c for c in chunks if c["distance"] <= threshold]


def build_prompt(query: str, chunks: list[dict]) -> str:
    """Arma el prompt de usuario con los chunks recuperados, citables por producto+archivo."""
    bloques = []
    for chunk in chunks:
        metadata = chunk["metadata"]
        bloques.append(
            f"[Producto: {metadata.get('producto', '?')} | Archivo: {metadata.get('source', '?')}]\n"
            f"{chunk['content']}\n"
        )
    contexto = "\n---\n".join(bloques)
    return f"Pregunta del ingeniero agronomo: {query}\n\nContexto (marbetes recuperados):\n{contexto}"


class AsistenteAgro:
    """Encapsula el pipeline de retrieval + generacion, para reusar entre CLI y bot."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.embedder = load_embedder()
        self.llm = ChatAnthropic(model=model_name)

    def responder(self, pregunta: str, n_results: int = 5) -> dict:
        """Devuelve {"respuesta": str, "fuentes": list[dict]} para una pregunta."""
        raw_results = query_index(pregunta, self.embedder, n_results=n_results)
        chunks = unpack_results(raw_results)
        relevantes = filter_relevant_chunks(chunks)
        if not relevantes:
            return {
                "respuesta": (
                    "No encontre marbetes relevantes para esta consulta. "
                    "No tengo evidencia suficiente para responder con certeza."
                ),
                "fuentes": [],
            }
        prompt = build_prompt(pregunta, relevantes)
        response = self.llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])
        return {"respuesta": response.content, "fuentes": relevantes}


def main():
    asistente = AsistenteAgro()
    print(f"Asistente listo (modelo: {asistente.llm.model}). Ctrl+C o 'exit' para salir.\n")
    try:
        while True:
            pregunta = input("Consulta: ")
            if not pregunta.strip():
                continue
            if pregunta.lower() == "exit":
                break
            resultado = asistente.responder(pregunta)
            print("\nRespuesta:", resultado["respuesta"])
            if resultado["fuentes"]:
                print("\nFuentes:")
                for i, chunk in enumerate(resultado["fuentes"], start=1):
                    m = chunk["metadata"]
                    print(f"  {i}. {m.get('producto')} ({m.get('source')}) - distancia {chunk['distance']:.3f}")
            print()
    except KeyboardInterrupt:
        print("\nChau.")


if __name__ == "__main__":
    main()
