"""Funciones de limpieza del dataset de alquileres de departamentos en CABA.

Uso (desde la raíz del proyecto):
    python -m src.cleaning
"""

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RAW = RAIZ / "data" / "raw" / "alquiler_departamentos_consolidado.pkl"
RUTA_TIPO_CAMBIO = RAIZ / "data" / "external" / "tipo_cambio.csv"
RUTA_LIMPIO = RAIZ / "data" / "processed" / "alquileres_limpio.parquet"

# Cada característica de `Features` se identifica por su etiqueta, no por su
# posición en la lista (el orden varía entre publicaciones).
# Etiquetas presentes en el dataset: "m² tot.", "amb.", "dorm.", "baño",
# "baños", "coch.". Todos los valores son enteros sin separador de miles.
PATRONES_FEATURES = {
    "m2": r"(\d+)\s*m² tot\.",
    "ambientes": r"(\d+)\s*amb\.",
    "dormitorios": r"(\d+)\s*dorm\.",
    "banos": r"(\d+)\s*baños?",
    "cocheras": r"(\d+)\s*coch\.",
}


def parsear_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extrae superficie, ambientes, dormitorios, baños y cocheras de `Features`.

    Devuelve una copia del DataFrame con una columna nueva por característica
    (tipo Int64, admite nulos). Si una publicación no informa una
    característica, el valor queda como nulo: no se asume 0.
    """
    df = df.copy()
    texto = df["Features"].str.join(" | ")

    for columna, patron in PATRONES_FEATURES.items():
        df[columna] = texto.str.extract(patron)[0].astype("Int64")

    return df


# Los 48 barrios oficiales de CABA agrupados por comuna.
COMUNAS = {
    1: ["Retiro", "San Nicolás", "Puerto Madero", "San Telmo", "Monserrat", "Constitución"],
    2: ["Recoleta"],
    3: ["Balvanera", "San Cristóbal"],
    4: ["La Boca", "Barracas", "Parque Patricios", "Nueva Pompeya"],
    5: ["Almagro", "Boedo"],
    6: ["Caballito"],
    7: ["Flores", "Parque Chacabuco"],
    8: ["Villa Soldati", "Villa Riachuelo", "Villa Lugano"],
    9: ["Liniers", "Mataderos", "Parque Avellaneda"],
    10: ["Villa Real", "Monte Castro", "Versalles", "Floresta", "Vélez Sársfield", "Villa Luro"],
    11: ["Villa General Mitre", "Villa Devoto", "Villa del Parque", "Villa Santa Rita"],
    12: ["Coghlan", "Saavedra", "Villa Urquiza", "Villa Pueyrredón"],
    13: ["Núñez", "Belgrano", "Colegiales"],
    14: ["Palermo"],
    15: ["Chacarita", "Villa Crespo", "La Paternal", "Villa Ortúzar", "Agronomía", "Parque Chas"],
}
BARRIO_A_COMUNA = {b: c for c, barrios in COMUNAS.items() for b in barrios}

# Nombres que usan los portales pero no son barrios oficiales (o están mal
# escritos). Las zonas informales se asignan al barrio donde está la mayor
# parte de su superficie. "Otro" no permite identificar el barrio -> nulo.
NORMALIZACION_BARRIOS = {
    "Barrio Norte": "Recoleta",
    "Centro / Microcentro": "San Nicolás",
    "Tribunales": "San Nicolás",
    "Catalinas": "Retiro",
    "Congreso": "Balvanera",
    "Once": "Balvanera",
    "Abasto": "Balvanera",
    "Parque Centenario": "Caballito",
    "Pompeya": "Nueva Pompeya",
    "San Cristobal": "San Cristóbal",
    "Velez Sarsfield": "Vélez Sársfield",
    "Villa Ortuzar": "Villa Ortúzar",
    "Otro": None,
}


def parsear_location(df: pd.DataFrame) -> pd.DataFrame:
    """Separa `Location` en `zona`, `barrio` (oficial) y `comuna`.

    `Location` tiene dos formatos:
    - "Palermo, Capital Federal": el barrio está a la izquierda.
    - "Palermo Hollywood, Palermo": subzona a la izquierda, barrio a la derecha.

    `zona` conserva el nombre más específico publicado (útil para análisis
    finos, ej. Palermo Soho vs. Palermo Chico). `barrio` se normaliza a los 48
    barrios oficiales; si no se puede identificar queda nulo.
    """
    df = df.copy()
    partes = df["Location"].str.split(",", n=1, expand=True)
    izquierda = partes[0].str.strip()
    derecha = partes[1].str.strip()

    df["zona"] = izquierda
    barrio = izquierda.where(derecha == "Capital Federal", derecha)
    df["barrio"] = barrio.replace(NORMALIZACION_BARRIOS)
    df["comuna"] = df["barrio"].map(BARRIO_A_COMUNA).astype("Int64")

    no_oficiales = set(df["barrio"].dropna()) - set(BARRIO_A_COMUNA)
    if no_oficiales:
        raise ValueError(f"Barrios sin mapear a uno oficial: {sorted(no_oficiales)}")

    return df


def parsear_precio(df: pd.DataFrame) -> pd.DataFrame:
    """Separa `Price` en `currency` ("USD" o "$") y `price_value` (numérico).

    Ejemplos: "USD 1.100" -> ("USD", 1100.0); "$ 470.000" -> ("$", 470000.0).
    "Consultar precio" queda con ambos valores nulos.
    """
    df = df.copy()
    df["currency"] = df["Price"].str.extract(r"(USD|\$)")[0]
    df["price_value"] = pd.to_numeric(
        df["Price"]
        .str.replace(".", "", regex=False)
        .str.replace("USD", "", regex=False)
        .str.replace("$", "", regex=False),
        errors="coerce",
    )
    return df


def convertir_a_usd(df: pd.DataFrame, tipo_cambio: pd.DataFrame, dolar: str = "mep") -> pd.DataFrame:
    """Agrega `tc` (pesos por dólar) y `precio_usd` usando la cotización del día del scraping.

    Se usa el dólar MEP por defecto: en 2024 la brecha con el oficial era de
    ~26%, y los alquileres en dólares se pagan con dólares de mercado, no al
    oficial. Si una fecha no tuviera cotización se toma la última disponible.

    `tipo_cambio` es la tabla de `data/external/tipo_cambio.csv`
    (columnas: fecha, oficial, mep, blue).
    """
    df = df.copy()
    tc = tipo_cambio[["fecha", dolar]].rename(columns={dolar: "tc"})
    tc["fecha"] = pd.to_datetime(tc["fecha"])

    df["fecha_scraping"] = df["scrap_date"].dt.normalize()
    orden_original = df.index
    df = pd.merge_asof(
        df.reset_index().sort_values("fecha_scraping"),
        tc.sort_values("fecha"),
        left_on="fecha_scraping",
        right_on="fecha",
        direction="backward",
    ).drop(columns="fecha").set_index("index").loc[orden_original]
    df.index.name = None

    df["precio_usd"] = df["price_value"].where(
        df["currency"] == "USD", df["price_value"] / df["tc"]
    ).round(1)
    return df


# Frases que indican alquiler temporario. Se excluyeron términos sueltos que
# generaban falsos positivos: "diario" ("comedor diario", ~4.800 avisos),
# "noches" ("días y noches soñadas") y "temporada" ("pileta en temporada").
REGEX_TEMPORARIO = (
    r"(?<!no es )alquiler temporari[oa]|(?<!no es )alquiler temporal|por temporada|"
    r"por d[ií]as?\b|por semana|semanal|quincena|quincenal|"
    r"estad[ií]a|m[ií]nimo.{0,20}(?:d[ií]as|noches)|por noche"
)
REGEX_ANUAL = r"alquiler anual|alquileres anual|valor primer año|primer año.*usd|segundo año"
REGEX_VENTA = r"\bventa\b|en venta|precio venta|venta directa|venta urgente|venta con renta"


def marcar_casos_especiales(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega marcas booleanas a partir de la descripción del aviso.

    - `es_temporario`: menciona una modalidad de alquiler temporario.
    - `es_anual`: menciona valores anuales o por año de contrato.
    - `posible_venta`: precio >= USD 10.000 publicado en USD y la descripción
      menciona venta (criterio definido en 01_exploracion.ipynb).
    """
    df = df.copy()
    descripcion = df["Description"].fillna("")
    df["es_temporario"] = descripcion.str.contains(REGEX_TEMPORARIO, case=False, regex=True)
    df["es_anual"] = descripcion.str.contains(REGEX_ANUAL, case=False, regex=True)
    df["posible_venta"] = (
        df["currency"].eq("USD")
        & (df["price_value"] >= 10_000)
        & descripcion.str.contains(REGEX_VENTA, case=False, regex=True)
    )
    return df


