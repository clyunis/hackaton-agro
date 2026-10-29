"""Convierte evaluacion/uso_tokens.jsonl en un resumen de costo en USD por consulta.

Usa los precios publicados de Claude Sonnet 5 (input/output/cache) para traducir las filas
de medir_tokens.py en dolares reales. Pensado para alimentar el canvas de modelo de negocio
(estructura de costos por consulta) con numeros de costo, no solo de tokens.

Uso (desde asistente/): uv run python scripts/resumen_gastos.py
"""

import json
import statistics
from pathlib import Path

RUTA_ENTRADA = Path(__file__).resolve().parent.parent / "evaluacion" / "uso_tokens.jsonl"
RUTA_SALIDA = Path(__file__).resolve().parent.parent / "reportes" / "resumen_gastos.md"

# USD por millon de tokens, precios de Claude Sonnet 5 (platform.claude.com/docs/about-claude/pricing).
PRECIO_INPUT_POR_MTOK = 2.0
PRECIO_OUTPUT_POR_MTOK = 10.0
PRECIO_CACHE_ESCRITURA_POR_MTOK = 2.5  # cache write de 5 minutos (default del SDK)
PRECIO_CACHE_LECTURA_POR_MTOK = 0.20


def cargar_filas(ruta: Path = RUTA_ENTRADA) -> list[dict]:
    """Lee el JSONL de uso_tokens y devuelve la lista de filas (una por turno medido)."""
    filas = []
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if linea:
                filas.append(json.loads(linea))
    return filas


def costo_de_fila(fila: dict) -> float:
    """Costo en USD de un turno, sumando input + output + cache write + cache read."""
    costo = 0.0
    costo += fila.get("input_tokens", 0) / 1_000_000 * PRECIO_INPUT_POR_MTOK
    costo += fila.get("output_tokens", 0) / 1_000_000 * PRECIO_OUTPUT_POR_MTOK
    costo += fila.get("cache_creation_input_tokens", 0) / 1_000_000 * PRECIO_CACHE_ESCRITURA_POR_MTOK
    costo += fila.get("cache_read_input_tokens", 0) / 1_000_000 * PRECIO_CACHE_LECTURA_POR_MTOK
    return costo


def agrupar_por_caso(filas: list[dict]) -> dict[str, list[float]]:
    """Costo de cada turno agrupado por nombre de caso de benchmark."""
    costos_por_caso: dict[str, list[float]] = {}
    for fila in filas:
        costos_por_caso.setdefault(fila["caso"], []).append(costo_de_fila(fila))
    return costos_por_caso


def generar_reporte(filas: list[dict]) -> str:
    """Arma el reporte en markdown: costo total, por turno y por caso."""
    costos = [costo_de_fila(fila) for fila in filas]
    costos_por_caso = agrupar_por_caso(filas)

    lineas = ["# Resumen de gastos AGRIA (Claude Sonnet 5)", ""]
    lineas.append(f"Turnos medidos: {len(filas)}")
    lineas.append(f"Costo total de la corrida: USD {sum(costos):.4f}")
    lineas.append(f"Costo promedio por turno: USD {statistics.mean(costos):.4f}")
    lineas.append(f"Costo mediana por turno: USD {statistics.median(costos):.4f}")
    lineas.append(f"Costo min/max por turno: USD {min(costos):.4f} / USD {max(costos):.4f}")
    lineas.append("")
    lineas.append("## Costo por caso (suma de sus turnos)")
    lineas.append("")
    lineas.append("| Caso | Turnos | Costo total USD | Costo promedio USD/turno |")
    lineas.append("|---|---|---|---|")
    for caso, lista_costos in sorted(costos_por_caso.items(), key=lambda item: -sum(item[1])):
        lineas.append(
            f"| {caso} | {len(lista_costos)} | {sum(lista_costos):.4f} | {statistics.mean(lista_costos):.4f} |"
        )
    lineas.append("")
    lineas.append("## Proyeccion simple")
    lineas.append("")
    costo_promedio = statistics.mean(costos)
    for consultas in (100, 1000, 10000):
        lineas.append(f"- {consultas} consultas: USD {costo_promedio * consultas:.2f}")
    lineas.append("")
    lineas.append(
        "Precios usados (USD/MTok): input {:.2f}, output {:.2f}, cache write {:.2f}, cache read {:.2f}.".format(
            PRECIO_INPUT_POR_MTOK,
            PRECIO_OUTPUT_POR_MTOK,
            PRECIO_CACHE_ESCRITURA_POR_MTOK,
            PRECIO_CACHE_LECTURA_POR_MTOK,
        )
    )
    return "\n".join(lineas) + "\n"


def main():
    """Carga uso_tokens.jsonl, genera el reporte y lo guarda + imprime."""
    filas = cargar_filas()
    reporte = generar_reporte(filas)
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    RUTA_SALIDA.write_text(reporte, encoding="utf-8")
    print(reporte)
    print(f"Reporte guardado en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
