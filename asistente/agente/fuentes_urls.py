"""Mapea el archivo local de cada fuente descargada a la URL de donde se bajo.

Lee raw_data/descargas/manifest_urls.tsv (ruta_relativa<TAB>url por linea, ver su propio
README) una sola vez. Le permite al orquestador mostrarle al ingeniero un link a la pagina
de origen (CASAFE, SENASA) en las fuentes citadas, en vez de nombrar un archivo local que
no le dice nada y que de todos modos no tiene sentido fuera de esta maquina.
"""

from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
RUTA_MANIFEST = RAIZ_REPO / "raw_data" / "descargas" / "manifest_urls.tsv"
PREFIJO_RAIZ_DESCARGAS = "raw_data/descargas/"


class MapaUrlsFuentes:
    """Busca la URL de origen de un archivo descargado, por ruta relativa o solo nombre."""

    def __init__(self, ruta_manifest: Path = RUTA_MANIFEST):
        self.url_por_ruta: dict[str, str] = {}
        self.url_por_nombre: dict[str, str] = {}
        if ruta_manifest.exists():
            for linea in ruta_manifest.read_text(encoding="utf-8").splitlines():
                if not linea.strip():
                    continue
                ruta_relativa, url = linea.split("\t", 1)
                self.url_por_ruta[ruta_relativa] = url
                self.url_por_nombre[Path(ruta_relativa).name] = url

    def buscar(self, archivo: str) -> str | None:
        """URL de origen para un 'archivo' tal como lo guarda cada fuente (ruta o solo nombre)."""
        archivo_sin_prefijo = archivo.removeprefix(PREFIJO_RAIZ_DESCARGAS)
        return self.url_por_ruta.get(archivo_sin_prefijo) or self.url_por_nombre.get(Path(archivo).name)


MAPA_URLS_FUENTES = MapaUrlsFuentes()
