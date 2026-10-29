"""Tests de ClienteClima y ClienteClimatologiaHistorica con un cliente HTTP falso (sin red)."""

import pytest

from agente.clima import ClienteClima, ClienteClimatologiaHistorica

RESPUESTA_OPEN_METEO_DE_PRUEBA = {
    "current": {
        "time": "2026-10-29T15:00",
        "temperature_2m": 18.5,
        "relative_humidity_2m": 55,
        "precipitation": 0.0,
        "wind_speed_10m": 10.0,
        "wind_gusts_10m": 18.0,
        "wind_direction_10m": 200,
    },
    "daily": {
        "time": ["2026-10-29", "2026-10-30", "2026-10-31"],
        "temperature_2m_max": [22.0, 23.1, 10.0],
        "temperature_2m_min": [10.0, 2.5, -1.0],
        "precipitation_sum": [0.0, 5.0, 0.0],
        "precipitation_probability_max": [10, 80, 5],
        "wind_speed_10m_max": [20.0, 8.0, 2.0],
        "wind_gusts_10m_max": [35.0, 15.0, 5.0],
        "et0_fao_evapotranspiration": [4.2, 3.0, 2.0],
    },
}


class ClienteHttpFalso:
    """Devuelve siempre el mismo cuerpo de respuesta y registra la URL/parametros pedidos."""

    def __init__(self, cuerpo=RESPUESTA_OPEN_METEO_DE_PRUEBA):
        self.cuerpo = cuerpo
        self.pedidos = []

    def obtener_json(self, url, parametros):
        """Simula ClienteHttpClima.obtener_json."""
        self.pedidos.append((url, parametros))
        return self.cuerpo


def test_consultar_pide_coordenadas_de_tandil_y_limita_los_dias():
    """La URL pedida usa las coordenadas de Tandil y recorta forecast_days al maximo permitido."""
    cliente_http = ClienteHttpFalso()
    cliente_clima = ClienteClima(cliente_http)

    cliente_clima.consultar(dias_pronostico=30)

    _, parametros = cliente_http.pedidos[0]
    assert parametros["latitude"] == -37.3217
    assert parametros["longitude"] == -59.1332
    assert parametros["forecast_days"] == 7


def test_condiciones_actuales_se_parsean_a_espanol():
    """El bloque 'current' de Open-Meteo se normaliza a los nombres de campo del prototipo."""
    datos = ClienteClima(ClienteHttpFalso()).consultar()
    actuales = datos["condiciones_actuales"]
    assert actuales["temperatura_c"] == 18.5
    assert actuales["viento_kmh"] == 10.0
    assert actuales["humedad_relativa_pct"] == 55


def test_dia_sin_riesgo_y_con_viento_en_ventana_queda_apto():
    """Dia 0: minima 10 C (sin riesgo) pero viento max 20 km/h, fuera de la ventana de aplicacion."""
    pronostico = ClienteClima(ClienteHttpFalso()).consultar()["pronostico_diario"]
    assert pronostico[0]["riesgo_helada"] == "sin_riesgo"
    assert pronostico[0]["apto_para_aplicar"] is False


def test_dia_con_riesgo_de_helada_y_alta_probabilidad_de_lluvia():
    """Dia 1: minima 2,5 C (riesgo de helada) y 80% de probabilidad de lluvia: no apto para aplicar."""
    pronostico = ClienteClima(ClienteHttpFalso()).consultar()["pronostico_diario"]
    assert pronostico[1]["riesgo_helada"] == "riesgo_helada"
    assert pronostico[1]["apto_para_aplicar"] is False


def test_dia_con_helada_probable_y_viento_insuficiente():
    """Dia 2: minima -1 C (helada probable) y viento max 2 km/h, por debajo del minimo para aplicar."""
    pronostico = ClienteClima(ClienteHttpFalso()).consultar()["pronostico_diario"]
    assert pronostico[2]["riesgo_helada"] == "helada_probable"
    assert pronostico[2]["apto_para_aplicar"] is False


def test_alertas_agronomicas_listan_los_dias_con_riesgo_de_helada():
    """Las alertas incluyen un mensaje por cada dia con riesgo de helada u helada probable."""
    alertas = ClienteClima(ClienteHttpFalso()).consultar()["alertas_agronomicas"]
    assert any("2026-10-30" in alerta and "riesgo_helada" in alerta for alerta in alertas)
    assert any("2026-10-31" in alerta and "helada_probable" in alerta for alerta in alertas)


def test_viento_actual_fuera_de_ventana_genera_alerta():
    """El viento actual (10 km/h) esta dentro de la ventana: no debe generar alerta de viento."""
    alertas = ClienteClima(ClienteHttpFalso()).consultar()["alertas_agronomicas"]
    assert not any("Viento actual" in alerta for alerta in alertas)


def test_resultado_incluye_limitaciones_y_fuente():
    """Todo resultado declara que es un modelo (no una estacion oficial) y sus limitaciones."""
    datos = ClienteClima(ClienteHttpFalso()).consultar()
    assert "Open-Meteo" in datos["fuente"]
    assert "SIGA" in datos["limitaciones"] or "INTA" in datos["limitaciones"]


