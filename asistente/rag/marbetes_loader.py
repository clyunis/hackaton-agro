"""Carga el corpus de marbetes CASAFE (raw_data/descargas/11_casafe_guia_marbetes).

Cada PDF de esa carpeta es un marbete (un producto/principio activo) ya separado
de la Guia Fitosanitaria CASAFE. catalogo_marbetes.csv trae metadata ya extraida
en un paso previo (titulo, marcas_comerciales, uso, cultivos_detectados,
relevante_tandil), pero el campo "titulo" esta mal en ~120 filas: el extractor
tomo el encabezado de pagina de la guia ("Versión Digital de la Guía ...") en vez
del nombre real del producto. Este modulo arregla eso leyendo el texto del PDF
y usa pdftotext (ya instalado en el sistema) en vez de una libreria de PDF en
Python, porque es mas rapido y no agrega una dependencia nueva solo para esto.
"""

import csv
import re
import subprocess
from pathlib import Path

MARBETES_DIR = Path("../raw_data/descargas/11_casafe_guia_marbetes")
CATALOGO_CSV = MARBETES_DIR / "catalogo_marbetes.csv"
SOURCE_TYPE = "marbete_casafe"
CORPUS_PATH = "data/marbetes_corpus.jsonl"

# Lineas de encabezado/pie de pagina de la guia que no son el nombre del producto.
_BOILERPLATE_PATTERNS = re.compile(
    r"versi[oó]n digital|casafe|ley 11\.?723|prohibida su reproducci[oó]n|^isbn|^\s*$",
    re.IGNORECASE,
)


def extract_text(pdf_path: Path) -> str:
    """Extrae el texto completo de un PDF con pdftotext -layout (preserva tablas)."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def extract_real_titulo(text: str, fallback: str) -> str:
    """Encuentra el nombre real del producto, saltando el encabezado de la guia.

    Heuristica: la primera linea no vacia que no sea boilerplate de la guia.
    Si no se encuentra ninguna, devuelve el fallback (titulo del catalogo CSV).
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _BOILERPLATE_PATTERNS.search(stripped):
            continue
        return stripped
    return fallback


def load_catalogo(csv_path: Path = CATALOGO_CSV) -> list[dict]:
    """Lee catalogo_marbetes.csv tal cual viene del scraping previo."""
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_marbetes(marbetes_dir: Path = MARBETES_DIR, solo_relevante_tandil: bool = True) -> list[dict]:
    """Devuelve una lista de docs {"page_content", "metadata"}, uno por marbete.

    Cada doc tiene el texto completo del PDF (no partido por pagina, a diferencia
    del patron original para papers: un marbete tiene 1-3 paginas y partirlo por
    pagina cortaria la tabla de dosis a la mitad). El chunking real pasa despues,
    en el pipeline de ingesta.
    """
    catalogo = load_catalogo(marbetes_dir / "catalogo_marbetes.csv")
    docs = []
    skipped = []
    for row in catalogo:
        if solo_relevante_tandil and row["relevante_tandil"] != "True":
            continue
        pdf_path = marbetes_dir / row["archivo"]
        if not pdf_path.exists():
            skipped.append(row["archivo"])
            continue
        try:
            text = extract_text(pdf_path)
        except subprocess.CalledProcessError:
            skipped.append(row["archivo"])
            continue
        if not text.strip():
            skipped.append(row["archivo"])
            continue
        titulo_real = extract_real_titulo(text, fallback=row["titulo"])
        cultivos = [c.strip() for c in row["cultivos_detectados"].split(";") if c.strip()]
        docs.append(
            {
                "page_content": text,
                "metadata": {
                    "id": f"{SOURCE_TYPE}:{row['id']}",
                    "source_type": SOURCE_TYPE,
                    "source": row["archivo"],
                    "producto": titulo_real,
                    "titulo_catalogo_original": row["titulo"],
                    "marcas_comerciales": row["marcas_comerciales"],
                    "uso": row["uso"],
                    "cultivos": cultivos,
                    "relevante_tandil": row["relevante_tandil"] == "True",
                },
            }
        )
    if skipped:
        print(f"Marbetes salteados (no encontrados o sin texto): {len(skipped)}")
    return docs
