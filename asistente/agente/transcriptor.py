"""Transcripcion de audio a texto para los mensajes de voz del bot de Telegram.

Separado del resto del orquestador por el mismo motivo que agente/buscador_marbetes.py:
que los tests no tengan que cargar un modelo pesado (Whisper, GPU real).

Precarga de libcublas/libcudnn: faster-whisper (via ctranslate2) busca esas librerias de
CUDA por nombre con dlopen al transcribir. En este venv solo estan instaladas como paquetes
de pip de PyTorch (nvidia-cublas-cu12, nvidia-cudnn-cu12), no en una ruta de sistema ni en
LD_LIBRARY_PATH, asi que ese dlopen por nombre falla ("Library libcublas.so.12 is not found").
Cargarlas explicitamente con ctypes por su ruta completa, antes de importar ctranslate2, las
deja ya mapeadas en el proceso: el dlopen por nombre que hace despues ctranslate2 las encuentra.
Si el paquete no esta instalado (maquina sin GPU) no rompe nada: WhisperModel cae a CPU.
"""

import ctypes
import importlib.util
import logging
from pathlib import Path

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

MODELO_WHISPER_POR_DEFECTO = "small"
IDIOMA_POR_DEFECTO = "es"

# (paquete pip, archivo .so dentro de ese paquete) en el orden en que se necesitan cargar.
LIBRERIAS_CUDA_A_PRECARGAR = [
    ("nvidia.cublas", "lib/libcublasLt.so.12"),
    ("nvidia.cublas", "lib/libcublas.so.12"),
    ("nvidia.cudnn", "lib/libcudnn_ops.so.9"),
    ("nvidia.cudnn", "lib/libcudnn_cnn.so.9"),
    ("nvidia.cudnn", "lib/libcudnn.so.9"),
]


def precargar_librerias_cuda() -> None:
    """Mapea libcublas/libcudnn del venv en el proceso para que ctranslate2 las encuentre."""
    for paquete, archivo_relativo in LIBRERIAS_CUDA_A_PRECARGAR:
        especificacion = importlib.util.find_spec(paquete)
        if not especificacion or not especificacion.submodule_search_locations:
            continue
        ruta = Path(next(iter(especificacion.submodule_search_locations))) / archivo_relativo
        try:
            ctypes.CDLL(str(ruta), mode=ctypes.RTLD_GLOBAL)
        except OSError:
            logger.debug("No se pudo precargar %s (puede no hacer falta en esta maquina)", ruta)


precargar_librerias_cuda()


class TranscriptorVoz:
    """Transcribe un archivo de audio a texto en espanol con un modelo Whisper local."""

    def __init__(self, modelo: str = MODELO_WHISPER_POR_DEFECTO):
        self.modelo = self._cargar_modelo(modelo)

    def _cargar_modelo(self, modelo: str) -> WhisperModel:
        """Intenta GPU y, si no esta disponible, cae a CPU sin romper el arranque del bot."""
        try:
            return WhisperModel(modelo, device="auto", compute_type="default")
        except Exception:
            logger.warning("No se pudo cargar Whisper con device='auto', forzando CPU.", exc_info=True)
            return WhisperModel(modelo, device="cpu", compute_type="int8")

    def transcribir(self, ruta_audio: str) -> str:
        """Texto transcripto en espanol de un archivo de audio (vacio si no detecta voz)."""
        segmentos, _info = self.modelo.transcribe(ruta_audio, language=IDIOMA_POR_DEFECTO)
        return " ".join(segmento.text.strip() for segmento in segmentos).strip()
