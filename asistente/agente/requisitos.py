"""Que datos hacen falta para responder bien cada tipo de consulta.

Esta tabla es conocimiento agronomico del equipo/tutor, no del modelo: esta pensada para
que el referente la pueda leer y corregir sin tocar el resto del codigo. El modelo la
consulta via la tool analizar_consulta antes de recomendar nada (ver orquestador.py).

Los "criterios" son guia interna, NO fuentes citables: el prompt le pide al modelo que
si los usa los presente como interpretacion propia.
"""

# Todas las claves de datos que puede registrar el modelo (es el enum de la tool).
CLAVES_DATOS = {
    "cultivo": "Cultivo actual o a implantar",
    "etapa_o_momento": "Momento: barbecho, presiembra, preemergencia, postemergencia o estado fenologico",
    "malezas_presentes": "Que malezas hay en el lote (especies)",
    "tamano_malezas": "Tamano o estado de las malezas (cm, hojas, roseta, macollaje, floracion)",
    "producto_o_formulacion": "Producto a usar: principio activo, sal/formulacion y concentracion",
    "plaga_o_enfermedad": "Plaga o enfermedad identificada",
    "nivel_de_dano_o_infestacion": "Resultado del monitoreo: densidad, incidencia, severidad o defoliacion",
    "productos_a_mezclar": "Productos (y formulaciones) que se quieren mezclar en el tanque",
    "dosis_aplicada": "Dosis aplicada o prevista",
    "cultivo_siguiente": "Cultivo que se quiere sembrar despues",
    "dias_desde_o_hasta_aplicacion": "Dias entre la aplicacion y la siembra prevista (o fecha de cada una)",
    "precipitaciones": "Lluvias registradas desde la aplicacion o condiciones de humedad del suelo",
    "sintoma_observado": "Sintoma que se observa (color, organo afectado, patron)",
    "distribucion_del_sintoma": "Como se distribuye en el lote: manchones, cabeceras, bajos, todo el lote",
    "manejo_previo": "Aplicaciones, fertilizaciones y antecesor recientes del lote",
    "condiciones_ambientales": "Condiciones recientes: heladas, sequia, anegamiento, temperaturas",
    "analisis_de_suelo": "Analisis de suelo: P Bray, MO, N-nitratos, pH, profundidad de muestreo",
    "rendimiento_objetivo": "Rendimiento objetivo (kg/ha)",
    "cultivo_antecesor": "Cultivo antecesor",
    "zona_o_partido": "Partido o zona del lote",
    "fertilizante_y_grado": "Fertilizante y su grado (ej. urea 46-0-0, MAP 11-52-0)",
    "objetivo_de_nutriente": "Cantidad de nutriente que se quiere aportar (kg/ha)",
    "ambiente_del_lote": "Caracteristicas del sector o ambiente (tosca, bajo, loma, textura)",
}

