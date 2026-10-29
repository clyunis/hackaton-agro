"""Calculos de nutrientes deterministicos, para que el modelo nunca haga cuentas de memoria.

Cada resultado trae la formula usada en texto, asi la respuesta final la puede mostrar
y el ingeniero la puede verificar a mano (requisito del desafio: calculos verificables).
"""

# Factores de conversion de la forma de expresion comercial al elemento:
# P2O5 -> P = 2 * 30,974 / 141,944 ; K2O -> K = 2 * 39,098 / 94,196.
FACTORES_A_ELEMENTAL = {
    "N": ("N", 1.0),
    "P": ("P", 1.0),
    "P2O5": ("P", 0.4364),
    "K": ("K", 1.0),
    "K2O": ("K", 0.8301),
    "S": ("S", 1.0),
}

FORMAS_DE_EXPRESION = list(FACTORES_A_ELEMENTAL)


def _formatear_numero(valor: float) -> str:
    """Formatea con hasta 2 decimales y coma decimal (estilo argentino)."""
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _formatear_factor(factor: float) -> str:
    """Formatea un factor de conversion con 4 decimales y coma decimal."""
    return f"{factor:.4f}".replace(".", ",")


class CalculadoraNutrientes:
    """Aporte de nutrientes de un fertilizante y dosis de producto para un objetivo."""

    def _validar_porcentaje(self, porcentaje_en_producto: float) -> None:
        """Un grado de fertilizante tiene que estar en (0, 100]."""
        if not 0 < porcentaje_en_producto <= 100:
            raise ValueError(f"Porcentaje fuera de rango: {porcentaje_en_producto}. Debe estar entre 0 y 100.")

    def _validar_forma(self, expresado_como: str) -> None:
        """Solo se aceptan las formas de expresion conocidas."""
        if expresado_como not in FACTORES_A_ELEMENTAL:
            raise ValueError(f"Forma de expresion desconocida: {expresado_como}. Opciones: {FORMAS_DE_EXPRESION}")

    def calcular_aporte(self, dosis_producto_kg_ha: float, porcentaje_en_producto: float, expresado_como: str) -> dict:
        """Kg/ha de nutriente (en la forma declarada y elemental) que aporta una dosis de producto."""
        self._validar_porcentaje(porcentaje_en_producto)
        self._validar_forma(expresado_como)
        if dosis_producto_kg_ha < 0:
            raise ValueError("La dosis de producto no puede ser negativa.")
        elemental, factor = FACTORES_A_ELEMENTAL[expresado_como]
        nutriente_kg_ha = dosis_producto_kg_ha * porcentaje_en_producto / 100
        elemental_kg_ha = nutriente_kg_ha * factor
        formula = (
            f"{_formatear_numero(dosis_producto_kg_ha)} kg/ha x {_formatear_numero(porcentaje_en_producto)}/100 = "
            f"{_formatear_numero(nutriente_kg_ha)} kg {expresado_como}/ha"
        )
        if factor != 1.0:
            formula += (
                f" ; {_formatear_numero(nutriente_kg_ha)} x {_formatear_factor(factor)} = "
                f"{_formatear_numero(elemental_kg_ha)} kg {elemental}/ha"
            )
        return {
            "nutriente_kg_ha": round(nutriente_kg_ha, 2),
            "expresado_como": expresado_como,
            "elemental": elemental,
            "elemental_kg_ha": round(elemental_kg_ha, 2),
            "formula": formula,
        }

    def calcular_dosis_producto(
        self,
        nutriente_objetivo_kg_ha: float,
        objetivo_expresado_como: str,
        porcentaje_en_producto: float,
        expresado_como: str,
    ) -> dict:
        """Kg/ha de producto necesarios para aportar un objetivo de nutriente."""
        self._validar_porcentaje(porcentaje_en_producto)
        self._validar_forma(expresado_como)
        self._validar_forma(objetivo_expresado_como)
        if nutriente_objetivo_kg_ha < 0:
            raise ValueError("El objetivo de nutriente no puede ser negativo.")
        elemental_objetivo, factor_objetivo = FACTORES_A_ELEMENTAL[objetivo_expresado_como]
        elemental_producto, factor_producto = FACTORES_A_ELEMENTAL[expresado_como]
        if elemental_objetivo != elemental_producto:
            raise ValueError(
                f"Objetivo en {objetivo_expresado_como} y producto en {expresado_como} no son el mismo nutriente."
            )
        # Llevar el objetivo a la misma forma en la que esta expresado el grado del producto.
        objetivo_en_forma_producto = nutriente_objetivo_kg_ha * factor_objetivo / factor_producto
        dosis_producto_kg_ha = objetivo_en_forma_producto / (porcentaje_en_producto / 100)
        formula = ""
        if objetivo_expresado_como != expresado_como:
            formula = (
                f"{_formatear_numero(nutriente_objetivo_kg_ha)} kg {objetivo_expresado_como} x "
                f"{_formatear_factor(factor_objetivo)} / {_formatear_factor(factor_producto)} = "
                f"{_formatear_numero(objetivo_en_forma_producto)} kg {expresado_como} ; "
            )
        formula += (
            f"{_formatear_numero(objetivo_en_forma_producto)} / ({_formatear_numero(porcentaje_en_producto)}/100) = "
            f"{_formatear_numero(dosis_producto_kg_ha)} kg/ha de producto"
        )
        return {"dosis_producto_kg_ha": round(dosis_producto_kg_ha, 2), "formula": formula}
