"""Orquestador agentico de AGRIA: un loop de tool use con Claude.

En cada consulta el modelo decide, con las tools de herramientas.py:
  1. hacia donde va la consulta y que datos faltan (analizar_consulta),
  2. si repregunta al ingeniero (termina el turno con preguntas) o sigue,
  3. que tools usar para juntar evidencia (buscar_marbetes) o hacer cuentas (calcular_*),
y recien ahi redacta la respuesta citando [F#].

Reemplaza al pipeline fijo de scripts/ask.py (buscar 5 chunks -> responder), que no
podia pedir datos ni hacer cuentas verificables. ask.py queda como v1 para comparar.

Historial: se usa la API de Anthropic directo (no langchain) y el historial de cada chat
es append-only -- se reenvian los bloques de la respuesta tal cual (incluido thinking).
Editar o recortar turnos del medio invalida el cache y, en cuentas nuevas, da 400.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field

from agente.calculadora import CalculadoraNutrientes
from agente.herramientas import DEFINICIONES_HERRAMIENTAS, EjecutorHerramientas, RegistroFuentes
from agente.regulacion import VerificadorRegulatorio
from agente.requisitos import CatalogoRequisitos

logger = logging.getLogger(__name__)

MODELO_POR_DEFECTO = os.environ.get("CLAUDE_MODEL_AGENTE", "claude-opus-5-5")
MAX_TOKENS_RESPUESTA = 16000
MAX_ITERACIONES_POR_DEFECTO = 6
# Compactacion simple: pasado este largo se descarta todo el historial (nunca un recorte parcial).
MAX_MENSAJES_HISTORIAL = 60

# Modelos que aceptan el fallback de servidor ante un rechazo de los clasificadores de seguridad
# (una consulta sobre toxicologia de un fitosanitario podria disparar un falso positivo).
MODELOS_CON_FALLBACK_SERVIDOR = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
BETA_FALLBACK_SERVIDOR = "server-side-fallback-2026-07-01"

MENSAJE_RECHAZO = (
    "No pude procesar esta consulta. Probá reformularla con más contexto técnico del lote."
)
MENSAJE_CORTADO = "La respuesta quedó incompleta. Probá con una consulta más acotada."

SYSTEM_PROMPT = """Sos AGRIA, un asistente tecnico para ingenieros agronomos de Tandil y partidos
vecinos (agricultura extensiva). Trabajas como un colega con criterio agronomico: antes de
recomendar, entendes la situacion del lote.

Como trabajar cada consulta:
1. Llama primero a analizar_consulta para clasificar la consulta y registrar los datos que el
   ingeniero ya dio. Te devuelve que datos criticos faltan, criterios para ese tipo de consulta,
   que herramientas usar y limitaciones conocidas de las fuentes.
2. Si faltan datos criticos, NO respondas con tablas genericas: termina el turno con preguntas
   concretas (maximo 4), explicando en una linea por que cada dato cambia la recomendacion. Si
   podes adelantar algo util y seguro sin esos datos, hacelo en una o dos lineas.
3. Con datos suficientes, busca evidencia con buscar_marbetes (podes buscar varias veces, con
   consultas especificas: principio activo + cultivo + maleza/plaga + momento). Para cualquier
   cuenta usa las herramientas de calculo y mostra la formula; nunca hagas cuentas de memoria.
4. Antes de recomendar un producto o principio activo, verifica su estado con
   verificar_estado_regulatorio. Los fragmentos de buscar_marbetes ya traen una linea
   "ESTADO SENASA [N#]" cuando hay una prohibicion o restriccion conocida.
5. Cuando el ingeniero responda tus preguntas, volve a llamar a analizar_consulta con los datos
   nuevos antes de seguir.

