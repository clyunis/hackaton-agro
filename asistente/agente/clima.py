"""Clientes de datos meteorologicos (actuales, pronostico e historicos) via Open-Meteo.

Por que Open-Meteo y no las fuentes que trajo el equipo:
- weatherspark.com y cebadacervecera.com.ar/.../datos-clima-inta-balcarce son paginas estaticas
  con promedios climatologicos historicos. Utiles para lo que las usa el agronomo (ver si una
  campana es normal o entra en un patron que se repite cada varios anios), pero no consultables
  por codigo ni acotables a un mes o a un partido distinto. ClienteClimatologiaHistorica cubre
  ese mismo uso con la Archive API de Open-Meteo (reanalisis ERA5, datos diarios desde 1940,
  sin clave), consultable por mes/anios/partido.
- SIGA INTA (siga.inta.gob.ar) es la fuente oficial mas completa (red de estaciones INTA/
  extra-INTA), pero es una SPA sin API publica documentada: el unico acceso programatico
  conocido es un paquete R (AgRoMeteorologiaINTA/siga) que llama endpoints internos sin
  garantia de estabilidad. Queda anotado como candidato a integrar mas adelante, no para el
  prototipo.
- Open-Meteo (forecast, archive y geocoding) es publica, sin clave, estable, y cubre cualquier
  coordenada: no solo Tandil. Para un prototipo que necesita actualidad y estabilidad de API es
  la opcion mas pragmatica; no reemplaza a una estacion oficial.

Los umbrales agronomicos (riesgo de helada, ventana de aplicacion) son criterio general del
equipo, no vienen de un documento citable: el prompt del orquestador le pide al modelo
presentarlos como interpretacion propia, no como dato de fuente.
"""

import datetime
from dataclasses import dataclass

import httpx

URL_API_PRONOSTICO = "https://api.open-meteo.com/v1/forecast"
URL_API_HISTORICA = "https://archive-api.open-meteo.com/v1/archive"
URL_API_GEOCODIFICACION = "https://geocoding-api.open-meteo.com/v1/search"

LATITUD_TANDIL = -37.3217
LONGITUD_TANDIL = -59.1332
NOMBRE_TANDIL = "Tandil, Buenos Aires"
ZONA_HORARIA = "America/Argentina/Buenos_Aires"

DIAS_PRONOSTICO_POR_DEFECTO = 5
DIAS_PRONOSTICO_MAXIMO = 7
ANIOS_ATRAS_POR_DEFECTO = 10
ANIOS_ATRAS_MAXIMO = 20

VARIABLES_ACTUALES = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
VARIABLES_DIARIAS = (
    "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
    "wind_speed_10m_max,wind_gusts_10m_max,et0_fao_evapotranspiration"
)
VARIABLES_DIARIAS_HISTORICAS = "temperature_2m_max,temperature_2m_min,precipitation_sum"

NOMBRES_MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# Riesgo de helada en el PRONOSTICO: criterio general (no de una fuente citable) -- a temperatura
# de pronostico (2 m) igual o por debajo de este umbral ya hay riesgo, porque la temperatura a
# nivel de cultivo suele ser varios grados menor que la de pronostico.
UMBRAL_RIESGO_HELADA_C = 3.0
UMBRAL_HELADA_PROBABLE_C = 0.0
# Helada en un REGISTRO HISTORICO: el dato ya ocurrio, se cuenta con el umbral fisico (0 C),
# sin el margen de incertidumbre que se usa para el pronostico.
UMBRAL_HELADA_HISTORICA_C = 0.0
MM_LLUVIA_MINIMO_PARA_CONTAR_DIA = 0.1

# Ventana de viento habitualmente recomendada para pulverizar (evitar deriva con viento fuerte
# e inversion termica con viento muy debil). Criterio general, no de una fuente citable.
VIENTO_MINIMO_APLICACION_KMH = 3.0
VIENTO_MAXIMO_APLICACION_KMH = 15.0
PROBABILIDAD_LLUVIA_ALERTA_PCT = 50.0

LIMITACIONES_PRONOSTICO = (
    "Datos de un modelo meteorologico (Open-Meteo, grilla); no es la fuente oficial del SMN ni de "
    "la red agrometeorologica del INTA (SIGA, siga.inta.gob.ar), que no tiene una API publica "
    "documentada para este prototipo. Los umbrales de riesgo de helada y de ventana de aplicacion "
    "son criterio agronomico general del equipo, no un dato de una fuente: presentarlos como "
    "interpretacion propia."
)
LIMITACIONES_HISTORICO = (
    "Serie historica de un modelo de reanalisis (Open-Meteo Archive, ERA5, grilla de ~25 km), no de "
    "una estacion de la zona consultada ni del SMN/INTA. Sirve para ver el orden de magnitud y "
    "patrones entre anios, no como dato de precision local."
)


