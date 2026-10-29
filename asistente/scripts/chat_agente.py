"""CLI del orquestador agentico: misma logica que el bot, mostrando la traza de tools.

Pensado para probar las preguntas del tutor y para la demo (se ve que AGRIA analiza la
consulta, que datos le faltan y que tools usa antes de responder). 'nueva' reinicia la
conversacion, 'exit' sale.
"""

import anthropic
from dotenv import load_dotenv

load_dotenv()

from agente.buscador_marbetes import BuscadorMarbetes  # despues de load_dotenv: lee CLAUDE_MODEL_AGENTE
from agente.orquestador import ConversacionAgro, OrquestadorAgro


def imprimir_resultado(resultado) -> None:
    """Muestra traza de tools, datos faltantes, respuesta y fuentes citadas."""
    for herramienta in resultado.herramientas_usadas:
        print(f"  > tool {herramienta['nombre']}: {herramienta['entrada']}")
    if resultado.datos_faltantes:
        print("  > faltan: " + ", ".join(faltante["clave"] for faltante in resultado.datos_faltantes))
    print("\nAGRIA:", resultado.texto)
    if resultado.fuentes:
        print("\nFuentes:")
        for fuente in resultado.fuentes_citadas():
            print(f"  [{fuente['etiqueta']}] {fuente['producto']} ({fuente['archivo']}): {fuente['extracto']}...")
    print()


def main():
    """Loop de consola sobre una ConversacionAgro."""
    orquestador = OrquestadorAgro(anthropic.Anthropic(), BuscadorMarbetes())
    conversacion = ConversacionAgro(orquestador)
    print(f"AGRIA lista (modelo: {orquestador.modelo}). 'nueva' reinicia, 'exit' sale.\n")
    try:
        while True:
            pregunta = input("Consulta: ").strip()
            if not pregunta:
                continue
            if pregunta.lower() == "exit":
                break
            if pregunta.lower() == "nueva":
                conversacion.reiniciar()
                print("(conversacion reiniciada)\n")
                continue
            imprimir_resultado(conversacion.consultar(pregunta))
    except KeyboardInterrupt:
        print("\nChau.")


if __name__ == "__main__":
    main()
