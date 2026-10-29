"""Bot de Telegram de AGRIA: cada chat tiene su conversacion con el orquestador agentico.

Long polling (no necesita URL publica/HTTPS, ideal para correr desde la notebook
durante el hackathon). El modelo de embeddings y el cliente de Claude se cargan
una sola vez al arrancar el proceso; el historial de cada chat vive en chat_data,
asi AGRIA puede repreguntar y usar la respuesta del ingeniero en el turno siguiente.
"""

import asyncio
import logging
import os
import re

import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

from agente.buscador_marbetes import BuscadorMarbetes  # despues de load_dotenv: lee CLAUDE_MODEL_AGENTE
from agente.orquestador import ConversacionAgro, OrquestadorAgro, ResultadoTurno

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG = 4000  # Telegram corta mensajes mas largos que ~4096 chars.

MENSAJE_BIENVENIDA = (
    "Hola, soy AGRIA. Contame tu consulta tecnica (productos, dosis, mezclas, calculos de "
    "fertilizantes). Si me faltan datos del lote te los voy a pedir. /nueva para empezar otra consulta."
)


def formatear_respuesta(resultado: ResultadoTurno) -> str:
    """Arma el texto final: respuesta + fuentes citadas con su extracto, sin pasarse del limite."""
    # Red de seguridad: si el modelo igual cuela markdown, lo limpiamos ya que
    # reply_text es texto plano y "**"/"##" se verian literalmente.
    texto = re.sub(r"^#{1,6}\s*", "", resultado.texto, flags=re.MULTILINE)
    texto = texto.replace("**", "").replace("__", "")
    texto_fuentes = ""
    if resultado.fuentes:
        lineas_fuentes = [
            f'[{fuente["etiqueta"]}] {fuente["producto"]} ({fuente["archivo"]}): "{fuente["extracto"]}..."'
            for fuente in resultado.fuentes_citadas()
        ]
        texto_fuentes = "\n\nFuentes:\n" + "\n".join(lineas_fuentes)
    # Se recorta la respuesta y no las fuentes: sin fuentes la respuesta no es verificable.
    texto_fuentes = texto_fuentes[: MAX_TELEGRAM_MSG // 2]
    return texto[: MAX_TELEGRAM_MSG - len(texto_fuentes)] + texto_fuentes


def obtener_conversacion(context: ContextTypes.DEFAULT_TYPE) -> ConversacionAgro:
    """Conversacion del chat actual; la crea la primera vez."""
    if "conversacion" not in context.chat_data:
        context.chat_data["conversacion"] = ConversacionAgro(context.application.bot_data["orquestador"])
    return context.chat_data["conversacion"]


async def responder_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de cada mensaje de texto recibido: corre un turno del orquestador y responde."""
    if not update.message or not update.message.text:
        return
    conversacion = obtener_conversacion(context)
    pregunta = update.message.text
    logger.info("Consulta recibida de %s: %s", update.effective_user.id, pregunta)
    await update.message.chat.send_action("typing")
    try:
        # En un thread para no bloquear el event loop mientras atiende a otros chats.
        resultado = await asyncio.to_thread(conversacion.consultar, pregunta)
        logger.info(
            "Tools usadas: %s | faltantes: %s",
            [herramienta["nombre"] for herramienta in resultado.herramientas_usadas],
            [faltante["clave"] for faltante in resultado.datos_faltantes],
        )
        await update.message.reply_text(formatear_respuesta(resultado))
    except Exception:
        logger.exception("Error respondiendo la consulta")
        await update.message.reply_text(
            "Hubo un error interno respondiendo tu consulta. Reintenta en un momento."
        )


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start: presentacion breve."""
    await update.message.reply_text(MENSAJE_BIENVENIDA)


async def nueva_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /nueva: descarta el historial del chat para arrancar otra consulta."""
    obtener_conversacion(context).reiniciar()
    await update.message.reply_text("Listo, arrancamos una consulta nueva.")


def main():
    """Carga el orquestador una sola vez y arranca el bot en long polling."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el .env")

    app = Application.builder().token(token).build()
    app.bot_data["orquestador"] = OrquestadorAgro(anthropic.Anthropic(), BuscadorMarbetes())
    app.add_handler(CommandHandler("start", iniciar))
    app.add_handler(CommandHandler("nueva", nueva_consulta))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_mensaje))

    logger.info("Bot arrancando (long polling, modelo %s)...", app.bot_data["orquestador"].modelo)
    app.run_polling()


if __name__ == "__main__":
    main()
