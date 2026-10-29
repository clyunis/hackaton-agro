"""Estado regulatorio SENASA de un principio activo o marca, para no recomendar productos prohibidos.

Dos fuentes, con roles distintos:
- senasaProductosFormulados.csv (Registro Nacional de Terapeutica Vegetal): dice si una marca
  o activo FIGURA en el registro. No dice para que cultivos esta autorizado ni su formulacion,
  y figurar no alcanza: hay productos con activos prohibidos que siguen listados.
- RESTRICCIONES_SENASA: tabla armada a mano con las resoluciones descargadas en
  raw_data/descargas/01_senasa_rntv/, citando el articulo textual. Es una busqueda exacta por
  nombre (no RAG): "esta prohibido?" es una pregunta de si/no que no puede depender de la
  similitud semantica.

La tabla cubre solo las resoluciones que estan en el repo (descargadas el 28/10/2026); una
norma posterior no estaria reflejada. Por eso cada resultado incluye LIMITACIONES.
"""

import csv
import re
import unicodedata
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
RUTA_PRODUCTOS_FORMULADOS = RAIZ_REPO / "raw_data" / "agro" / "senasaProductosFormulados.csv"
CARPETA_RESOLUCIONES = "raw_data/descargas/01_senasa_rntv"
MAX_EJEMPLOS_PRODUCTOS = 5

LIMITACIONES = (
    "El registro (CSV de SENASA, fecha y URL de descarga no registradas) no indica cultivos autorizados "
    "ni formulacion. La tabla de prohibiciones cubre solo las Res. SENASA 32/2019 (Anexos I y II), "
    "149/2018, 263/2018, 670/2018, 466/2019, 875/2019, 414/2021 y 425/2021; normas posteriores no "
    "estan incluidas. Para el marbete legal vigente, consultar el vademecum de SENASA."
)

TEXTO_414_2021_ART_3 = (
    "Se prohibe a partir de los CUATROCIENTOS CINCUENTA Y CINCO (455) dias de entrada en vigencia de la "
    "presente resolucion, la comercializacion y uso de productos fitosanitarios formulados a base de "
    "Clorpirifos etil y Clorpirifos metil."
)
TEXTO_425_2021_ART_3 = (
    "Se prohibe a partir de los CUATROCIENTOS OCHENTA Y CINCO (485) dias de entrada en vigencia de la "
    "presente resolucion, la comercializacion y uso en todo el Territorio Nacional de los productos "
    "formulados a base de Fipronil como Suspension Concentrada (SC) y Granulos Dispersables (WG)."
)
TEXTO_466_2019_ART_3 = (
    "Se prohibe a partir de los SETECIENTOS TREINTA (730) dias corridos de la entrada en vigencia de la "
    "presente resolucion, la comercializacion y uso de los productos formulados con esteres butilicos e "
    "isobutilicos de la sustancia activa 2,4-D. (Articulo sustituido por Res. SENASA 875/2019 Art. 1)"
)
TEXTO_263_2018_ARTS_2_Y_3 = (
    "Art. 2: Se prohibe a partir de los TRESCIENTOS SESENTA Y CINCO (365) dias de la entrada en vigencia "
    "de la presente resolucion, la comercializacion y uso de las sustancias activas carbofuran, "
    "carbosulfan, diazinon, aldicarb y dicofol y sus productos formulados. Art. 3 (texto de Res. SENASA "
    "670/2018): Se exceptua de la prohibicion establecida en los Articulos 1 y 2 de la presente "
    "resolucion, la formulacion en granulos de carbofuran al DIEZ POR CIENTO (10 %)."
)
TEXTO_149_2018_ART_1 = (
    "Se prohibe la importacion, comercializacion y uso de los principios activos Diclorvos (DDVP) y "
    "Triclorfon y de los productos formulados que los contengan, para su utilizacion en granos, incluidas "
    "las etapas de produccion, poscosecha, transporte, manipuleo, acondicionamiento y almacenamiento, asi "
    "como tambien en instalaciones para el almacenamiento de granos y de tabaco."
)

