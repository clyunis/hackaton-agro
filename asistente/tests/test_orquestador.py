"""Tests del loop del orquestador con un cliente de Claude falso (sin red ni GPU)."""

import json
from types import SimpleNamespace

import pytest

from agente.orquestador import ConversacionAgro, OrquestadorAgro


def bloque_texto(texto):
    """Bloque de texto como los que devuelve la API."""
    return SimpleNamespace(type="text", text=texto)


def bloque_herramienta(identificador, nombre, entrada):
    """Bloque tool_use como los que devuelve la API."""
    return SimpleNamespace(type="tool_use", id=identificador, name=nombre, input=entrada)


def respuesta(stop_reason, *bloques, usage=None):
    """Respuesta de messages.create con stop_reason, contenido y 'usage' (opcional) dados."""
    return SimpleNamespace(stop_reason=stop_reason, content=list(bloques), usage=usage)


def uso(input_tokens=0, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0):
    """Objeto 'usage' como el que devuelve la API (los campos ausentes se leen como 0)."""
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
    )


class ClienteFalso:
    """Imita anthropic.Anthropic: devuelve respuestas guionadas y registra cada llamada."""

    def __init__(self, respuestas_guionadas):
        self.respuestas_guionadas = list(respuestas_guionadas)
        self.llamadas = []
        self.messages = SimpleNamespace(create=self._crear)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear_beta))

    def _crear(self, **parametros):
        """Registra la llamada (copiando messages, que el orquestador sigue mutando)."""
        parametros["messages"] = list(parametros["messages"])
        self.llamadas.append(parametros)
        return self.respuestas_guionadas.pop(0)

    def _crear_beta(self, **parametros):
        """Misma logica que _crear, marcando que se uso el endpoint beta."""
        parametros["_beta"] = True
        return self._crear(**parametros)


class BuscadorFalso:
    """Devuelve siempre el mismo fragmento de marbete y registra las consultas."""

    def __init__(self):
        self.consultas = []

    def buscar(self, consulta):
        """Simula BuscadorMarbetes.buscar."""
        self.consultas.append(consulta)
        return [
            {
                "id": "marbete_casafe:254_chunk_3",
                "producto": "GLIFOSATO",
                "archivo": "0254_glifosato.pdf",
                "contenido": "Producto: GLIFOSATO\n---\nSoja  Rama negra  PC 62%: 2 l/ha  Aplicar en roseta",
                "distancia": 0.41,
            }
        ]


def resultados_de_herramientas(llamada):
    """Extrae los tool_result del ultimo mensaje enviado en una llamada."""
    return llamada["messages"][-1]["content"]


def test_consulta_incompleta_termina_en_preguntas_sin_buscar():
    """'Dame dosis de glifosato para soja': analiza, ve que faltan datos y repregunta."""
    cliente = ClienteFalso(
        [
            respuesta(
                "tool_use",
                bloque_herramienta(
                    "t1",
                    "analizar_consulta",
                    {"tipo_consulta": "dosis_herbicida", "datos_identificados": [{"clave": "cultivo", "valor": "soja"}]},
                ),
            ),
            respuesta("end_turn", bloque_texto("Antes de darte una dosis: que malezas hay y de que tamano?")),
        ]
    )
    buscador = BuscadorFalso()
    orquestador = OrquestadorAgro(cliente, buscador, modelo="claude-opus-5-5")

    resultado = orquestador.responder([], "dame dosis de glifosato para soja")

    assert "malezas" in resultado.texto
    assert buscador.consultas == []
    claves_faltantes = {faltante["clave"] for faltante in resultado.datos_faltantes}
    assert {"malezas_presentes", "tamano_malezas"} <= claves_faltantes
    resultado_analisis = json.loads(resultados_de_herramientas(cliente.llamadas[1])[0]["content"])
    assert resultado_analisis["puede_responder"] is False


def test_calculo_se_hace_con_la_herramienta():
    """La cuenta de urea sale de la calculadora y vuelve al modelo como tool_result."""
    cliente = ClienteFalso(
        [
            respuesta(
                "tool_use",
                bloque_herramienta(
                    "t1",
                    "calcular_aporte_nutriente",
                    {"dosis_producto_kg_ha": 200, "porcentaje_en_producto": 46, "expresado_como": "N"},
                ),
            ),
            respuesta("end_turn", bloque_texto("Aportaste 92 kg N/ha.")),
        ]
    )
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5")

    resultado = orquestador.responder([], "Aplique 200 kg/ha de urea, cuanto N aporte?")

    resultado_calculo = json.loads(resultados_de_herramientas(cliente.llamadas[1])[0]["content"])
    assert resultado_calculo["nutriente_kg_ha"] == pytest.approx(92.0)
    assert resultado.herramientas_usadas[0]["nombre"] == "calcular_aporte_nutriente"


