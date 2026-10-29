"""Tests de MapaUrlsFuentes: resuelve el archivo local de una fuente a su URL de origen."""

from pathlib import Path

from agente.fuentes_urls import MapaUrlsFuentes


def escribir_manifiesto(tmp_path: Path) -> Path:
    """Manifiesto de prueba con una entrada de marbete y una de norma, como el real."""
    ruta = tmp_path / "manifest_urls.tsv"
    ruta.write_text(
        "11_casafe_guia_marbetes/0254_glifosato.pdf\thttps://guiaonline.casafe.org/documentos/254.pdf\n"
        "01_senasa_rntv/res_senasa_414_2021_clorpirifos.pdf\thttps://argentina.gob.ar/res414.pdf\n",
        encoding="utf-8",
    )
    return ruta


def test_busca_por_solo_nombre_de_archivo(tmp_path):
    """Un marbete llega como 'archivo' con solo el nombre (sin carpeta): igual se resuelve."""
    mapa = MapaUrlsFuentes(escribir_manifiesto(tmp_path))

    assert mapa.buscar("0254_glifosato.pdf") == "https://guiaonline.casafe.org/documentos/254.pdf"


def test_busca_por_ruta_relativa_con_prefijo_raw_data(tmp_path):
    """Una norma llega como 'raw_data/descargas/01_senasa_rntv/archivo.pdf': se le saca el prefijo."""
    mapa = MapaUrlsFuentes(escribir_manifiesto(tmp_path))

    url = mapa.buscar("raw_data/descargas/01_senasa_rntv/res_senasa_414_2021_clorpirifos.pdf")

    assert url == "https://argentina.gob.ar/res414.pdf"


def test_archivo_desconocido_devuelve_none(tmp_path):
    """Si el archivo no esta en el manifiesto (ej. uno nuevo sin registrar), no inventa una URL."""
    mapa = MapaUrlsFuentes(escribir_manifiesto(tmp_path))

    assert mapa.buscar("archivo_que_no_existe.pdf") is None


def test_manifiesto_inexistente_no_rompe(tmp_path):
    """Si todavia no se descargo nada (manifiesto ausente), buscar() siempre devuelve None."""
    mapa = MapaUrlsFuentes(tmp_path / "no_existe.tsv")

    assert mapa.buscar("0254_glifosato.pdf") is None