@dataclass
class ClienteHttpClima:
    """Wrapper fino sobre httpx para que los clientes de este modulo sean faciles de testear."""

    tiempo_de_espera_segundos: float = 15.0

    def obtener_json(self, url: str, parametros: dict) -> dict:
        """GET a la URL con esos parametros; devuelve el cuerpo ya parseado como dict."""
        respuesta = httpx.get(url, params=parametros, timeout=self.tiempo_de_espera_segundos)
        respuesta.raise_for_status()
        return respuesta.json()


class ClienteGeocodificacion:
    """Resuelve un nombre de lugar (partido, localidad) a coordenadas via Open-Meteo Geocoding."""

    def __init__(self, cliente_http=None):
        self.cliente_http = cliente_http or ClienteHttpClima()

    def resolver(self, nombre_lugar: str) -> dict | None:
        """Primer resultado para ese nombre en Argentina, como {nombre, latitud, longitud}, o None."""
        cuerpo = self.cliente_http.obtener_json(
            URL_API_GEOCODIFICACION, {"name": nombre_lugar, "count": 1, "language": "es", "country": "AR"}
        )
        resultados = cuerpo.get("results") or []
        if not resultados:
            return None
        primero = resultados[0]
        provincia = primero.get("admin1", "")
        return {
            "nombre": f"{primero['name']}, {provincia}" if provincia else primero["name"],
            "latitud": primero["latitude"],
            "longitud": primero["longitude"],
        }


class ResolutorUbicacion:
    """Decide que coordenadas usar: las del partido pedido, o Tandil si no se pide o no se resuelve."""

    def __init__(
        self,
        geocodificador=None,
        latitud_defecto: float = LATITUD_TANDIL,
        longitud_defecto: float = LONGITUD_TANDIL,
        nombre_defecto: str = NOMBRE_TANDIL,
    ):
        self.geocodificador = geocodificador or ClienteGeocodificacion()
        self.latitud_defecto = latitud_defecto
        self.longitud_defecto = longitud_defecto
        self.nombre_defecto = nombre_defecto

    def resolver(self, zona_o_partido: str | None) -> dict:
        """{latitud, longitud, nombre, avisos}; avisos trae un mensaje si hubo que usar el default."""
        if not zona_o_partido:
            return {
                "latitud": self.latitud_defecto,
                "longitud": self.longitud_defecto,
                "nombre": self.nombre_defecto,
                "avisos": [],
            }
        lugar = self.geocodificador.resolver(zona_o_partido)
        if lugar is None:
            aviso = f"No se encontro '{zona_o_partido}'; se uso {self.nombre_defecto} como referencia."
            return {
                "latitud": self.latitud_defecto,
                "longitud": self.longitud_defecto,
                "nombre": self.nombre_defecto,
                "avisos": [aviso],
            }
        return {"latitud": lugar["latitud"], "longitud": lugar["longitud"], "nombre": lugar["nombre"], "avisos": []}