class ClienteHttpMultiplexado:
    """Devuelve un cuerpo distinto segun que parte de la URL matchea (geocoding vs forecast/archive)."""

    def __init__(self, respuestas: dict):
        self.respuestas = respuestas
        self.pedidos = []

    def obtener_json(self, url, parametros):
        """Busca la primera clave que sea substring de la URL pedida."""
        self.pedidos.append((url, parametros))
        for clave, cuerpo in self.respuestas.items():
            if clave in url:
                return cuerpo
        raise AssertionError(f"URL inesperada en el test: {url}")

    def pedido_a(self, parte_de_url):
        """Parametros del primer pedido cuya URL contiene esa parte."""
        return next(parametros for url, parametros in self.pedidos if parte_de_url in url)


RESPUESTA_GEOCODING_RAUCH = {
    "results": [{"name": "Rauch", "latitude": -36.78, "longitude": -59.09, "admin1": "Buenos Aires"}]
}


def test_zona_o_partido_resuelve_coordenadas_por_geocoding():
    """Si se pide un partido, consultar_clima pega al geocodificador y usa esas coordenadas."""
    cliente_http = ClienteHttpMultiplexado(
        {"geocoding": RESPUESTA_GEOCODING_RAUCH, "forecast": RESPUESTA_OPEN_METEO_DE_PRUEBA}
    )
    datos = ClienteClima(cliente_http).consultar(zona_o_partido="Rauch")

    pedido_forecast = cliente_http.pedido_a("forecast")
    assert pedido_forecast["latitude"] == -36.78
    assert pedido_forecast["longitude"] == -59.09
    assert "Rauch" in datos["ubicacion"]
    assert datos["alertas_agronomicas"].count(
        "No se encontro 'Rauch'; se uso Tandil, Buenos Aires como referencia."
    ) == 0


def test_zona_o_partido_no_encontrada_cae_a_tandil_con_aviso():
    """Si el geocodificador no encuentra el lugar, se usa Tandil y queda un aviso en las alertas."""
    cliente_http = ClienteHttpMultiplexado({"geocoding": {"results": []}, "forecast": RESPUESTA_OPEN_METEO_DE_PRUEBA})
    datos = ClienteClima(cliente_http).consultar(zona_o_partido="LugarInventadoXYZ")

    assert "Tandil" in datos["ubicacion"]
    assert any("LugarInventadoXYZ" in alerta for alerta in datos["alertas_agronomicas"])


RESPUESTA_HISTORICA_DE_PRUEBA = {
    "daily": {
        "time": ["2024-04-30", "2024-05-01", "2024-05-02", "2024-05-03", "2025-05-01", "2025-05-02"],
        "temperature_2m_max": [20.0, 18.0, 19.0, 17.0, 22.0, 21.0],
        "temperature_2m_min": [8.0, 1.0, -1.0, 5.0, 9.0, 10.0],
        "precipitation_sum": [0.0, 5.0, 0.0, 2.0, 0.0, 0.0],
    }
}


def test_climatologia_historica_agrupa_por_anio_el_mes_pedido():
    """Solo los dias de mayo entran en el resumen, agrupados por anio (abril 30 queda afuera)."""
    cliente_http = ClienteHttpFalso(RESPUESTA_HISTORICA_DE_PRUEBA)
    datos = ClienteClimatologiaHistorica(cliente_http).consultar(mes=5)

    anios = {anio["anio"]: anio for anio in datos["anios"]}
    assert set(anios) == {2024, 2025}
    assert anios[2024]["temp_max_promedio_c"] == pytest.approx(18.0)
    assert anios[2024]["precipitacion_total_mm"] == pytest.approx(7.0)
    assert anios[2024]["dias_con_helada"] == 1
    assert anios[2024]["dias_con_lluvia"] == 2
    assert anios[2025]["dias_con_helada"] == 0
    assert datos["mes_consultado"] == "mayo"


def test_climatologia_historica_calcula_el_promedio_entre_anios():
    """El promedio_historico es el promedio simple de cada indicador entre los anios devueltos."""
    cliente_http = ClienteHttpFalso(RESPUESTA_HISTORICA_DE_PRUEBA)
    datos = ClienteClimatologiaHistorica(cliente_http).consultar(mes=5)

    assert datos["promedio_historico"]["dias_con_helada"] == pytest.approx(0.5)
    assert datos["promedio_historico"]["precipitacion_total_mm"] == pytest.approx(3.5)


def test_climatologia_historica_mes_invalido_no_llama_a_la_red():
    """Un mes fuera de 1-12 falla antes de pegarle a ninguna API."""
    with pytest.raises(ValueError):
        ClienteClimatologiaHistorica(ClienteHttpFalso()).consultar(mes=13)


def test_climatologia_historica_usa_tandil_por_defecto():
    """Sin zona_o_partido, la climatologia historica tambien usa Tandil."""
    cliente_http = ClienteHttpFalso(RESPUESTA_HISTORICA_DE_PRUEBA)
    datos = ClienteClimatologiaHistorica(cliente_http).consultar(mes=5)
    assert "Tandil" in datos["ubicacion"]