# Anexo I de la Res. SENASA 32/2019 (Listado de Principios Activos Prohibidos), textual.
# Cada entrada: (nombre como figura en el anexo, alias normalizables adicionales).
ANEXO_I_32_2019 = [
    ("2,4,5-T", []), ("3-CLORO-1,2-PROPANODIOL", []), ("ALCOHOL ALILICO", []), ("ALDRIN", []),
    ("ARSENIATO DE CALCIO", []), ("ARSENIATO DE PLOMO", []), ("ARSENIATO DE SODIO", []), ("ARSENICO", []),
    ("BLASTICIDIN-S", []), ("BROMETALIN", []), ("BUTOCARBOXIM", []), ("BUTOXICARBOXIM", []),
    ("CADUSAFOS", []), ("CANFECLOR", []), ("CAPTAFOL", []), ("CIANURO DE CALCIO", []),
    ("CIANURO DE SODIO", []), ("CLORDANO", []), ("CLORFENVINFOS", []), ("CLORMEFOS", []),
    ("CLOROBENCILATO", []), ("CLOROETOXIFOS", []), ("CLOROFACINONE", []), ("CLORURO DE MERCURIO", []),
    ("COUMAFOS", []), ("COUMATETRALYL", []), ("D.D.T.", []), ("DAMINOZIDE", []),
    ("DEMETON-S-METIL", []), ("DIBROMURO DE ETILENO", []), ("DICROTOFOS", []), ("DIELDRIN", []),
    ("DIFACINONE", []), ("DIFENACOUM", []), ("DINOCAP", []), ("DINOTERB", []), ("DISULFOTON", []),
    ("DNOC", []), ("DODECACLORO", []), ("EDIFENFOS", []), ("ENDOSULFAN", []), ("ENDRIN", []),
    ("EPN", []), ("ETIOFENCARB", []), ("ETOPROFOS", []), ("FAMFUR", []),
    ("FENIL ACETATO DE MERCURIO", []), ("FLOCOUMAFEN", []), ("FLUCITRINATO", []),
    ("FLUOROACETAMIDA", []), ("FLUOROACETATO DE SODIO", []), ("FLURATIOCARB", []), ("FORATO", []),
    ("FOSFAMIDON", []), ("FOSFURO DE ZINC", []), ("H.C.B. (HEXACLORO CICLO BENCENO)", ["HEXACLORO CICLO BENCENO"]),
    ("H.C.H. (HEXACLORO CICLO HEXANO)", ["HEXACLORO CICLO HEXANO"]), ("HEPTACLORO", []), ("HEPTENOFOS", []),
    ("ISOXATION", []), ("LINDANO", []), ("MECARBAM", []), ("METAMIDOFOS", []), ("METIL AZINFOS", []),
    ("METOXICLORO", []), ("MEVINFOS", []), ("MONOCROTOFOS", []), ("OMETOATO", []), ("OXAMYL", []),
    ("OXIDO DE MERCURIO", []), ("PARATION (ETIL)", ["PARATION"]), ("PARATION (METIL)", ["PARATION"]),
    ("PENTACLOROFENOL Y SUS DERIVADOS", ["PENTACLOROFENOL"]), ("PROPETAMFOS", []),
    ("SULFATO DE ESTRICNINA", []), ("SULFOTEP", []), ("TALIO", []), ("TEBUPIRIMIFOS", []),
    ("TERBUFOS", []), ("THIOMETON", []), ("TIOFANOX", []), ("TRIAZOFOS", []), ("VAMIDOTION", []),
    ("VERDE PARIS", []), ("WARFARINA", []),
]

