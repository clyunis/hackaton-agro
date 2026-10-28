"""Bot de Telegram: mismo pipeline de scripts/ask.py, servido por mensajes en vez de stdin.

Long polling (no necesita URL publica/HTTPS, ideal para correr desde la notebook
durante el hackathon). El modelo de embeddings y el cliente de Claude se cargan
una sola vez al arrancar el proceso (AsistenteAgro.__init__), no por mensaje.
"""

import logging
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from scripts.ask import AsistenteAgro

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG = 4000  # Telegram corta mensajes mas largos que ~4096 chars.


def formatear_respuesta(resultado: dict) -> str:
    """Arma el texto final: respuesta + lista de fuentes citadas."""
    # Red de seguridad: si el modelo igual cuela markdown, lo limpiamos ya que
    # reply_text es texto plano y "**"/"##" se verian literalmente.
    texto = re.sub(r"^#{1,6}\s*", "", resultado["respuesta"], flags=re.MULTILINE)
    texto = texto.replace("**", "").replace("__", "")
    if resultado["fuentes"]:
        lineas_fuentes = [
            f"  {i}. {c['metadata'].get('producto')} ({c['metadata'].get('source')})"
            for i, c in enumerate(resultado["fuentes"], start=1)
        ]
        texto += "\n\nFuentes consultadas:\n" + "\n".join(lineas_fuentes)
    return texto[:MAX_TELEGRAM_MSG]


async def responder_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de cada mensaje de texto recibido: corre el pipeline RAG y responde."""
    if not update.message or not update.message.text:
        return
    asistente: AsistenteAgro = context.application.bot_data["asistente"]
    pregunta = update.message.text
    logger.info("Consulta recibida de %s: %s", update.effective_user.id, pregunta)
    await update.message.chat.send_action("typing")
    try:
        resultado = asistente.responder(pregunta)
        await update.message.reply_text(formatear_respuesta(resultado))
    except Exception:
        logger.exception("Error respondiendo la consulta")
        await update.message.reply_text(
            "Hubo un error interno respondiendo tu consulta. Reintenta en un momento."
        )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el .env")

    app = Application.builder().token(token).build()
    app.bot_data["asistente"] = AsistenteAgro()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_mensaje))

    logger.info("Bot arrancando (long polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
