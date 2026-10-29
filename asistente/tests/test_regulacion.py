"""Tests del verificador regulatorio SENASA (registro CSV + tabla de prohibiciones)."""

import pytest

from agente.regulacion import (
    RUTA_PRODUCTOS_FORMULADOS,
    RegistroSenasa,
    VerificadorRegulatorio,
    normalizar_nombre,
    separar_activos,
)

CSV_DE_PRUEBA = (
    "﻿N° registro;Marca;Empresa;Activos;Banda tox; \n"
    '"SE-007";"TERFOS 48";"CHEMOTECNICA S. A.";"CLORPIRIFOS 48%";"II";\n'
    '"ST-T-101301";"GLYFONEX 72 SG";"RAINBOW AGROSCIENSES SA";"GLIFOSATO 79,2% p/p";"No Clasificado";\n'
    '"42347";"FLAULEN";"RAINBOW AGROSCIENSES SA";"ETIPROLE 35%, FIPRONIL 25%";"II";\n'
    '"42680";"FULLIST";"INSUMOS AGROQUIMICOS SA";"2,4 D 12,5%, GLUFOSINATO DE AMONIO 12,5%";"S/D";\n'
)


@pytest.fixture
def verificador(tmp_path):
    """Verificador sobre un CSV chico con el mismo formato que el de SENASA."""
    ruta_csv = tmp_path / "productos.csv"
    ruta_csv.write_text(CSV_DE_PRUEBA, encoding="utf-8")
    return VerificadorRegulatorio(RegistroSenasa(ruta_csv))


def test_normalizar_nombre_saca_tildes_puntos_y_signos():
    """Los nombres se comparan sin tildes, mayusculas ni signos."""
    assert normalizar_nombre("Clorpirifós") == "CLORPIRIFOS"
    assert normalizar_nombre("D.D.T.") == "DDT"
    assert normalizar_nombre("2,4-D") == "2 4 D"


@pytest.mark.parametrize(
    "activos, esperados",
    [
        ("ETIPROLE 35%, FIPRONIL 25%", ["ETIPROLE", "FIPRONIL"]),
        ("2,4 D 12,5%, GLUFOSINATO DE AMONIO 12,5%", ["2,4 D", "GLUFOSINATO DE AMONIO"]),
        ("FIPRONIL ,003%", ["FIPRONIL"]),
        ("CLETODIM 24% p/v, QUIZALOFOP-P ETIL 12% p/v", ["CLETODIM", "QUIZALOFOP-P ETIL"]),
    ],
)
def test_separar_activos_respeta_comas_decimales(activos, esperados):
    """La coma separa activos, pero tambien aparece en '2,4 D' y en concentraciones."""
    assert separar_activos(activos) == esperados


def test_clorpirifos_esta_prohibido_por_la_414(verificador):
    """El caso que motivo la tool: el marbete CASAFE es anterior a la prohibicion."""
    resultado = verificador.verificar("clorpirifós")
    assert resultado["restricciones"][0]["estado"] == "prohibido"
    assert resultado["restricciones"][0]["norma"] == "Res. SENASA 414/2021"
    assert resultado["restricciones"][0]["articulo"] == "Art. 3"
    assert resultado["conclusion"].startswith("PROHIBIDO")


def test_marca_registrada_con_activo_prohibido(verificador):
    """Que una marca figure en el CSV del registro no la vuelve legal."""
    resultado = verificador.verificar("Terfos 48")
    assert resultado["productos_registrados"]["cantidad"] == 1
    assert resultado["conclusion"].startswith("PROHIBIDO")


def test_glifosato_registrado_sin_prohibiciones(verificador):
    """Activo registrado y fuera de la tabla de prohibiciones."""
    resultado = verificador.verificar("glifosato")
    assert resultado["restricciones"] == []
    assert resultado["productos_registrados"]["cantidad"] == 1
    assert "sin prohibiciones" in resultado["conclusion"]


def test_fipronil_prohibido_solo_en_sc_y_wg(verificador):
    """La 425/2021 alcanza solo a las formulaciones SC y WG."""
    resultado = verificador.verificar("fipronil")
    assert resultado["restricciones"][0]["estado"] == "prohibido_parcial"
    assert "SC" in resultado["restricciones"][0]["alcance"]


def test_carbofuran_tiene_excepcion_y_restriccion(verificador):
    """Carbofuran: prohibido salvo granulado 10% (263/2018 y 670/2018) y restringido en Anexo II."""
    estados = {r["estado"] for r in verificador.verificar("carbofuran")["restricciones"]}
    assert estados == {"prohibido_parcial", "uso_restringido"}


def test_2_4_d_en_sal_o_ester_etilhexilico_no_alerta(verificador):
    """La 466/2019 alcanza solo esteres butilicos e isobutilicos de 2,4-D."""
    assert verificador.alerta_para_producto("2,4 D SAL COLINA") is None
    assert verificador.alerta_para_producto("2,4 D ESTER ETILEXILICO") is None
    assert "PARCIAL" in verificador.alerta_para_producto("2,4 D ESTER")


def test_anexo_i_de_la_32_2019(verificador):
    """Los activos del Anexo I de la Res. 32/2019 salen como prohibidos."""
    resultado = verificador.verificar("paration metil")
    assert resultado["restricciones"][0]["norma"] == "Res. SENASA 32/2019 Anexo I"


def test_etil_azinfos_no_confunde_con_etion_ni_metil_azinfos(verificador):
    """La coincidencia es por palabras completas, no por substring."""
    normas = [r["principio_activo"] for r in verificador.verificar("etil azinfos")["restricciones"]]
    assert normas == ["ETIL AZINFOS"]


def test_producto_no_encontrado_no_se_da_por_legal(verificador):
    """Sin registro ni restricciones, la conclusion es que no se puede confirmar."""
    resultado = verificador.verificar("producto inventado xyz")
    assert resultado["productos_registrados"]["cantidad"] == 0
    assert "No se encontro" in resultado["conclusion"]


def test_alerta_para_producto_de_marbete(verificador):
    """Los titulos de marbete combinados ('A + B') se chequean activo por activo."""
    alerta = verificador.alerta_para_producto("CIPERMETRINA + CLORPIRIFOS")
    assert "PROHIBIDO" in alerta and "414/2021" in alerta
    assert verificador.alerta_para_producto("GLIFOSATO") is None


def test_csv_real_del_repo_carga():
    """El CSV descargado de SENASA se parsea completo (unas 7.500 filas)."""
    registro = RegistroSenasa(RUTA_PRODUCTOS_FORMULADOS)
    assert len(registro.productos) > 7000
