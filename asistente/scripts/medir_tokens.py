"""Mide el uso de tokens de AGRIA en un set de consultas representativas.

Corre cada caso de BENCHMARK_CASOS contra el orquestador real (API de Anthropic, busqueda
de marbetes en GPU, clima real via Open-Meteo) y registra el 'uso_tokens' de cada turno en
un JSONL para trazabilidad. Al final imprime estadisticas (promedio/mediana/min/max) pensadas
para el canvas de modelo de negocio (estructura de costos). Pensado para corner una vez y
auditar los resultados despues, no para correr en CI: hace llamadas reales con costo real.

Uso (desde asistente/): uv run python scripts/medir_tokens.py
"""

import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

from agente.buscador_marbetes import BuscadorMarbetes  # despues de load_dotenv
from agente.clima import ClienteClima, ClienteClimatologiaHistorica
from agente.orquestador import ConversacionAgro, OrquestadorAgro

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RUTA_RESULTADOS = Path(__file__).resolve().parent.parent / "evaluacion" / "uso_tokens.jsonl"
CAMPOS_NUMERICOS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "llamadas_api",
    "tiempo_s",
)

# Cada caso es una conversacion de uno o mas turnos (para medir tanto una respuesta completa
# en un solo mensaje como el patron pregunta -> repregunta -> respuesta con datos del lote).
BENCHMARK_CASOS = [
    {
        "nombre": "dosis_glifosato_completa",
        "turnos": ["Tengo rama negra en roseta en un lote de soja en barbecho en Tandil, con glifosato 62% PC, ¿que dosis aplico?"],
    },
    {
        "nombre": "dosis_glifosato_incompleta",
        "turnos": [
            "Dame la dosis de glifosato para soja",
            "Es para rama negra en roseta, glifosato 48% SL, lote en Tandil",
        ],
    },
    {
        "nombre": "verificacion_regulatoria_prohibido",
        "turnos": ["¿Puedo usar clorpirifos en mi lote de maiz?"],
    },
    {
        "nombre": "verificacion_regulatoria_parcial",
        "turnos": ["¿Esta permitido el 2,4-D? Lo quiero aplicar en un lote de trigo"],
    },
    {
        "nombre": "calculo_aporte_nutriente",
        "turnos": ["Aplique 200 kg/ha de urea, ¿cuanto N le aporte al lote?"],
    },
    {
        "nombre": "calculo_dosis_fertilizante",
        "turnos": ["Necesito aportar 90 kg/ha de N en un lote de maiz, ¿cuantos kg/ha de urea (46%) tengo que tirar?"],
    },
    {
        "nombre": "riesgo_heladas_pronostico",
        "turnos": ["¿Hay riesgo de helada para los proximos dias en Tandil?"],
    },
    {
        "nombre": "condiciones_aplicacion_otro_partido",
        "turnos": ["Quiero fumigar hoy en Rauch, ¿estan dadas las condiciones de viento y lluvia?"],
    },
    {
        "nombre": "climatologia_historica",
        "turnos": ["¿Como vienen siendo las heladas de mayo en los ultimos 10 anios en Tandil?"],
    },
    {
        "nombre": "busqueda_maleza_sin_producto",
        "turnos": ["Necesito controlar yuyo colorado en un lote de maiz, ¿que principios activos puedo usar?"],
    },
    {
        "nombre": "fuera_de_cobertura_normativa_local",
        "turnos": ["¿Que dice la ordenanza de Tandil sobre aplicaciones cerca de zonas pobladas?"],
    },
    {
        "nombre": "comparacion_hibridos",
        "turnos": ["¿Que diferencia hay entre usar glifosato solo o mezclado con 2,4-D para un barbecho largo?"],
    },
]


