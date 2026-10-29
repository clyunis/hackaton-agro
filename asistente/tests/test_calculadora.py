"""Tests de CalculadoraNutrientes: cuentas verificables, sin LLM."""

import pytest

from agente.calculadora import CalculadoraNutrientes


@pytest.fixture
def calculadora():
    """Instancia nueva de la calculadora para cada test."""
    return CalculadoraNutrientes()


def test_aporte_de_nitrogeno_desde_urea(calculadora):
    """Caso del tutor: 200 kg/ha de urea al 46% de N aportan 92 kg N/ha."""
    resultado = calculadora.calcular_aporte(200, 46, "N")
    assert resultado["nutriente_kg_ha"] == pytest.approx(92.0)
    assert resultado["elemental_kg_ha"] == pytest.approx(92.0)
    assert "200" in resultado["formula"] and "92" in resultado["formula"]


def test_aporte_de_fosforo_expresado_como_p2o5(calculadora):
    """Caso del tutor: 150 kg/ha de un producto con 20% P2O5 aportan 30 kg P2O5 = 13,09 kg P."""
    resultado = calculadora.calcular_aporte(150, 20, "P2O5")
    assert resultado["nutriente_kg_ha"] == pytest.approx(30.0)
    assert resultado["elemental"] == "P"
    assert resultado["elemental_kg_ha"] == pytest.approx(13.09, abs=0.01)
    assert "0,4364" in resultado["formula"]


def test_aporte_de_potasio_expresado_como_k2o(calculadora):
    """100 kg/ha de cloruro de potasio (60% K2O) aportan 60 kg K2O = 49,8 kg K."""
    resultado = calculadora.calcular_aporte(100, 60, "K2O")
    assert resultado["elemental_kg_ha"] == pytest.approx(49.81, abs=0.01)


def test_dosis_de_urea_para_un_objetivo_de_nitrogeno(calculadora):
    """Para aportar 92 kg N/ha con urea (46% N) hacen falta 200 kg/ha de producto."""
    resultado = calculadora.calcular_dosis_producto(92, "N", 46, "N")
    assert resultado["dosis_producto_kg_ha"] == pytest.approx(200.0)


def test_dosis_de_map_para_un_objetivo_en_fosforo_elemental(calculadora):
    """Objetivo en P elemental con producto en P2O5: convierte antes de dividir."""
    resultado = calculadora.calcular_dosis_producto(20, "P", 52, "P2O5")
    # 20 kg P / 0,4364 = 45,83 kg P2O5 ; / 0,52 = 88,13 kg/ha de MAP
    assert resultado["dosis_producto_kg_ha"] == pytest.approx(88.13, abs=0.05)


def test_rechaza_porcentaje_fuera_de_rango(calculadora):
    """Un porcentaje de 0 o mayor a 100 no es un grado de fertilizante valido."""
    with pytest.raises(ValueError):
        calculadora.calcular_aporte(100, 0, "N")
    with pytest.raises(ValueError):
        calculadora.calcular_aporte(100, 120, "N")


def test_rechaza_nutrientes_incompatibles(calculadora):
    """No se puede pedir un objetivo de N con un producto expresado en P2O5."""
    with pytest.raises(ValueError):
        calculadora.calcular_dosis_producto(50, "N", 46, "P2O5")