# Anexo II de la Res. SENASA 32/2019 (Listado de Principios Activos de Uso Restringido), textual.
ANEXO_II_32_2019 = [
    ("ALDICARB", ("Se encuentra prohibido su uso en zonas donde se presenten conjuntamente: dosis superiores "
     "a 1,500 kg de aldicarb por hectarea, temperatura del suelo inferior a 10 C, capacidad de campo "
     "inferior al 15 % en volumen, materia organica inferior al 1 % en los 30 cm superiores, subsuelo pH "
     "inferior a 6 y precipitacion media anual superior a 800 mm o riego equivalente.")),
    ("AMINOTRIAZOL", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("BICLORURO DE MERCURIO", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("CARBOFURAN", "Se encuentra prohibido su uso en cultivos de peral y manzano."),
    ("COMPUESTO DE SELENIO", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("COMPUESTOS ARSENICALES", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("COMPUESTOS FLUORADOS", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("COMPUESTOS MERCURIALES", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("ETIL AZINFOS", "Se encuentra prohibido su uso en cultivos horticolas y frutales en general."),
    ("ETION", "Se encuentra prohibido su uso en cultivos de peral y manzano."),
    ("FENITROTION", ("Se encuentra prohibido su uso y aplicacion en las etapas de poscosecha, transporte, "
     "manipuleo, acondicionamiento y almacenamiento de granos.")),
    ("FORMOTION", "Uso no autorizado en cultivo de tabaco."),
    ("ISODRIN", "Se encuentra prohibido su uso en cultivo de tabaco."),
    ("PERMETRINA", "Uso no autorizado en cultivo de tabaco."),
]


def normalizar_nombre(texto: str) -> str:
    """Mayusculas sin tildes; los puntos se eliminan (D.D.T. -> DDT) y el resto de signos son espacios."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    sin_puntos = sin_tildes.upper().replace(".", "")
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", sin_puntos).split())


def separar_activos(activos: str) -> list[str]:
    """Separa 'ETIPROLE 35%, FIPRONIL 25%' en nombres, sin cortar '2,4 D' ni ',003%'."""
    nombres = re.findall(r"\s*(.+?)\s+[\d.,]*\d\s*%\s*(?:p/[pv])?\s*(?:,|$)", activos)
    return [nombre.strip() for nombre in nombres] or [activos.strip()]


def _construir_restricciones() -> list[dict]:
    """Arma la tabla de restricciones a partir de las resoluciones y anexos de arriba."""
    restricciones = [
        {
            "principio_activo": "CLORPIRIFOS (etil y metil)",
            "alias": ["CLORPIRIFOS"],
            "estado": "prohibido",
            "alcance": "Comercializacion y uso prohibidos (plazo de 455 dias ya cumplido).",
            "norma": "Res. SENASA 414/2021",
            "articulo": "Art. 3",
            "archivo": "res_senasa_414_2021_clorpirifos.pdf",
            "texto": TEXTO_414_2021_ART_3,
        },
        {
            "principio_activo": "FIPRONIL",
            "alias": ["FIPRONIL"],
            "estado": "prohibido_parcial",
            "alcance": "Prohibidas comercializacion y uso de formulaciones SC y WG; otras formulaciones no "
            "estan alcanzadas por esta norma. Verificar la formulacion del producto.",
            "norma": "Res. SENASA 425/2021",
            "articulo": "Art. 3",
            "archivo": "res_senasa_425_2021_fipronil.pdf",
            "texto": TEXTO_425_2021_ART_3,
        },
        {
            "principio_activo": "2,4-D (esteres butilicos e isobutilicos)",
            "alias": ["2 4 D"],
            # Formas de 2,4-D que la norma no alcanza: si el nombre las menciona, no se alerta.
            "excluyentes": ["SAL", "SALES", "COLINA", "AMINA", "DIMETILAMINA", "ETILEXILICO", "ETILHEXILICO"],
            "estado": "prohibido_parcial",
            "alcance": "Prohibidos solo los formulados con esteres butilicos e isobutilicos; otras sales y "
            "esteres de 2,4-D no estan alcanzados. Verificar la formulacion del producto.",
            "norma": "Res. SENASA 466/2019 (mod. Res. 875/2019)",
            "articulo": "Art. 3",
            "archivo": "res_senasa_466_2019.pdf",
            "texto": TEXTO_466_2019_ART_3,
        },
        {
            "principio_activo": "CARBOFURAN",
            "alias": ["CARBOFURAN"],
            "estado": "prohibido_parcial",
            "alcance": "Comercializacion y uso prohibidos, excepto la formulacion en granulos al 10 %.",
            "norma": "Res. SENASA 263/2018 (mod. Res. 670/2018)",
            "articulo": "Arts. 2 y 3",
            "archivo": "res_senasa_263_2018.pdf",
            "texto": TEXTO_263_2018_ARTS_2_Y_3,
        },
    ]
    for activo in ["CARBOSULFAN", "DIAZINON", "ALDICARB", "DICOFOL"]:
        restricciones.append(
            {
                "principio_activo": activo,
                "alias": [activo],
                "estado": "prohibido",
                "alcance": "Comercializacion y uso prohibidos (plazo de 365 dias ya cumplido).",
                "norma": "Res. SENASA 263/2018",
                "articulo": "Art. 2",
                "archivo": "res_senasa_263_2018.pdf",
                "texto": TEXTO_263_2018_ARTS_2_Y_3,
            }
        )
    for activo, alias in [("DICLORVOS (DDVP)", ["DICLORVOS", "DDVP"]), ("TRICLORFON", ["TRICLORFON"])]:
        restricciones.append(
            {
                "principio_activo": activo,
                "alias": alias,
                "estado": "prohibido_parcial",
                "alcance": "Prohibido para uso en granos (produccion, poscosecha, almacenamiento) y en "
                "instalaciones de almacenamiento de granos y tabaco.",
                "norma": "Res. SENASA 149/2018",
                "articulo": "Art. 1",
                "archivo": "res_senasa_149_2018.docx",
                "texto": TEXTO_149_2018_ART_1,
            }
        )
    for nombre_anexo, alias_extra in ANEXO_I_32_2019:
        restricciones.append(
            {
                "principio_activo": nombre_anexo,
                "alias": [re.sub(r"\(.*?\)", " ", nombre_anexo) + " " + " ".join(re.findall(r"\((.*?)\)", nombre_anexo))]
                + alias_extra,
                "estado": "prohibido",
                "alcance": "Principio activo prohibido.",
                "norma": "Res. SENASA 32/2019 Anexo I",
                "articulo": "Art. 1",
                "archivo": "res_senasa_32_2019_anexo1.pdf",
                "texto": f"Listado de Principios Activos Prohibidos: {nombre_anexo}.",
            }
        )
    for nombre_anexo, texto_restriccion in ANEXO_II_32_2019:
        restricciones.append(
            {
                "principio_activo": nombre_anexo,
                "alias": [nombre_anexo],
                "estado": "uso_restringido",
                "alcance": texto_restriccion,
                "norma": "Res. SENASA 32/2019 Anexo II",
                "articulo": "Art. 2",
                "archivo": "res_senasa_32_2019_anexo2.pdf",
                "texto": f"Listado de Principios Activos de Uso Restringido: {nombre_anexo}. {texto_restriccion}",
            }
        )
    for restriccion in restricciones:
        restriccion["tokens_alias"] = [set(normalizar_nombre(alias).split()) for alias in restriccion["alias"]]
        restriccion["tokens_excluyentes"] = set(restriccion.pop("excluyentes", []))
        restriccion["archivo"] = f"{CARPETA_RESOLUCIONES}/{restriccion['archivo']}"
    return restricciones


RESTRICCIONES_SENASA = _construir_restricciones()


class RegistroSenasa:
    """Productos formulados inscriptos en el Registro Nacional de Terapeutica Vegetal (CSV de SENASA)."""

    def __init__(self, ruta_csv: Path = RUTA_PRODUCTOS_FORMULADOS):
        self.productos = []
        with open(ruta_csv, encoding="utf-8-sig") as archivo_csv:
            for fila in csv.DictReader(archivo_csv, delimiter=";"):
                activos = separar_activos(fila["Activos"])
                self.productos.append(
                    {
                        "registro": fila["N° registro"],
                        "marca": fila["Marca"],
                        "empresa": fila["Empresa"],
                        "activos": fila["Activos"],
                        "banda_toxicologica": fila["Banda tox"],
                        "tokens_marca": set(normalizar_nombre(fila["Marca"]).split()),
                        "tokens_activos": [set(normalizar_nombre(activo).split()) for activo in activos],
                        "nombres_activos": activos,
                    }
                )

    def buscar(self, nombre: str) -> list[dict]:
        """Productos cuya marca coincide con el nombre, o que contienen ese principio activo."""
        tokens_nombre = set(normalizar_nombre(nombre).split())
        if not tokens_nombre:
            return []
        return [
            producto
            for producto in self.productos
            if tokens_nombre == producto["tokens_marca"]
            or any(tokens_nombre <= tokens_activo for tokens_activo in producto["tokens_activos"])
        ]


class VerificadorRegulatorio:
    """Cruza un nombre contra la tabla de prohibiciones y el registro, y concluye su estado."""

    def __init__(self, registro: RegistroSenasa | None = None):
        self.registro = registro or RegistroSenasa()

    def restricciones_para(self, nombre_activo: str) -> list[dict]:
        """Restricciones cuyo alias esta contenido (palabra por palabra) en el nombre del activo."""
        tokens_nombre = set(normalizar_nombre(nombre_activo).split())
        return [
            restriccion
            for restriccion in RESTRICCIONES_SENASA
            if any(tokens_alias <= tokens_nombre for tokens_alias in restriccion["tokens_alias"])
            and not tokens_nombre & restriccion["tokens_excluyentes"]
        ]

    def verificar(self, nombre: str) -> dict:
        """Estado regulatorio de un principio activo o marca comercial, con la norma que lo respalda."""
        productos = self.registro.buscar(nombre)
        restricciones_por_norma = {}
        nombres_a_chequear = [nombre]
        for producto in productos:
            if set(normalizar_nombre(nombre).split()) == producto["tokens_marca"]:
                nombres_a_chequear.extend(producto["nombres_activos"])
        for nombre_activo in nombres_a_chequear:
            for restriccion in self.restricciones_para(nombre_activo):
                restricciones_por_norma[(restriccion["principio_activo"], restriccion["norma"])] = restriccion
        restricciones = [self._resumir_restriccion(r) for r in restricciones_por_norma.values()]
        return {
            "consulta": nombre,
            "restricciones": restricciones,
            "productos_registrados": {
                "cantidad": len(productos),
                "ejemplos": [
                    {clave: producto[clave] for clave in ("registro", "marca", "empresa", "activos", "banda_toxicologica")}
                    for producto in productos[:MAX_EJEMPLOS_PRODUCTOS]
                ],
            },
            "conclusion": self._concluir(restricciones, len(productos)),
            "limitaciones": LIMITACIONES,
        }

    def restricciones_para_producto(self, producto_marbete: str) -> list[dict]:
        """Restricciones de un titulo de marbete combinado ('A + B'), chequeando activo por activo."""
        restricciones = []
        for activo in producto_marbete.split("+"):
            for restriccion in self.restricciones_para(activo):
                if restriccion not in restricciones:
                    restricciones.append(restriccion)
        return restricciones

    def describir_restriccion(self, restriccion: dict) -> str:
        """Una linea legible: estado, activo, alcance y norma."""
        etiqueta_estado = restriccion["estado"].upper().replace("_", " ")
        return (
            f"{etiqueta_estado} {restriccion['principio_activo']}: {restriccion['alcance']} "
            f"({restriccion['norma']} {restriccion['articulo']})"
        )

    def alerta_para_producto(self, producto_marbete: str) -> str | None:
        """Alerta de una linea para un titulo de marbete, o None si no hay restricciones."""
        restricciones = self.restricciones_para_producto(producto_marbete)
        return " | ".join(self.describir_restriccion(r) for r in restricciones) or None

    def _resumir_restriccion(self, restriccion: dict) -> dict:
        """Restriccion sin los campos internos de matching."""
        campos_internos = ("alias", "tokens_alias", "tokens_excluyentes")
        return {clave: valor for clave, valor in restriccion.items() if clave not in campos_internos}

    def _concluir(self, restricciones: list[dict], cantidad_productos: int) -> str:
        """Conclusion deterministica, de la mas grave a la menos grave."""
        estados = {restriccion["estado"] for restriccion in restricciones}
        normas = "; ".join(f"{r['norma']} {r['articulo']}" for r in restricciones)
        if "prohibido" in estados:
            return f"PROHIBIDO ({normas}). No recomendar, aunque figure en un marbete o en el registro."
        if "prohibido_parcial" in estados:
            return f"PROHIBIDO PARCIALMENTE ({normas}). Verificar formulacion o uso antes de recomendar."
        if "uso_restringido" in estados:
            return f"USO RESTRINGIDO ({normas}). Verificar que el uso propuesto no este alcanzado."
        if cantidad_productos:
            return (
                f"Figura en el registro de SENASA ({cantidad_productos} productos), sin prohibiciones en las "
                "normas cargadas. Esto no confirma que este autorizado para el cultivo consultado."
            )
        return (
            "No se encontro en el registro de SENASA ni en las normas cargadas: no se puede confirmar que "
            "este registrado. Revisar el nombre o consultar el vademecum de SENASA."
        )
