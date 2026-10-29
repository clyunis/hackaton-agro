"""Definicion de las tools que ve el modelo y su ejecucion local.

Las definiciones (JSON schema) tienen que ser identicas en todas las requests de una
conversacion: cambiarlas invalida el cache de prompt y los bloques de thinking previos.
Por eso se arman una sola vez a nivel modulo.
"""

import json

from agente.calculadora import FORMAS_DE_EXPRESION, CalculadoraNutrientes
from agente.clima import ANIOS_ATRAS_POR_DEFECTO, DIAS_PRONOSTICO_POR_DEFECTO, ClienteClima, ClienteClimatologiaHistorica
from agente.fuentes_urls import MAPA_URLS_FUENTES
from agente.regulacion import VerificadorRegulatorio
from agente.requisitos import CLAVES_DATOS, TIPOS_CONSULTA, CatalogoRequisitos

LARGO_EXTRACTO_FUENTE = 220
# Prefijos sin URL propia en el manifiesto (clima): se nombra el organismo, no un archivo local.
ORGANISMO_POR_PREFIJO = {"F": "Guia CASAFE", "N": "SENASA", "W": "Open-Meteo"}

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
        "name": "verificar_estado_regulatorio",
        "description": (
            "Verifica el estado regulatorio de un principio activo o marca comercial: si figura en el "
            "registro de SENASA y si esta prohibido, prohibido parcialmente (ciertas formulaciones o usos) "
            "o de uso restringido segun las resoluciones SENASA cargadas. Las normas vuelven con etiqueta "
            "[N#] para citar. Usala antes de recomendar cualquier producto."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Principio activo (ej. clorpirifos) o marca comercial"}
            },
            "required": ["nombre"],
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
        "name": "consultar_clima",
        "description": (
            "Trae condiciones meteorologicas actuales y pronostico diario (hasta 7 dias) de un partido: "
            "temperatura, humedad, viento, rafagas, lluvia y evapotranspiracion, con alertas de riesgo de "
            "helada y de ventana de viento para pulverizar. Son datos de un modelo meteorologico (Open-Meteo), "
            "no de una estacion propia ni del SMN/INTA. Usala para preguntas sobre condiciones para aplicar, "
            "riesgo de heladas o cualquier consulta que dependa del clima actual o de los proximos dias."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "dias_pronostico": {
                    "type": "integer",
                    "description": "Cantidad de dias de pronostico a incluir (1 a 7). Si no se da, se usan 5.",
                },
                "zona_o_partido": {
                    "type": "string",
                    "description": (
                        "Partido o localidad a consultar (ej. 'Rauch', 'Balcarce'). Si no se da, se usa Tandil."
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "consultar_climatologia_historica",
        "description": (
            "Serie historica de un mes (temperatura, lluvia y dias con helada, anio por anio) en los ultimos "
            "N anios de un partido, via el archivo historico de Open-Meteo (reanalisis, no estacion propia). "
            "Sirve para ver si una campana es normal o entra en un patron que se repite cada varios anios, "
            "en vez de leer promedios estaticos. Usala cuando la consulta compare contra lo historico (ej. "
            "'como viene siendo mayo en los ultimos anios') en vez de pedir el clima de hoy."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "integer", "description": "Mes a analizar, 1 (enero) a 12 (diciembre)."},
                "anios_atras": {
                    "type": "integer",
                    "description": "Cuantos anios hacia atras incluir (1 a 20). Si no se da, se usan 10.",
                },
                "zona_o_partido": {
                    "type": "string",
                    "description": (
                        "Partido o localidad a consultar (ej. 'Rauch', 'Balcarce'). Si no se da, se usa Tandil."
                    ),
                },
            },
            "required": ["mes"],
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
    """Asigna etiquetas a lo citable de un turno: [F1].. marbete, [N1].. normas SENASA, [W1].. clima."""

    def __init__(self):
        self.fuentes_por_id: dict[str, dict] = {}
        self.cantidad_por_prefijo: dict[str, int] = {}

    def _agregar(self, identificador: str, prefijo: str, producto: str, archivo: str, texto: str) -> dict:
        """Registra una fuente nueva o devuelve la existente (misma etiqueta si se recupera dos veces)."""
        if identificador not in self.fuentes_por_id:
            self.cantidad_por_prefijo[prefijo] = self.cantidad_por_prefijo.get(prefijo, 0) + 1
            url = MAPA_URLS_FUENTES.buscar(archivo)
            self.fuentes_por_id[identificador] = {
                "etiqueta": f"{prefijo}{self.cantidad_por_prefijo[prefijo]}",
                "producto": producto,
                "archivo": archivo,
                "extracto": " ".join(texto.split())[:LARGO_EXTRACTO_FUENTE],
                # Referencia corta para mostrarle al ingeniero: el link a la pagina de origen
                # si se conoce, o el organismo (nunca el nombre del archivo local).
                "referencia": url or ORGANISMO_POR_PREFIJO.get(prefijo, producto),
            }
        return self.fuentes_por_id[identificador]

    def registrar(self, fragmento: dict) -> dict:
        """Etiqueta [F#] para un fragmento de marbete (el extracto saltea el encabezado del chunk)."""
        contenido_sin_encabezado = fragmento["contenido"].split("---\n", 1)[-1]
        return self._agregar(
            fragmento["id"], "F", fragmento["producto"], fragmento["archivo"], contenido_sin_encabezado
        )

    def registrar_norma(self, restriccion: dict) -> dict:
        """Etiqueta [N#] para una restriccion SENASA, con el texto del articulo como extracto."""
        cita = f"{restriccion['norma']} {restriccion['articulo']}"
        return self._agregar(
            f"norma:{restriccion['principio_activo']}:{cita}", "N", cita, restriccion["archivo"], restriccion["texto"]
        )

    def registrar_clima(self, datos_clima: dict) -> dict:
        """Etiqueta [W#] para una consulta de clima actual/pronostico, por ubicacion y momento."""
        resumen = (
            f"{datos_clima['ubicacion']}, actualizado {datos_clima['actualizado']}: "
            f"{datos_clima['condiciones_actuales']['temperatura_c']} C, "
            f"viento {datos_clima['condiciones_actuales']['viento_kmh']} km/h."
        )
        return self._agregar(
            f"clima:{datos_clima['ubicacion']}:{datos_clima['actualizado']}",
            "W",
            f"Clima {datos_clima['ubicacion']} ({datos_clima['actualizado']})",
            datos_clima["fuente"],
            resumen,
        )

    def registrar_climatologia_historica(self, datos_historicos: dict) -> dict:
        """Etiqueta [W#] para una consulta de climatologia historica, por ubicacion/mes/rango de anios."""
        resumen = (
            f"{datos_historicos['ubicacion']}, {datos_historicos['mes_consultado']} "
            f"{datos_historicos['rango_consultado']}: promedio {datos_historicos['promedio_historico']}."
        )
        return self._agregar(
            f"clima_historico:{datos_historicos['ubicacion']}:{datos_historicos['mes_consultado']}:"
            f"{datos_historicos['rango_consultado']}",
            "W",
            f"Clima historico {datos_historicos['ubicacion']} ({datos_historicos['mes_consultado']} "
            f"{datos_historicos['rango_consultado']})",
            datos_historicos["fuente"],
            resumen,
        )

    def todas(self) -> list[dict]:
        """Fuentes registradas en orden de aparicion."""
        return list(self.fuentes_por_id.values())


class EjecutorHerramientas:
    """Ejecuta localmente la tool que pidio el modelo y devuelve el texto del tool_result."""

    def __init__(
        self,
        buscador,
        catalogo: CatalogoRequisitos,
        calculadora: CalculadoraNutrientes,
        verificador: VerificadorRegulatorio,
        cliente_clima=None,
        cliente_climatologia_historica=None,
    ):
        self.buscador = buscador
        self.catalogo = catalogo
        self.calculadora = calculadora
        self.verificador = verificador
        self.cliente_clima = cliente_clima or ClienteClima()
        self.cliente_climatologia_historica = cliente_climatologia_historica or ClienteClimatologiaHistorica()

    def ejecutar(self, nombre: str, entrada: dict, registro_fuentes: RegistroFuentes) -> str:
        """Despacha por nombre. Lanza ValueError ante entradas invalidas (vuelve al modelo como is_error)."""
        if nombre == "analizar_consulta":
            analisis = self.catalogo.analizar(entrada["tipo_consulta"], entrada["datos_identificados"])
            return json.dumps(analisis, ensure_ascii=False)
        if nombre == "buscar_marbetes":
            return self._buscar_marbetes(entrada["consulta"], registro_fuentes)
        if nombre == "verificar_estado_regulatorio":
            return self._verificar_estado_regulatorio(entrada["nombre"], registro_fuentes)
        if nombre == "consultar_clima":
            return self._consultar_clima(
                entrada.get("dias_pronostico", DIAS_PRONOSTICO_POR_DEFECTO),
                entrada.get("zona_o_partido"),
                registro_fuentes,
            )
        if nombre == "consultar_climatologia_historica":
            return self._consultar_climatologia_historica(
                entrada["mes"],
                entrada.get("anios_atras", ANIOS_ATRAS_POR_DEFECTO),
                entrada.get("zona_o_partido"),
                registro_fuentes,
            )
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
            # El estado regulatorio va pegado al fragmento: el modelo lo ve aunque no llame a la tool.
            lineas_alerta = [
                f"ESTADO SENASA [{registro_fuentes.registrar_norma(r)['etiqueta']}]: "
                f"{self.verificador.describir_restriccion(r)}"
                for r in self.verificador.restricciones_para_producto(fragmento["producto"])
            ]
            encabezado = (
                f"[{fuente['etiqueta']}] Producto: {fragmento['producto']} | Archivo: {fragmento['archivo']} | "
                f"distancia {fragmento['distancia']:.2f}"
            )
            bloques.append("\n".join([encabezado, *lineas_alerta, fragmento["contenido"]]))
        return "\n\n---\n\n".join(bloques)

    def _verificar_estado_regulatorio(self, nombre: str, registro_fuentes: RegistroFuentes) -> str:
        """Estado regulatorio en JSON, con cada norma etiquetada [N#] para citar."""
        resultado = self.verificador.verificar(nombre)
        for restriccion in resultado["restricciones"]:
            restriccion["etiqueta"] = registro_fuentes.registrar_norma(restriccion)["etiqueta"]
        return json.dumps(resultado, ensure_ascii=False)

    def _consultar_clima(self, dias_pronostico: int, zona_o_partido: str | None, registro_fuentes: RegistroFuentes) -> str:
        """Clima actual y pronostico de un partido en JSON, etiquetado [W#] para citar."""
        datos = self.cliente_clima.consultar(dias_pronostico, zona_o_partido)
        datos["etiqueta"] = registro_fuentes.registrar_clima(datos)["etiqueta"]
        return json.dumps(datos, ensure_ascii=False)

    def _consultar_climatologia_historica(
        self, mes: int, anios_atras: int, zona_o_partido: str | None, registro_fuentes: RegistroFuentes
    ) -> str:
        """Serie historica de un mes en JSON, etiquetada [W#] para citar."""
        datos = self.cliente_climatologia_historica.consultar(mes, anios_atras, zona_o_partido)
        datos["etiqueta"] = registro_fuentes.registrar_climatologia_historica(datos)["etiqueta"]
        return json.dumps(datos, ensure_ascii=False)