@dataclass
class RegistroUso:
    """Una fila medida: un turno real de un caso del benchmark."""

    caso: str
    turno_indice: int
    pregunta: str
    completo: bool
    herramientas_usadas: list
    tiempo_s: float
    uso_tokens: dict = field(default_factory=dict)

    def como_fila(self) -> dict:
        """Dict plano para loguear a JSONL y para las estadisticas agregadas."""
        fila = {
            "caso": self.caso,
            "turno_indice": self.turno_indice,
            "pregunta": self.pregunta,
            "completo": self.completo,
            "herramientas_usadas": self.herramientas_usadas,
            "tiempo_s": round(self.tiempo_s, 2),
        }
        fila.update(self.uso_tokens)
        fila["total_tokens"] = fila["input_tokens"] + fila["output_tokens"]
        return fila


class BenchmarkTokens:
    """Corre el set de casos contra un OrquestadorAgro real y junta las filas medidas."""

    def __init__(self, orquestador: OrquestadorAgro):
        self.orquestador = orquestador
        self.filas: list[dict] = []

    def correr(self, casos: list[dict]) -> list[dict]:
        """Corre todos los casos (cada uno en su propia conversacion) y devuelve las filas."""
        for caso in casos:
            self._correr_caso(caso)
        return self.filas

    def _correr_caso(self, caso: dict) -> None:
        """Corre los turnos de un caso en una conversacion nueva, logueando cada turno."""
        conversacion = ConversacionAgro(self.orquestador)
        for indice, pregunta in enumerate(caso["turnos"]):
            print(f"-> {caso['nombre']} (turno {indice + 1}/{len(caso['turnos'])}): {pregunta[:70]}...")
            inicio = time.monotonic()
            resultado = conversacion.consultar(pregunta)
            tiempo_s = time.monotonic() - inicio
            registro = RegistroUso(
                caso=caso["nombre"],
                turno_indice=indice,
                pregunta=pregunta,
                completo=resultado.completo,
                herramientas_usadas=[h["nombre"] for h in resultado.herramientas_usadas],
                tiempo_s=tiempo_s,
                uso_tokens=resultado.uso_tokens,
            )
            self.filas.append(registro.como_fila())
            print(f"   {resultado.uso_tokens}, {tiempo_s:.1f}s")


def guardar_filas(filas: list[dict], ruta: Path = RUTA_RESULTADOS) -> None:
    """Agrega las filas al JSONL de resultados (no pisa corridas anteriores)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as archivo:
        for fila in filas:
            archivo.write(json.dumps(fila, ensure_ascii=False) + "\n")


def imprimir_estadisticas(filas: list[dict]) -> None:
    """Promedio/mediana/min/max por campo numerico, mas el total general de la corrida."""
    print(f"\n=== Estadisticas sobre {len(filas)} turnos ===")
    for campo in CAMPOS_NUMERICOS:
        valores = [fila[campo] for fila in filas]
        print(
            f"{campo:32s} promedio={statistics.mean(valores):8.1f}  mediana={statistics.median(valores):8.1f}"
            f"  min={min(valores):7.1f}  max={max(valores):8.1f}"
        )
    print(f"\nTotal input_tokens de la corrida:  {sum(f['input_tokens'] for f in filas)}")
    print(f"Total output_tokens de la corrida: {sum(f['output_tokens'] for f in filas)}")
    print(f"Total cache_read_input_tokens:     {sum(f['cache_read_input_tokens'] for f in filas)}")
    print(f"Turnos incompletos (refusal/cortado): {sum(1 for f in filas if not f['completo'])}")


def main():
    """Carga el orquestador real, corre el benchmark y muestra las estadisticas."""
    orquestador = OrquestadorAgro(
        anthropic.Anthropic(),
        BuscadorMarbetes(),
        cliente_clima=ClienteClima(),
        cliente_climatologia_historica=ClienteClimatologiaHistorica(),
    )
    print(f"Modelo: {orquestador.modelo}\n")
    filas = BenchmarkTokens(orquestador).correr(BENCHMARK_CASOS)
    guardar_filas(filas)
    imprimir_estadisticas(filas)
    print(f"\nFilas guardadas en {RUTA_RESULTADOS}")


if __name__ == "__main__":
    main()