TIPOS_CONSULTA = {
    "dosis_herbicida": {
        "descripcion": "Dosis o eleccion de herbicida para controlar malezas",
        "requisitos": [
            ("malezas_presentes", True),
            ("tamano_malezas", True),
            ("producto_o_formulacion", True),
            ("cultivo", True),
            ("etapa_o_momento", True),
            ("condiciones_ambientales", False),
        ],
        "criterios": [
            ("La dosis se define por las malezas presentes, su tamano/estado y el producto (sal y "
            "concentracion), no por el cultivo antecesor."),
            ("El glifosato actua solo sobre malezas emergidas; no tiene efecto residual util en el suelo. "
            "Si el lote esta limpio, no se justifica aplicarlo."),
            ("Una dosis que funciono en otro lote (por ejemplo, la del vecino) no es transferible: depende "
            "de las malezas, su tamano, el producto y las condiciones de ese lote."),
            ("Si la maleza no figura en la tabla del marbete para ese cultivo y momento, decir que el "
            "marbete no respalda esa dosis."),
        ],
        "herramientas_sugeridas": ["buscar_marbetes", "verificar_estado_regulatorio"],
        "limitaciones_corpus": "",
    },
    "dosis_insecticida_fungicida": {
        "descripcion": "Control quimico de una plaga o enfermedad",
        "requisitos": [
            ("plaga_o_enfermedad", True),
            ("nivel_de_dano_o_infestacion", True),
            ("cultivo", True),
            ("etapa_o_momento", True),
            ("producto_o_formulacion", False),
        ],
        "criterios": [
            "Aplicar solo si el monitoreo supera el umbral de dano o de accion; si no hay monitoreo, pedirlo.",
            "Respetar el periodo de carencia y las restricciones del marbete.",
        ],
        "herramientas_sugeridas": ["buscar_marbetes", "verificar_estado_regulatorio"],
        "limitaciones_corpus": "",
    },
    "mezcla_de_productos": {
        "descripcion": "Compatibilidad de productos en mezcla de tanque",
        "requisitos": [
            ("productos_a_mezclar", True),
            ("etapa_o_momento", True),
            ("cultivo", False),
        ],
        "criterios": [
            ("Revisar la seccion de compatibilidad de cada marbete involucrado. Si un marbete no menciona "
            "la mezcla, decir que no hay respaldo documental para ella."),
        ],
        "herramientas_sugeridas": ["buscar_marbetes", "verificar_estado_regulatorio"],
        "limitaciones_corpus": "",
    },
    "restriccion_siembra_posterior": {
        "descripcion": "Si se puede sembrar un cultivo despues de aplicar un producto (intervalo/rotacion)",
        "requisitos": [
            ("producto_o_formulacion", True),
            ("cultivo_siguiente", True),
            ("dias_desde_o_hasta_aplicacion", True),
            ("dosis_aplicada", False),
            ("precipitaciones", False),
        ],
        "criterios": [
            ("Buscar en el marbete restricciones de rotacion o intervalo hasta la siembra. Si no figuran, "
            "decir explicitamente que no hay evidencia en los marbetes disponibles; no inferir plazos."),
        ],
        "herramientas_sugeridas": ["buscar_marbetes", "verificar_estado_regulatorio"],
        "limitaciones_corpus": "",
    },
    "diagnostico_sintoma": {
        "descripcion": "Interpretar un sintoma observado en el cultivo",
        "requisitos": [
            ("cultivo", True),
            ("sintoma_observado", True),
            ("distribucion_del_sintoma", True),
            ("etapa_o_momento", True),
            ("manejo_previo", False),
            ("condiciones_ambientales", False),
        ],
        "criterios": [
            ("Un mismo sintoma (por ejemplo, amarillamiento) puede tener varias causas: nutricional, hidrica, "
            "fitotoxicidad, enfermedad o plaga. No atribuir una causa sin datos; proponer que observar o medir."),
            ("En leguminosas como la soja el nitrogeno proviene en gran parte de la fijacion biologica: "
            "revisar la nodulacion antes de pensar en fertilizar con nitrogeno."),
        ],
        "herramientas_sugeridas": [],
        "limitaciones_corpus": "El corpus indexado (marbetes) no incluye guias de diagnostico de sintomas.",
    },
    "fertilizacion": {
        "descripcion": "Estrategia o dosis de fertilizacion",
        "requisitos": [
            ("cultivo", True),
            ("rendimiento_objetivo", True),
            ("analisis_de_suelo", True),
            ("zona_o_partido", False),
            ("cultivo_antecesor", False),
            ("fertilizante_y_grado", False),
            ("ambiente_del_lote", False),
        ],
        "criterios": [
            ("Un sector que rinde menos puede estar limitado por otro factor (agua, suelo, tosca, malezas); "
            "diagnosticar la limitante antes de agregar fertilizante para igualar rendimientos."),
            ("Si el ingeniero da un requerimiento o una dosis objetivo, convertirla a producto con las "
            "herramientas de calculo y mostrar la formula."),
        ],
        "herramientas_sugeridas": ["calcular_dosis_fertilizante", "calcular_aporte_nutriente"],
        "limitaciones_corpus": (
            "El corpus indexado (marbetes) no contiene modelos ni tablas de recomendacion de fertilizacion: "
            "no hay respaldo documental para fijar una dosis. Decirlo y ofrecer el calculo a partir de un "
            "objetivo que provea el ingeniero."
        ),
    },
    "calculo_nutrientes": {
        "descripcion": "Cuenta de aporte de nutriente o conversion de dosis",
        "requisitos": [
            ("fertilizante_y_grado", True),
            ("dosis_aplicada", False),
            ("objetivo_de_nutriente", False),
        ],
        "criterios": ["Usar siempre las herramientas de calculo y mostrar la formula."],
        "herramientas_sugeridas": ["calcular_aporte_nutriente", "calcular_dosis_fertilizante"],
        "limitaciones_corpus": "",
    },
    "consulta_general": {
        "descripcion": "Cualquier otra consulta tecnica",
        "requisitos": [],
        "criterios": [],
        "herramientas_sugeridas": ["buscar_marbetes", "verificar_estado_regulatorio"],
        "limitaciones_corpus": "",
    },
    "condiciones_aplicacion": {
        "descripcion": "Si las condiciones meteorologicas actuales o de los proximos dias permiten pulverizar",
        "requisitos": [
            ("etapa_o_momento", False),
            ("producto_o_formulacion", False),
            ("cultivo", False),
        ],
        "criterios": [
            ("Evaluar viento y lluvia pronosticados con consultar_clima, no de memoria. Viento muy bajo "
            "favorece inversion termica y viento alto favorece deriva; ambos son criterio agronomico "
            "general del equipo (no un dato de fuente): presentarlos como interpretacion propia con el "
            "umbral usado."),
            ("Si el producto a aplicar tiene restricciones propias de viento, humedad o temperatura en su "
            "marbete, esas si son dato de fuente [F#] y pisan al criterio general."),
        ],
        "herramientas_sugeridas": ["consultar_clima", "buscar_marbetes"],
        "limitaciones_corpus": (
            "consultar_clima usa un modelo meteorologico (Open-Meteo), no una estacion de Tandil ni del "
            "SMN/INTA: es una referencia, no un dato de precision local."
        ),
    },
    "riesgo_heladas": {
        "descripcion": "Riesgo de helada en el lote para los proximos dias y su efecto sobre el cultivo",
        "requisitos": [
            ("cultivo", False),
            ("etapa_o_momento", False),
        ],
        "criterios": [
            ("El riesgo de helada se evalua con consultar_clima sobre la temperatura minima pronosticada, "
            "no de memoria. El umbral de riesgo es criterio agronomico general del equipo (la temperatura "
            "a nivel de cultivo suele ser menor que la de pronostico a 2 m): presentarlo como "
            "interpretacion propia."),
            ("La sensibilidad a la helada depende del cultivo y de su estado fenologico (por ejemplo, "
            "floracion es mas sensible que vegetativo); si no se sabe el estado, pedirlo antes de concluir "
            "que no hay riesgo."),
            ("Para saber si una helada puntual es rara o si mayo/junio suelen traer heladas en esa zona, "
            "usar consultar_climatologia_historica (dias con helada por anio), no solo el pronostico."),
        ],
        "herramientas_sugeridas": ["consultar_clima", "consultar_climatologia_historica"],
        "limitaciones_corpus": (
            "consultar_clima usa un modelo meteorologico (Open-Meteo), no una estacion de Tandil ni del "
            "SMN/INTA: es una referencia, no un dato de precision local."
        ),
    },
}