def test_busqueda_registra_fuentes_y_filtra_las_citadas():
    """Los fragmentos recuperados se etiquetan [F1]..; la respuesta lista solo los citados."""
    cliente = ClienteFalso(
        [
            respuesta("tool_use", bloque_herramienta("t1", "buscar_marbetes", {"consulta": "glifosato soja rama negra"})),
            respuesta("end_turn", bloque_texto("PC 62%: 2 l/ha en roseta [F1].")),
        ]
    )
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5")

    resultado = orquestador.responder([], "glifosato para rama negra en roseta, barbecho de soja")

    texto_resultado_busqueda = resultados_de_herramientas(cliente.llamadas[1])[0]["content"]
    assert "[F1]" in texto_resultado_busqueda
    assert [fuente["etiqueta"] for fuente in resultado.fuentes_citadas()] == ["F1"]
    assert resultado.fuentes_citadas()[0]["archivo"] == "0254_glifosato.pdf"


class BuscadorClorpirifos(BuscadorFalso):
    """Devuelve un marbete de un activo prohibido (la guia CASAFE es anterior a la Res. 414/2021)."""

    def buscar(self, consulta):
        """Simula un fragmento del marbete de clorpirifos."""
        self.consultas.append(consulta)
        return [
            {
                "id": "marbete_casafe:114_chunk_0",
                "producto": "CLORPIRIFOS",
                "archivo": "0114_clorpirifos.pdf",
                "contenido": "Producto: CLORPIRIFOS\n---\nSoja  Oruga medidora  ...",
                "distancia": 0.35,
            }
        ]


def test_busqueda_marca_fragmentos_prohibidos_con_su_norma():
    """Cada fragmento de un activo prohibido llega con 'ESTADO SENASA [N#]' y la norma queda citable."""
    cliente = ClienteFalso(
        [
            respuesta("tool_use", bloque_herramienta("t1", "buscar_marbetes", {"consulta": "oruga soja"})),
            respuesta("end_turn", bloque_texto("El clorpirifos esta prohibido [N1].")),
        ]
    )
    orquestador = OrquestadorAgro(cliente, BuscadorClorpirifos(), modelo="claude-opus-5-5")

    resultado = orquestador.responder([], "que uso para oruga medidora en soja?")

    texto_resultado_busqueda = resultados_de_herramientas(cliente.llamadas[1])[0]["content"]
    assert "ESTADO SENASA [N1]: PROHIBIDO" in texto_resultado_busqueda
    citadas = resultado.fuentes_citadas()
    assert [fuente["etiqueta"] for fuente in citadas] == ["N1"]
    assert citadas[0]["producto"] == "Res. SENASA 414/2021 Art. 3"


def test_verificar_estado_regulatorio_etiqueta_las_normas():
    """La tool devuelve la conclusion y cada restriccion con su etiqueta [N#]."""
    cliente = ClienteFalso(
        [
            respuesta("tool_use", bloque_herramienta("t1", "verificar_estado_regulatorio", {"nombre": "clorpirifos"})),
            respuesta("end_turn", bloque_texto("Prohibido [N1].")),
        ]
    )
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5")

    orquestador.responder([], "puedo usar clorpirifos?")

    resultado_verificacion = json.loads(resultados_de_herramientas(cliente.llamadas[1])[0]["content"])
    assert resultado_verificacion["conclusion"].startswith("PROHIBIDO")
    assert resultado_verificacion["restricciones"][0]["etiqueta"] == "N1"


class ClienteClimaFalso:
    """Devuelve siempre el mismo resultado de ClienteClima.consultar, sin red."""

    def __init__(self):
        self.dias_pedidos = []

    def consultar(self, dias_pronostico, zona_o_partido=None):
        """Simula ClienteClima.consultar con un dia de pronostico con riesgo de helada."""
        self.dias_pedidos.append(dias_pronostico)
        return {
            "ubicacion": "Tandil, Buenos Aires (-37.3217, -59.1332)",
            "fuente": "Open-Meteo (api.open-meteo.com), modelo meteorologico, no estacion propia de Tandil",
            "actualizado": "2026-10-29T15:00",
            "condiciones_actuales": {
                "hora": "2026-10-29T15:00",
                "temperatura_c": 18.5,
                "humedad_relativa_pct": 55,
                "precipitacion_mm": 0.0,
                "viento_kmh": 10.0,
                "rafagas_kmh": 18.0,
                "direccion_viento_grados": 200,
            },
            "pronostico_diario": [
                {
                    "fecha": "2026-10-30",
                    "temp_max_c": 23.1,
                    "temp_min_c": 2.5,
                    "precipitacion_mm": 5.0,
                    "probabilidad_precipitacion_pct": 80,
                    "viento_max_kmh": 8.0,
                    "rafagas_max_kmh": 15.0,
                    "evapotranspiracion_mm": 3.0,
                    "riesgo_helada": "riesgo_helada",
                    "apto_para_aplicar": False,
                }
            ],
            "alertas_agronomicas": ["2026-10-30: riesgo_helada (minima 2.5 C)."],
            "limitaciones": "Datos de un modelo meteorologico, no de una estacion de Tandil.",
        }