# Umbrales de valores plausibles para un alquiler mensual de departamento.
PRECIO_USD_MIN, PRECIO_USD_MAX = 100, 15_000
M2_MIN, M2_MAX = 15, 1_000
AMBIENTES_MAX = 10
USD_M2_MIN, USD_M2_MAX = 2, 100


def aplicar_filtros(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica los filtros en orden y devuelve (df_filtrado, embudo).

    `embudo` registra cuántos registros elimina cada filtro, para documentar
    el universo final del análisis.
    """
    usd_m2 = df["precio_usd"] / df["m2"]
    filtros = [
        ("Sin precio publicado (\"Consultar precio\")", df["precio_usd"].isna()),
        ("Posible publicación de venta", df["posible_venta"]),
        ("Alquiler temporario", df["es_temporario"]),
        (f"Precio fuera de USD {PRECIO_USD_MIN}-{PRECIO_USD_MAX:,}", ~df["precio_usd"].between(PRECIO_USD_MIN, PRECIO_USD_MAX)),
        ("Sin superficie informada", df["m2"].isna()),
        (f"Superficie fuera de {M2_MIN}-{M2_MAX:,} m²", ~df["m2"].between(M2_MIN, M2_MAX)),
        (f"Más de {AMBIENTES_MAX} ambientes", df["ambientes"] > AMBIENTES_MAX),
        (f"USD/m² fuera de {USD_M2_MIN}-{USD_M2_MAX}", ~usd_m2.between(USD_M2_MIN, USD_M2_MAX)),
        ("Barrio no identificado", df["barrio"].isna()),
    ]

    filas = [{"paso": "Dataset original", "eliminados": 0, "restantes": len(df)}]
    mantener = pd.Series(True, index=df.index)
    for nombre, excluir in filtros:
        excluir = excluir.fillna(False).astype(bool)
        eliminados = (mantener & excluir).sum()
        mantener &= ~excluir
        filas.append({"paso": nombre, "eliminados": int(eliminados), "restantes": int(mantener.sum())})

    embudo = pd.DataFrame(filas)
    embudo["% del original"] = (embudo["restantes"] / len(df) * 100).round(1)
    return df[mantener].copy(), embudo


COLUMNAS_CONSTANTES = ["type_building", "type_operation"]


def limpiar_dataset(
    ruta_raw: Path = RUTA_RAW,
    ruta_tipo_cambio: Path = RUTA_TIPO_CAMBIO,
    dolar: str = "mep",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corre la limpieza completa y devuelve (df_limpio, embudo).

    El resultado conserva el historial: un mismo `id` puede aparecer en varias
    fechas de scraping. Para análisis de corte transversal conviene quedarse
    con una fila por `id` (por ejemplo, la última publicación).
    """
    df = pd.read_pickle(ruta_raw)
    tipo_cambio = pd.read_csv(ruta_tipo_cambio)

    df = parsear_features(df)
    df = parsear_location(df)
    df = parsear_precio(df)
    df = convertir_a_usd(df, tipo_cambio, dolar=dolar)
    df = marcar_casos_especiales(df)
    df, embudo = aplicar_filtros(df)

    df["precio_usd_m2"] = (df["precio_usd"] / df["m2"]).round(2)
    df = df.drop(columns=COLUMNAS_CONSTANTES).reset_index(drop=True)
    return df, embudo


if __name__ == "__main__":
    df_limpio, embudo = limpiar_dataset()
    RUTA_LIMPIO.parent.mkdir(parents=True, exist_ok=True)
    df_limpio.to_parquet(RUTA_LIMPIO, index=False)
    print(embudo.to_string(index=False))
    print(f"\nGuardado {RUTA_LIMPIO.relative_to(RAIZ)}: {len(df_limpio):,} filas, {df_limpio['id'].nunique():,} propiedades únicas")