class ClienteClima:
    """Condiciones actuales y pronostico diario de un partido (Tandil por defecto), con alertas."""

    def __init__(self, cliente_http=None, resolutor_ubicacion=None):
        self.cliente_http = cliente_http or ClienteHttpClima()
        self.resolutor_ubicacion = resolutor_ubicacion or ResolutorUbicacion(ClienteGeocodificacion(self.cliente_http))

    def consultar(self, dias_pronostico: int = DIAS_PRONOSTICO_POR_DEFECTO, zona_o_partido: str | None = None) -> dict:
        """Trae clima actual + pronostico diario del partido pedido (Tandil si no se da ninguno)."""
        dias = max(1, min(dias_pronostico, DIAS_PRONOSTICO_MAXIMO))
        ubicacion = self.resolutor_ubicacion.resolver(zona_o_partido)
        cuerpo = self.cliente_http.obtener_json(
            URL_API_PRONOSTICO,
            {
                "latitude": ubicacion["latitud"],
                "longitude": ubicacion["longitud"],
                "timezone": ZONA_HORARIA,
                "forecast_days": dias,
                "current": VARIABLES_ACTUALES,
                "daily": VARIABLES_DIARIAS,
            },
        )
        condiciones_actuales = self._parsear_condiciones_actuales(cuerpo["current"])
        pronostico_diario = self._parsear_pronostico_diario(cuerpo["daily"])
        return {
            "ubicacion": f"{ubicacion['nombre']} ({ubicacion['latitud']}, {ubicacion['longitud']})",
            "fuente": "Open-Meteo (api.open-meteo.com), modelo meteorologico, no estacion propia del partido",
            "actualizado": condiciones_actuales["hora"],
            "condiciones_actuales": condiciones_actuales,
            "pronostico_diario": pronostico_diario,
            "alertas_agronomicas": ubicacion["avisos"] + self._evaluar_alertas(condiciones_actuales, pronostico_diario),
            "limitaciones": LIMITACIONES_PRONOSTICO,
        }

    def _parsear_condiciones_actuales(self, actuales: dict) -> dict:
        """Normaliza el bloque 'current' de la respuesta a nombres de campo en espanol."""
        return {
            "hora": actuales["time"],
            "temperatura_c": actuales["temperature_2m"],
            "humedad_relativa_pct": actuales["relative_humidity_2m"],
            "precipitacion_mm": actuales["precipitation"],
            "viento_kmh": actuales["wind_speed_10m"],
            "rafagas_kmh": actuales["wind_gusts_10m"],
            "direccion_viento_grados": actuales["wind_direction_10m"],
        }

    def _parsear_pronostico_diario(self, diario: dict) -> list[dict]:
        """Arma una lista de dias a partir de las columnas paralelas que devuelve la API."""
        return [
            {
                "fecha": diario["time"][i],
                "temp_max_c": diario["temperature_2m_max"][i],
                "temp_min_c": diario["temperature_2m_min"][i],
                "precipitacion_mm": diario["precipitation_sum"][i],
                "probabilidad_precipitacion_pct": diario["precipitation_probability_max"][i],
                "viento_max_kmh": diario["wind_speed_10m_max"][i],
                "rafagas_max_kmh": diario["wind_gusts_10m_max"][i],
                "evapotranspiracion_mm": diario["et0_fao_evapotranspiration"][i],
                "riesgo_helada": self._evaluar_riesgo_helada(diario["temperature_2m_min"][i]),
                "apto_para_aplicar": self._evaluar_condiciones_aplicacion(
                    diario["wind_speed_10m_max"][i], diario["precipitation_probability_max"][i]
                ),
            }
            for i in range(len(diario["time"]))
        ]

    def _evaluar_riesgo_helada(self, temperatura_minima_c: float) -> str:
        """Clasifica el riesgo de helada del dia por la temperatura minima de pronostico (2 m)."""
        if temperatura_minima_c <= UMBRAL_HELADA_PROBABLE_C:
            return "helada_probable"
        if temperatura_minima_c <= UMBRAL_RIESGO_HELADA_C:
            return "riesgo_helada"
        return "sin_riesgo"

    def _evaluar_condiciones_aplicacion(self, viento_maximo_kmh: float, probabilidad_lluvia_pct: float) -> bool:
        """True si viento y probabilidad de lluvia del dia entran en la ventana recomendada."""
        viento_en_ventana = VIENTO_MINIMO_APLICACION_KMH <= viento_maximo_kmh <= VIENTO_MAXIMO_APLICACION_KMH
        return viento_en_ventana and probabilidad_lluvia_pct < PROBABILIDAD_LLUVIA_ALERTA_PCT

    def _evaluar_alertas(self, condiciones_actuales: dict, pronostico_diario: list[dict]) -> list[str]:
        """Mensajes cortos para los proximos dias con riesgo de helada o viento fuera de ventana."""
        alertas = []
        if not (VIENTO_MINIMO_APLICACION_KMH <= condiciones_actuales["viento_kmh"] <= VIENTO_MAXIMO_APLICACION_KMH):
            alertas.append(
                f"Viento actual {condiciones_actuales['viento_kmh']} km/h fuera de la ventana recomendada "
                f"para pulverizar ({VIENTO_MINIMO_APLICACION_KMH:.0f}-{VIENTO_MAXIMO_APLICACION_KMH:.0f} km/h)."
            )
        for dia in pronostico_diario:
            if dia["riesgo_helada"] != "sin_riesgo":
                alertas.append(f"{dia['fecha']}: {dia['riesgo_helada']} (minima {dia['temp_min_c']} C).")
        return alertas