def test_consultar_clima_registra_fuente_w_y_llega_etiquetada():
    """El resultado de consultar_clima se etiqueta [W1] y queda citable como cualquier otra fuente."""
    cliente_llm = ClienteFalso(
        [
            respuesta("tool_use", bloque_herramienta("t1", "consultar_clima", {"dias_pronostico": 2})),
            respuesta("end_turn", bloque_texto("Hay riesgo de helada el 30/10 [W1].")),
        ]
    )
    cliente_clima = ClienteClimaFalso()
    orquestador = OrquestadorAgro(cliente_llm, BuscadorFalso(), modelo="claude-opus-5-5", cliente_clima=cliente_clima)

    resultado = orquestador.responder([], "hay riesgo de helada para los proximos dias?")

    assert cliente_clima.dias_pedidos == [2]
    texto_resultado_clima = resultados_de_herramientas(cliente_llm.llamadas[1])[0]["content"]
    assert "[W1]" not in texto_resultado_clima  # la etiqueta va en el dict, no incrustada en el texto
    datos_clima = json.loads(texto_resultado_clima)
    assert datos_clima["etiqueta"] == "W1"
    citadas = resultado.fuentes_citadas()
    assert [fuente["etiqueta"] for fuente in citadas] == ["W1"]


class ClienteClimatologiaHistoricaFalso:
    """Devuelve siempre el mismo resumen historico, sin red."""

    def __init__(self):
        self.pedidos = []

    def consultar(self, mes, anios_atras=None, zona_o_partido=None):
        """Simula ClienteClimatologiaHistorica.consultar con dos anios de mayo."""
        self.pedidos.append((mes, anios_atras, zona_o_partido))
        return {
            "ubicacion": "Tandil, Buenos Aires (-37.3217, -59.1332)",
            "fuente": "Open-Meteo Archive (archive-api.open-meteo.com), reanalisis ERA5, no estaciones locales",
            "mes_consultado": "mayo",
            "rango_consultado": "2016-2026",
            "anios": [
                {"anio": 2021, "temp_max_promedio_c": 18.0, "temp_min_promedio_c": 5.0, "temp_min_minima_c": -2.0,
                 "precipitacion_total_mm": 40.0, "dias_con_helada": 3, "dias_con_lluvia": 6},
            ],
            "promedio_historico": {"dias_con_helada": 3, "precipitacion_total_mm": 40.0},
            "limitaciones": ["Serie historica de un modelo de reanalisis."],
        }


def test_consultar_climatologia_historica_registra_fuente_w():
    """El resultado de consultar_climatologia_historica tambien se etiqueta [W#] y queda citable."""
    cliente_llm = ClienteFalso(
        [
            respuesta(
                "tool_use", bloque_herramienta("t1", "consultar_climatologia_historica", {"mes": 5, "anios_atras": 10})
            ),
            respuesta("end_turn", bloque_texto("Mayo suele traer heladas [W1].")),
        ]
    )
    cliente_historico = ClienteClimatologiaHistoricaFalso()
    orquestador = OrquestadorAgro(
        cliente_llm, BuscadorFalso(), modelo="claude-opus-5-5", cliente_climatologia_historica=cliente_historico
    )

    resultado = orquestador.responder([], "como vienen siendo las heladas de mayo en los ultimos anios?")

    assert cliente_historico.pedidos == [(5, 10, None)]
    datos_historicos = json.loads(resultados_de_herramientas(cliente_llm.llamadas[1])[0]["content"])
    assert datos_historicos["etiqueta"] == "W1"
    assert [fuente["etiqueta"] for fuente in resultado.fuentes_citadas()] == ["W1"]


def test_error_de_herramienta_vuelve_como_is_error():
    """Una entrada invalida no rompe el loop: el modelo recibe el error y puede corregir."""
    cliente = ClienteFalso(
        [
            respuesta(
                "tool_use",
                bloque_herramienta(
                    "t1",
                    "calcular_aporte_nutriente",
                    {"dosis_producto_kg_ha": 200, "porcentaje_en_producto": 0, "expresado_como": "N"},
                ),
            ),
            respuesta("end_turn", bloque_texto("Revisa el grado del fertilizante.")),
        ]
    )
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5")

    orquestador.responder([], "urea al 0%")

    resultado_herramienta = resultados_de_herramientas(cliente.llamadas[1])[0]
    assert resultado_herramienta["is_error"] is True


