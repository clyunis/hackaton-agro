"""Tests de RegistroFuentes: cada fuente registrada trae una 'referencia' corta citable."""

from agente.herramientas import RegistroFuentes


def test_marbete_real_resuelve_su_url_de_casafe():
    """0254_glifosato.pdf esta en el manifiesto real: la referencia es el link a guiaonline.casafe.org."""
    registro = RegistroFuentes()
    fragmento = {
        "id": "marbete_casafe:254_chunk_0",
        "producto": "GLIFOSATO",
        "archivo": "0254_glifosato.pdf",
        "contenido": "Producto: GLIFOSATO\n---\nSoja  Rama negra  PC 62%: 2 l/ha",
    }

    fuente = registro.registrar(fragmento)

    assert fuente["referencia"] == "https://guiaonline.casafe.org/documentos/254.pdf"


def test_norma_real_resuelve_su_url_de_senasa():
    """res_senasa_414_2021_clorpirifos.pdf esta en el manifiesto: la referencia es el link oficial."""
    registro = RegistroFuentes()
    restriccion = {
        "principio_activo": "CLORPIRIFOS",
        "norma": "Res. SENASA 414/2021",
        "articulo": "Art. 3",
        "archivo": "raw_data/descargas/01_senasa_rntv/res_senasa_414_2021_clorpirifos.pdf",
        "texto": "Se prohibe la comercializacion y uso de clorpirifos.",
    }

    fuente = registro.registrar_norma(restriccion)

    assert fuente["referencia"].startswith("https://www.argentina.gob.ar/")


def test_archivo_sin_url_conocida_nombra_el_organismo_no_el_archivo():
    """Un marbete que no esta en el manifiesto cae al nombre del organismo, nunca al archivo local."""
    registro = RegistroFuentes()
    fragmento = {
        "id": "marbete_casafe:9999_chunk_0",
        "producto": "PRODUCTO INEXISTENTE",
        "archivo": "9999_no_esta_en_el_manifiesto.pdf",
        "contenido": "Producto: PRODUCTO INEXISTENTE\n---\nSoja  Test  1 l/ha",
    }

    fuente = registro.registrar(fragmento)

    assert fuente["referencia"] == "Guia CASAFE"
    assert "9999_no_esta_en_el_manifiesto.pdf" not in fuente["referencia"]


def test_clima_no_tiene_url_y_nombra_open_meteo():
    """El clima no viene de un archivo descargado: la referencia siempre es el nombre del organismo."""
    registro = RegistroFuentes()
    datos_clima = {
        "ubicacion": "Tandil, Buenos Aires (-37.3217, -59.1332)",
        "fuente": "Open-Meteo (api.open-meteo.com), modelo meteorologico, no estacion propia de Tandil",
        "actualizado": "2026-10-29T15:00",
        "condiciones_actuales": {"temperatura_c": 18.5, "viento_kmh": 10.0},
    }

    fuente = registro.registrar_clima(datos_clima)

    assert fuente["referencia"] == "Open-Meteo"
