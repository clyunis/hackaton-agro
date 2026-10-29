"""Definicion de las tools que ve el modelo y su ejecucion local.

Las definiciones (JSON schema) tienen que ser identicas en todas las requests de una
conversacion: cambiarlas invalida el cache de prompt y los bloques de thinking previos.
Por eso se arman una sola vez a nivel modulo.
"""

import json

from agente.calculadora import FORMAS_DE_EXPRESION, CalculadoraNutrientes
from agente.requisitos import CLAVES_DATOS, TIPOS_CONSULTA, CatalogoRequisitos

LARGO_EXTRACTO_FUENTE = 220

DEFINICIONES_HERRAMIENTAS = [
    {
        "name": "analizar_consulta",
        "description": (
            "Clasifica la consulta del ingeniero y registra los datos del lote que ya dio. Devuelve que "
            "datos criticos faltan para responder bien, criterios agronomicos internos para ese tipo de "
            "consulta, que herramientas usar y las limitaciones conocidas de las fuentes. Llamala al "
            "comienzo de cada consulta nueva y otra vez cuando el ingeniero aporte datos nuevos."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_consulta": {
                    "type": "string",
                    "enum": list(TIPOS_CONSULTA),
                    "description": "; ".join(f"{tipo}: {d['descripcion']}" for tipo, d in TIPOS_CONSULTA.items()),
                },
                "datos_identificados": {
                    "type": "array",
                    "description": "Datos que el ingeniero ya informo en la conversacion. No inventes valores.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clave": {
                                "type": "string",
                                "enum": list(CLAVES_DATOS),
                                "description": "; ".join(f"{clave}: {d}" for clave, d in CLAVES_DATOS.items()),
                            },
                            "valor": {"type": "string", "description": "Lo que dijo el ingeniero, textual o resumido"},
                        },
                        "required": ["clave", "valor"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["tipo_consulta", "datos_identificados"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_marbetes",
        "description": (
            "Busca fragmentos de marbetes de productos fitosanitarios (Guia CASAFE, zona Tandil) por "
            "similitud semantica. Cada fragmento vuelve con una etiqueta [F#] para citar. Usa consultas "
            "especificas: principio activo + cultivo + maleza/plaga + momento. Podes llamarla varias veces."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"consulta": {"type": "string", "description": "Texto de busqueda"}},
            "required": ["consulta"],
            "additionalProperties": False,
        },
    },
    {
        "name": "calcular_aporte_nutriente",
        "description": (
            "Calcula cuantos kg/ha de nutriente aporta una dosis de fertilizante, en la forma declarada "
            "(ej. P2O5) y como elemento (P). Devuelve la formula para mostrarla."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "dosis_producto_kg_ha": {"type": "number", "description": "Dosis de producto en kg/ha"},
                "porcentaje_en_producto": {"type": "number", "description": "Grado del nutriente en el producto (%)"},
                "expresado_como": {"type": "string", "enum": FORMAS_DE_EXPRESION},
            },
            "required": ["dosis_producto_kg_ha", "porcentaje_en_producto", "expresado_como"],
            "additionalProperties": False,
        },
    },
    {
        "name": "calcular_dosis_fertilizante",
        "description": (
            "Calcula los kg/ha de producto necesarios para aportar un objetivo de nutriente, convirtiendo "
            "entre formas (P/P2O5, K/K2O) si hace falta. Devuelve la formula para mostrarla."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "nutriente_objetivo_kg_ha": {"type": "number"},
                "objetivo_expresado_como": {"type": "string", "enum": FORMAS_DE_EXPRESION},
                "porcentaje_en_producto": {"type": "number", "description": "Grado del nutriente en el producto (%)"},
                "expresado_como": {"type": "string", "enum": FORMAS_DE_EXPRESION},
            },
            "required": [
                "nutriente_objetivo_kg_ha",
                "objetivo_expresado_como",
                "porcentaje_en_producto",
                "expresado_como",
            ],
            "additionalProperties": False,
        },
    },
]


class RegistroFuentes:
    """Asigna etiquetas [F1], [F2]... a los fragmentos recuperados durante un turno."""

    def __init__(self):
        self.fuentes_por_id: dict[str, dict] = {}

    def registrar(self, fragmento: dict) -> dict:
        """Devuelve la fuente etiquetada; un mismo fragmento recuperado dos veces conserva su etiqueta."""
        if fragmento["id"] not in self.fuentes_por_id:
            contenido_sin_encabezado = fragmento["contenido"].split("---\n", 1)[-1]
            extracto = " ".join(contenido_sin_encabezado.split())[:LARGO_EXTRACTO_FUENTE]
            self.fuentes_por_id[fragmento["id"]] = {
                "etiqueta": f"F{len(self.fuentes_por_id) + 1}",
                "producto": fragmento["producto"],
                "archivo": fragmento["archivo"],
                "extracto": extracto,
            }
        return self.fuentes_por_id[fragmento["id"]]

    def todas(self) -> list[dict]:
        """Fuentes registradas en orden de aparicion."""
        return list(self.fuentes_por_id.values())


class EjecutorHerramientas:
    """Ejecuta localmente la tool que pidio el modelo y devuelve el texto del tool_result."""

    def __init__(self, buscador, catalogo: CatalogoRequisitos, calculadora: CalculadoraNutrientes):
        self.buscador = buscador
        self.catalogo = catalogo
        self.calculadora = calculadora

    def ejecutar(self, nombre: str, entrada: dict, registro_fuentes: RegistroFuentes) -> str:
        """Despacha por nombre. Lanza ValueError ante entradas invalidas (vuelve al modelo como is_error)."""
        if nombre == "analizar_consulta":
            analisis = self.catalogo.analizar(entrada["tipo_consulta"], entrada["datos_identificados"])
            return json.dumps(analisis, ensure_ascii=False)
        if nombre == "buscar_marbetes":
            return self._buscar_marbetes(entrada["consulta"], registro_fuentes)
        if nombre == "calcular_aporte_nutriente":
            resultado = self.calculadora.calcular_aporte(
                entrada["dosis_producto_kg_ha"], entrada["porcentaje_en_producto"], entrada["expresado_como"]
            )
            return json.dumps(resultado, ensure_ascii=False)
        if nombre == "calcular_dosis_fertilizante":
            resultado = self.calculadora.calcular_dosis_producto(
                entrada["nutriente_objetivo_kg_ha"],
                entrada["objetivo_expresado_como"],
                entrada["porcentaje_en_producto"],
                entrada["expresado_como"],
            )
            return json.dumps(resultado, ensure_ascii=False)
        raise ValueError(f"Herramienta desconocida: {nombre}")

    def _buscar_marbetes(self, consulta: str, registro_fuentes: RegistroFuentes) -> str:
        """Busca fragmentos y los devuelve etiquetados para que el modelo los cite."""
        fragmentos = self.buscador.buscar(consulta)
        if not fragmentos:
            return "Sin resultados relevantes en los marbetes para esta busqueda."
        bloques = []
        for fragmento in fragmentos:
            fuente = registro_fuentes.registrar(fragmento)
            bloques.append(
                f"[{fuente['etiqueta']}] Producto: {fragmento['producto']} | Archivo: {fragmento['archivo']} | "
                f"distancia {fragmento['distancia']:.2f}\n{fragmento['contenido']}"
            )
        return "\n\n---\n\n".join(bloques)