def test_limite_de_iteraciones_fuerza_respuesta_sin_herramientas():
    """Si el modelo no deja de pedir herramientas, la ultima llamada va con tool_choice none."""
    pedido_busqueda = respuesta("tool_use", bloque_herramienta("t", "buscar_marbetes", {"consulta": "x"}))
    cliente = ClienteFalso([pedido_busqueda, pedido_busqueda, respuesta("end_turn", bloque_texto("Cierre."))])
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5", max_iteraciones=2)

    resultado = orquestador.responder([], "consulta")

    assert cliente.llamadas[-1]["tool_choice"] == {"type": "none"}
    assert resultado.texto == "Cierre."


def test_rechazo_no_modifica_el_historial():
    """Ante stop_reason refusal se devuelve un aviso y no se agregan mensajes al historial."""
    cliente = ClienteFalso([respuesta("refusal")])
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5")

    resultado = orquestador.responder([], "consulta")

    assert resultado.completo is False
    assert resultado.mensajes_nuevos == []


def test_fallback_de_servidor_solo_en_modelos_que_lo_soportan():
    """Opus 5.5 va por el endpoint beta con fallbacks; Haiku 4.5 por el endpoint comun."""
    cliente_opus = ClienteFalso([respuesta("end_turn", bloque_texto("ok"))])
    OrquestadorAgro(cliente_opus, BuscadorFalso(), modelo="claude-opus-5-5").responder([], "hola")
    assert cliente_opus.llamadas[0]["_beta"] is True
    assert cliente_opus.llamadas[0]["fallbacks"] == "default"

    cliente_haiku = ClienteFalso([respuesta("end_turn", bloque_texto("ok"))])
    OrquestadorAgro(cliente_haiku, BuscadorFalso(), modelo="claude-haiku-4-5").responder([], "hola")
    assert "_beta" not in cliente_haiku.llamadas[0]
    assert "fallbacks" not in cliente_haiku.llamadas[0]


def test_conversacion_acumula_el_historial_sin_editarlo():
    """La respuesta a una repregunta viaja con todo el turno anterior intacto adelante."""
    cliente = ClienteFalso(
        [
            respuesta("end_turn", bloque_texto("Que malezas hay?")),
            respuesta("end_turn", bloque_texto("Con rama negra en roseta...")),
        ]
    )
    conversacion = ConversacionAgro(OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5"))

    conversacion.consultar("dame dosis de glifosato para soja")
    conversacion.consultar("rama negra en roseta")

    mensajes_segunda_llamada = cliente.llamadas[1]["messages"]
    assert mensajes_segunda_llamada[0] == {"role": "user", "content": "dame dosis de glifosato para soja"}
    assert mensajes_segunda_llamada[1]["role"] == "assistant"
    assert mensajes_segunda_llamada[-1] == {"role": "user", "content": "rama negra en roseta"}


def test_conversacion_reiniciar_vacia_el_historial():
    """/nueva arranca de cero (compactacion simple: se descarta todo el historial)."""
    cliente = ClienteFalso([respuesta("end_turn", bloque_texto("a")), respuesta("end_turn", bloque_texto("b"))])
    conversacion = ConversacionAgro(OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5"))

    conversacion.consultar("primera")
    conversacion.reiniciar()
    conversacion.consultar("segunda")

    assert cliente.llamadas[1]["messages"] == [{"role": "user", "content": "segunda"}]


def test_uso_tokens_se_acumula_entre_llamadas_del_turno():
    """Una tool_use + una respuesta final suman sus 'usage' en el total del turno."""
    cliente = ClienteFalso(
        [
            respuesta(
                "tool_use",
                bloque_herramienta("t1", "buscar_marbetes", {"consulta": "glifosato soja"}),
                usage=uso(input_tokens=500, output_tokens=50, cache_read_input_tokens=400),
            ),
            respuesta(
                "end_turn",
                bloque_texto("PC 62%: 2 l/ha [F1]."),
                usage=uso(input_tokens=600, output_tokens=80, cache_creation_input_tokens=100),
            ),
        ]
    )
    orquestador = OrquestadorAgro(cliente, BuscadorFalso(), modelo="claude-opus-5-5")

    resultado = orquestador.responder([], "glifosato para soja")

    assert resultado.uso_tokens == {
        "llamadas_api": 2,
        "input_tokens": 1100,
        "output_tokens": 130,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 400,
    }
