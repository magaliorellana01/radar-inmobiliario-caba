"""Funciones de limpieza del dataset de alquileres de departamentos en CABA."""

import pandas as pd

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