Reglas de respuesta:
- Toda afirmacion tecnica (dosis, cultivo habilitado, momento, restriccion, carencia) lleva la
  etiqueta de su fuente: [F#] para marbetes, [N#] para normas SENASA, ej: [F2]. Dosis y momentos se copian tal
  como figuran en el marbete: no cambies "despues de la siembra" por "despues de la emergencia",
  ni reagrupes las filas de la tabla con un criterio que el marbete no usa.
- Los criterios que devuelve analizar_consulta son guia interna del equipo, no fuentes citables.
  Todo lo que no salga literalmente de una fuente va marcado como "Interpretacion propia:".
- Si las fuentes no cubren la situacion (la maleza no figura, no hay plazo informado, no hay
  modelo de fertilizacion), decilo: "No tengo evidencia suficiente en las fuentes disponibles
  para ...". No inventes dosis, plazos ni restricciones.
- Si la situacion no justifica una aplicacion (por ejemplo, lote limpio), decilo en vez de dar
  una dosis.
- Nunca recomiendes un producto PROHIBIDO, aunque figure en un marbete (la guia CASAFE es anterior
  a varias prohibiciones): decilo citando la norma [N#] y, si corresponde, busca alternativas. Si es
  PROHIBIDO PARCIAL o USO RESTRINGIDO, explica el alcance y pedi la formulacion o el uso previsto.
  Que un producto figure en el registro no confirma que este autorizado para ese cultivo; si la
  herramienta no lo encuentra, no lo des por legal.
- Espanol rioplatense, conciso y tecnico. Texto plano sin Markdown (nada de **, ## ni backticks):
  se muestra en Telegram. Listas con "-"."""


@dataclass
class ResultadoTurno:
    """Lo que devuelve el orquestador para un turno de la conversacion."""

    texto: str
    completo: bool = True
    fuentes: list[dict] = field(default_factory=list)
    datos_faltantes: list[dict] = field(default_factory=list)
    herramientas_usadas: list[dict] = field(default_factory=list)
    mensajes_nuevos: list[dict] = field(default_factory=list)

    def fuentes_citadas(self) -> list[dict]:
        """Fuentes cuya etiqueta (F# o N#) aparece en el texto; si no cito ninguna, todas las recuperadas."""
        etiquetas_citadas = set(re.findall(r"\b([FN]\d+)\b", self.texto))
        citadas = [fuente for fuente in self.fuentes if fuente["etiqueta"] in etiquetas_citadas]
        return citadas or self.fuentes


class OrquestadorAgro:
    """Corre el loop de tool use para un turno: modelo -> tools -> modelo ... -> respuesta."""

    def __init__(
        self,
        cliente_anthropic,
        buscador,
        modelo: str = MODELO_POR_DEFECTO,
        max_iteraciones: int = MAX_ITERACIONES_POR_DEFECTO,
        verificador: VerificadorRegulatorio | None = None,
    ):
        self.cliente = cliente_anthropic
        self.modelo = modelo
        self.max_iteraciones = max_iteraciones
        self.ejecutor = EjecutorHerramientas(
            buscador, CatalogoRequisitos(), CalculadoraNutrientes(), verificador or VerificadorRegulatorio()
        )

    def _llamar_modelo(self, mensajes: list[dict], permitir_herramientas: bool = True):
        """Una request a la Messages API; system y tools son fijos para no romper el cache."""
        parametros = {
            "model": self.modelo,
            "max_tokens": MAX_TOKENS_RESPUESTA,
            "system": SYSTEM_PROMPT,
            "tools": DEFINICIONES_HERRAMIENTAS,
            "messages": mensajes,
            "cache_control": {"type": "ephemeral"},
        }
        if not permitir_herramientas:
            parametros["tool_choice"] = {"type": "none"}
        if self.modelo in MODELOS_CON_FALLBACK_SERVIDOR:
            return self.cliente.beta.messages.create(
                **parametros, betas=[BETA_FALLBACK_SERVIDOR], fallbacks="default"
            )
        return self.cliente.messages.create(**parametros)

    def _ejecutar_herramientas(self, respuesta, registro_fuentes: RegistroFuentes, resultado: ResultadoTurno) -> dict:
        """Corre todos los tool_use de una respuesta y arma un unico mensaje user con sus tool_result."""
        resultados_herramientas = []
        for bloque in respuesta.content:
            if bloque.type != "tool_use":
                continue
            resultado.herramientas_usadas.append({"nombre": bloque.name, "entrada": bloque.input})
            logger.info("Tool %s: %s", bloque.name, bloque.input)
            try:
                contenido = self.ejecutor.ejecutar(bloque.name, bloque.input, registro_fuentes)
                resultados_herramientas.append({"type": "tool_result", "tool_use_id": bloque.id, "content": contenido})
                if bloque.name == "analizar_consulta":
                    resultado.datos_faltantes = json.loads(contenido)["datos_faltantes_criticos"]
            except (ValueError, KeyError) as error:
                resultados_herramientas.append(
                    {"type": "tool_result", "tool_use_id": bloque.id, "content": f"Error: {error}", "is_error": True}
                )
        return {"role": "user", "content": resultados_herramientas}

    def responder(self, historial: list[dict], pregunta: str) -> ResultadoTurno:
        """Corre un turno completo. No modifica historial: los mensajes a agregar van en mensajes_nuevos."""
        registro_fuentes = RegistroFuentes()
        resultado = ResultadoTurno(texto="")
        mensajes_nuevos = [{"role": "user", "content": pregunta}]
        mensajes = list(historial) + mensajes_nuevos

        respuesta = None
        for _ in range(self.max_iteraciones):
            respuesta = self._llamar_modelo(mensajes)
            if respuesta.stop_reason in ("refusal", "max_tokens"):
                break
            mensaje_asistente = {"role": "assistant", "content": respuesta.content}
            mensajes.append(mensaje_asistente)
            mensajes_nuevos.append(mensaje_asistente)
            if respuesta.stop_reason != "tool_use":
                break
            mensaje_resultados = self._ejecutar_herramientas(respuesta, registro_fuentes, resultado)
            mensajes.append(mensaje_resultados)
            mensajes_nuevos.append(mensaje_resultados)
        else:
            # Llego al limite pidiendo herramientas: una ultima llamada que solo puede responder texto.
            respuesta = self._llamar_modelo(mensajes, permitir_herramientas=False)
            if respuesta.stop_reason not in ("refusal", "max_tokens"):
                mensaje_asistente = {"role": "assistant", "content": respuesta.content}
                mensajes_nuevos.append(mensaje_asistente)

        if respuesta.stop_reason in ("refusal", "max_tokens"):
            # El turno se descarta entero: el historial del chat queda como estaba.
            texto_aviso = MENSAJE_RECHAZO if respuesta.stop_reason == "refusal" else MENSAJE_CORTADO
            return ResultadoTurno(texto=texto_aviso, completo=False, herramientas_usadas=resultado.herramientas_usadas)

        resultado.texto = "\n".join(bloque.text for bloque in respuesta.content if bloque.type == "text").strip()
        resultado.fuentes = registro_fuentes.todas()
        resultado.mensajes_nuevos = mensajes_nuevos
        return resultado


class ConversacionAgro:
    """Historial append-only de un chat (un ingeniero) sobre un OrquestadorAgro compartido."""

    def __init__(self, orquestador: OrquestadorAgro):
        self.orquestador = orquestador
        self.historial: list[dict] = []

    def consultar(self, pregunta: str) -> ResultadoTurno:
        """Corre un turno y, si termino bien, agrega sus mensajes al historial."""
        if len(self.historial) > MAX_MENSAJES_HISTORIAL:
            self.reiniciar()
        resultado = self.orquestador.responder(self.historial, pregunta)
        if resultado.completo:
            self.historial.extend(resultado.mensajes_nuevos)
        return resultado

    def reiniciar(self) -> None:
        """Descarta todo el historial (comando /nueva)."""
        self.historial = []
