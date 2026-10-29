"""Tests de CatalogoRequisitos: que datos hacen falta segun el tipo de consulta."""

import pytest

from agente.requisitos import CLAVES_DATOS, CatalogoRequisitos


@pytest.fixture
def catalogo():
    """Instancia nueva del catalogo para cada test."""
    return CatalogoRequisitos()


def test_dosis_de_herbicida_sin_datos_pide_malezas_tamano_y_producto(catalogo):
    """Caso del tutor: 'dame dosis de glifosato para soja' tiene que pedir malezas, tamano y producto."""
    analisis = catalogo.analizar(
        "dosis_herbicida",
        [{"clave": "cultivo", "valor": "soja"}, {"clave": "producto_o_formulacion", "valor": ""}],
    )
    claves_faltantes = {faltante["clave"] for faltante in analisis["datos_faltantes_criticos"]}
    assert {"malezas_presentes", "tamano_malezas", "producto_o_formulacion"} <= claves_faltantes
    assert "cultivo" not in claves_faltantes
    assert analisis["datos_presentes"] == {"cultivo": "soja"}
    assert analisis["puede_responder"] is False


def test_dosis_de_herbicida_completa_puede_responder(catalogo):
    """Con todos los datos criticos, el analisis habilita la busqueda de evidencia."""
    analisis = catalogo.analizar(
        "dosis_herbicida",
        [
            {"clave": "cultivo", "valor": "soja"},
            {"clave": "etapa_o_momento", "valor": "barbecho"},
            {"clave": "malezas_presentes", "valor": "rama negra"},
            {"clave": "tamano_malezas", "valor": "roseta de 5 cm"},
            {"clave": "producto_o_formulacion", "valor": "glifosato sal potasica 62%"},
        ],
    )
    assert analisis["datos_faltantes_criticos"] == []
    assert analisis["puede_responder"] is True
    assert "buscar_marbetes" in analisis["herramientas_sugeridas"]


def test_criterio_del_tutor_sobre_glifosato_esta_en_el_catalogo(catalogo):
    """El criterio 'la dosis depende de malezas y tamano, no del antecesor' viaja al modelo."""
    analisis = catalogo.analizar("dosis_herbicida", [])
    criterios = " ".join(analisis["criterios"]).lower()
    assert "antecesor" in criterios
    assert "residual" in criterios


def test_fertilizacion_declara_la_limitacion_del_corpus(catalogo):
    """El corpus indexado no tiene modelos de fertilizacion: el analisis lo tiene que avisar."""
    analisis = catalogo.analizar("fertilizacion", [])
    assert analisis["limitaciones_corpus"]


def test_tipo_desconocido_falla(catalogo):
    """Un tipo de consulta fuera del catalogo es un error del llamador."""
    with pytest.raises(ValueError):
        catalogo.analizar("tipo_inventado", [])


def test_todos_los_requisitos_usan_claves_conocidas(catalogo):
    """Cada clave requerida tiene que existir en CLAVES_DATOS (es el enum de la tool)."""
    for tipo in catalogo.tipos_disponibles():
        for requisito in catalogo.requisitos_de(tipo):
            assert requisito["clave"] in CLAVES_DATOS