class CatalogoRequisitos:
    """Contrasta los datos que dio el ingeniero contra los requisitos del tipo de consulta."""

    def tipos_disponibles(self) -> list[str]:
        """Nombres de los tipos de consulta (es el enum de la tool)."""
        return list(TIPOS_CONSULTA)

    def requisitos_de(self, tipo_consulta: str) -> list[dict]:
        """Lista de requisitos {clave, descripcion, critico} de un tipo de consulta."""
        if tipo_consulta not in TIPOS_CONSULTA:
            raise ValueError(f"Tipo de consulta desconocido: {tipo_consulta}. Opciones: {self.tipos_disponibles()}")
        return [
            {"clave": clave, "descripcion": CLAVES_DATOS[clave], "critico": es_critico}
            for clave, es_critico in TIPOS_CONSULTA[tipo_consulta]["requisitos"]
        ]

    def analizar(self, tipo_consulta: str, datos_identificados: list[dict]) -> dict:
        """Devuelve datos presentes, faltantes (criticos y opcionales), criterios y herramientas sugeridas."""
        requisitos = self.requisitos_de(tipo_consulta)
        datos_presentes = {
            dato["clave"]: dato["valor"].strip()
            for dato in datos_identificados
            if dato.get("valor", "").strip()
        }
        faltantes_criticos = []
        faltantes_opcionales = []
        for requisito in requisitos:
            if requisito["clave"] in datos_presentes:
                continue
            faltante = {"clave": requisito["clave"], "descripcion": requisito["descripcion"]}
            (faltantes_criticos if requisito["critico"] else faltantes_opcionales).append(faltante)
        definicion = TIPOS_CONSULTA[tipo_consulta]
        return {
            "tipo_consulta": tipo_consulta,
            "datos_presentes": datos_presentes,
            "datos_faltantes_criticos": faltantes_criticos,
            "datos_faltantes_opcionales": faltantes_opcionales,
            "puede_responder": not faltantes_criticos,
            "criterios": definicion["criterios"],
            "herramientas_sugeridas": definicion["herramientas_sugeridas"],
            "limitaciones_corpus": definicion["limitaciones_corpus"],
        }
