"""Bot de Telegram de AGRIA: cada chat tiene su conversacion con el orquestador agentico.

Long polling (no necesita URL publica/HTTPS, ideal para correr desde la notebook
durante el hackathon). El modelo de embeddings, el cliente de Claude y el transcriptor
de voz se cargan una sola vez al arrancar el proceso; el historial de cada chat vive en
chat_data, asi AGRIA puede repreguntar y usar la respuesta del ingeniero en el turno siguiente.
"""

import asyncio
import contextlib
import logging
import os
import re
import tempfile
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

from agente.buscador_marbetes import BuscadorMarbetes  # despues de load_dotenv: lee CLAUDE_MODEL_AGENTE
from agente.orquestador import ConversacionAgro, OrquestadorAgro, ResultadoTurno
from agente.transcriptor import TranscriptorVoz

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG = 4000  # Telegram corta mensajes mas largos que ~4096 chars.
# Telegram vuelve a mostrar "escribiendo..." por unos 5s por cada aviso: se repite antes de que
# se corte, porque el orquestador (varias llamadas a herramientas) puede tardar mucho mas que eso.
INTERVALO_AVISO_ESCRIBIENDO_S = 4

MENSAJE_BIENVENIDA = (
    "Hola, soy AGRIA. Contame tu consulta tecnica (productos, dosis, mezclas, calculos de "
    "fertilizantes), escrita o por audio. Si me faltan datos del lote te los voy a pedir. "
    "/nueva para empezar otra consulta."
)
MENSAJE_AUDIO_SIN_VOZ = (
    "No llegue a entender nada en el audio. Probá de nuevo mas cerca del microfono o escribila."
)
MENSAJE_ERROR_TRANSCRIPCION = "No pude procesar el audio. Probá de nuevo o escribi la consulta."


def formatear_respuesta(resultado: ResultadoTurno) -> str:
    """Arma el texto final: respuesta + una lista corta de fuentes citadas, sin pasarse del limite."""
    # Red de seguridad: si el modelo igual cuela markdown, lo limpiamos ya que
    # reply_text es texto plano y "**"/"##" se verian literalmente.
    texto = re.sub(r"^#{1,6}\s*", "", resultado.texto, flags=re.MULTILINE)
    texto = texto.replace("**", "").replace("__", "")
    texto_fuentes = ""
    if resultado.fuentes:
        # Una linea por fuente: producto + link a la pagina de origen (o el organismo si no
        # hay link). Nada de archivos locales ni del extracto completo: eso es ruido en Telegram.
        lineas_fuentes = [
            f'[{fuente["etiqueta"]}] {fuente["producto"]}: {fuente["referencia"]}'
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


async def avisar_escribiendo_mientras_tanto(chat) -> None:
    """Repite la accion 'escribiendo...' hasta que la cancelen (el turno puede tardar bastante)."""
    while True:
        await chat.send_action("typing")
        await asyncio.sleep(INTERVALO_AVISO_ESCRIBIENDO_S)


async def procesar_pregunta(update: Update, context: ContextTypes.DEFAULT_TYPE, pregunta: str) -> None:
    """Corre un turno del orquestador para 'pregunta' (venga de texto o de audio) y responde."""
    conversacion = obtener_conversacion(context)
    logger.info("Consulta recibida de %s: %s", update.effective_user.id, pregunta)
    tarea_escribiendo = asyncio.create_task(avisar_escribiendo_mientras_tanto(update.message.chat))
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
    finally:
        tarea_escribiendo.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea_escribiendo


async def responder_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de cada mensaje de texto recibido."""
    if not update.message or not update.message.text:
        return
    await procesar_pregunta(update, context, update.message.text)


async def responder_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de notas de voz/audio: transcribe, muestra lo entendido y sigue como si fuera texto.

    El eco de la transcripcion importa en este bot mas que en uno generico: si Whisper confunde
    un nombre de principio activo (ej. "clorpirifos" por otra cosa), el ingeniero lo nota antes
    de que AGRIA responda sobre un producto equivocado.
    """
    if not update.message or not (update.message.voice or update.message.audio):
        return
    await update.message.chat.send_action("typing")
    archivo_audio = update.message.voice or update.message.audio
    transcriptor: TranscriptorVoz = context.application.bot_data["transcriptor"]
    with tempfile.NamedTemporaryFile(suffix=".ogg") as temporal:
        try:
            archivo = await archivo_audio.get_file()
            await archivo.download_to_drive(custom_path=temporal.name)
            texto = await asyncio.to_thread(transcriptor.transcribir, temporal.name)
        except Exception:
            logger.exception("Error transcribiendo el audio")
            await update.message.reply_text(MENSAJE_ERROR_TRANSCRIPCION)
            return
    if not texto:
        await update.message.reply_text(MENSAJE_AUDIO_SIN_VOZ)
        return
    await update.message.reply_text(f'🎤 Entendí: "{texto}"')
    await procesar_pregunta(update, context, texto)


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start: presentacion breve."""
    await update.message.reply_text(MENSAJE_BIENVENIDA)


async def nueva_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /nueva: descarta el historial del chat para arrancar otra consulta."""
    obtener_conversacion(context).reiniciar()
    await update.message.reply_text("Listo, arrancamos una consulta nueva.")


def main():
    """Carga el orquestador y el transcriptor una sola vez y arranca el bot en long polling."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el .env")

    app = Application.builder().token(token).build()
    app.bot_data["orquestador"] = OrquestadorAgro(anthropic.Anthropic(), BuscadorMarbetes())
    app.bot_data["transcriptor"] = TranscriptorVoz()
    app.add_handler(CommandHandler("start", iniciar))
    app.add_handler(CommandHandler("nueva", nueva_consulta))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_mensaje))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, responder_audio))

    logger.info("Bot arrancando (long polling, modelo %s)...", app.bot_data["orquestador"].modelo)
    app.run_polling()


if __name__ == "__main__":
    main()
