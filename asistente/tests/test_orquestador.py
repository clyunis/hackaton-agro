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


def respuesta(stop_reason, *bloques):
    """Respuesta de messages.create con stop_reason y contenido dados."""
    return SimpleNamespace(stop_reason=stop_reason, content=list(bloques))


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