class ClienteClimatologiaHistorica:
    """Serie historica de un mes (temperatura, lluvia, dias con helada) en los ultimos N anios.

    Reemplaza al uso que el equipo le da a weatherspark/cebadacervecera (mirar si una campana
    entra en un patron que se repite cada varios anios), pero consultable por mes, cantidad de
    anios y partido en vez de leer una tabla estatica.
    """

    def __init__(self, cliente_http=None, resolutor_ubicacion=None):
        self.cliente_http = cliente_http or ClienteHttpClima()
        self.resolutor_ubicacion = resolutor_ubicacion or ResolutorUbicacion(ClienteGeocodificacion(self.cliente_http))

    def consultar(
        self,
        mes: int,
        anios_atras: int = ANIOS_ATRAS_POR_DEFECTO,
        zona_o_partido: str | None = None,
        hoy: datetime.date | None = None,
    ) -> dict:
        """Un resumen por anio (temp., lluvia, dias con helada) de ese mes en los ultimos anios_atras."""
        if not 1 <= mes <= 12:
            raise ValueError(f"Mes invalido: {mes}. Debe estar entre 1 y 12.")
        anios_atras = max(1, min(anios_atras, ANIOS_ATRAS_MAXIMO))
        hoy = hoy or datetime.date.today()
        anio_inicio = hoy.year - anios_atras
        ubicacion = self.resolutor_ubicacion.resolver(zona_o_partido)
        cuerpo = self.cliente_http.obtener_json(
            URL_API_HISTORICA,
            {
                "latitude": ubicacion["latitud"],
                "longitude": ubicacion["longitud"],
                "timezone": ZONA_HORARIA,
                "start_date": f"{anio_inicio}-01-01",
                "end_date": hoy.isoformat(),
                "daily": VARIABLES_DIARIAS_HISTORICAS,
            },
        )
        anios_agregados = self._agregar_por_anio(cuerpo["daily"], mes)
        return {
            "ubicacion": f"{ubicacion['nombre']} ({ubicacion['latitud']}, {ubicacion['longitud']})",
            "fuente": "Open-Meteo Archive (archive-api.open-meteo.com), reanalisis ERA5, no estaciones locales",
            "mes_consultado": NOMBRES_MESES[mes],
            "rango_consultado": f"{anio_inicio}-{hoy.year}",
            "anios": anios_agregados,
            "promedio_historico": self._promediar(anios_agregados),
            "limitaciones": ubicacion["avisos"] + [LIMITACIONES_HISTORICO],
        }

    def _agregar_por_anio(self, diario: dict, mes: int) -> list[dict]:
        """Agrupa los dias de ese mes por anio y calcula los indicadores de cada anio."""
        por_anio: dict[int, dict] = {}
        for i, fecha_texto in enumerate(diario["time"]):
            fecha = datetime.date.fromisoformat(fecha_texto)
            if fecha.month != mes:
                continue
            registro = por_anio.setdefault(fecha.year, {"temps_max": [], "temps_min": [], "precipitaciones": []})
            registro["temps_max"].append(diario["temperature_2m_max"][i])
            registro["temps_min"].append(diario["temperature_2m_min"][i])
            registro["precipitaciones"].append(diario["precipitation_sum"][i])
        return [self._resumir_anio(anio, registro) for anio, registro in sorted(por_anio.items())]

    def _resumir_anio(self, anio: int, registro: dict) -> dict:
        """Indicadores de un anio a partir de las listas diarias de ese mes."""
        temps_min = registro["temps_min"]
        return {
            "anio": anio,
            "temp_max_promedio_c": round(sum(registro["temps_max"]) / len(registro["temps_max"]), 1),
            "temp_min_promedio_c": round(sum(temps_min) / len(temps_min), 1),
            "temp_min_minima_c": round(min(temps_min), 1),
            "precipitacion_total_mm": round(sum(registro["precipitaciones"]), 1),
            "dias_con_helada": sum(1 for t in temps_min if t <= UMBRAL_HELADA_HISTORICA_C),
            "dias_con_lluvia": sum(1 for p in registro["precipitaciones"] if p > MM_LLUVIA_MINIMO_PARA_CONTAR_DIA),
        }

    def _promediar(self, anios_agregados: list[dict]) -> dict:
        """Promedio simple de cada indicador a lo largo de los anios devueltos (referencia rapida)."""
        if not anios_agregados:
            return {}
        claves = (
            "temp_max_promedio_c", "temp_min_promedio_c", "precipitacion_total_mm",
            "dias_con_helada", "dias_con_lluvia",
        )
        return {clave: round(sum(anio[clave] for anio in anios_agregados) / len(anios_agregados), 1) for clave in claves}
