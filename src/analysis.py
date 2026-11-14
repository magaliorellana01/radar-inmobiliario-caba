"""Funciones de análisis sobre el dataset limpio de alquileres."""

import pandas as pd

MIN_PROPIEDADES = 30


def ultima_publicacion(df: pd.DataFrame) -> pd.DataFrame:
    """Deja una fila por propiedad (`id`): su publicación más reciente.

    El dataset limpio conserva el historial de cada aviso en varias fechas de
    scraping. Para comparar barrios o tipologías cada departamento debe contar
    una sola vez; si no, los avisos que estuvieron publicados más tiempo
    pesarían más en las estadísticas.
    """
    return (
        df.sort_values("scrap_date")
        .drop_duplicates("id", keep="last")
        .reset_index(drop=True)
    )


def resumen_por_barrio(df: pd.DataFrame, min_propiedades: int = MIN_PROPIEDADES) -> pd.DataFrame:
    """Mediana de precio y de USD/m² por barrio, ordenado de mayor a menor USD/m².

    Se usa la mediana y no el promedio porque los precios tienen una
    distribución asimétrica (pocos departamentos muy caros suben el promedio).
    Se excluyen los barrios con menos de `min_propiedades` departamentos, cuya
    mediana no es representativa.
    """
    resumen = (
        df.groupby("barrio")
        .agg(
            propiedades=("id", "size"),
            comuna=("comuna", "first"),
            mediana_usd_m2=("precio_usd_m2", "median"),
            p25_usd_m2=("precio_usd_m2", lambda s: s.quantile(0.25)),
            p75_usd_m2=("precio_usd_m2", lambda s: s.quantile(0.75)),
            mediana_precio_usd=("precio_usd", "median"),
            mediana_m2=("m2", "median"),
        )
        .query("propiedades >= @min_propiedades")
        .sort_values("mediana_usd_m2", ascending=False)
    )
    return resumen.round(1)


AMBIENTES_TOPE = 5
CORREDOR_NORTE = ["Puerto Madero", "Palermo", "Núñez", "Belgrano", "Retiro", "Recoleta"]


def agrupar_ambientes(ambientes: pd.Series) -> pd.Series:
    """Agrupa los departamentos de 5 o más ambientes en una sola categoría ("5+")."""
    etiquetas = ambientes.clip(upper=AMBIENTES_TOPE).astype("Int64").astype(str)
    return etiquetas.replace({str(AMBIENTES_TOPE): f"{AMBIENTES_TOPE}+", "<NA>": pd.NA})


def resumen_por_ambientes(df: pd.DataFrame) -> pd.DataFrame:
    """Precio, superficie y USD/m² por cantidad de ambientes (1 a 5+).

    Incluye el % de avisos ubicados en el corredor norte para detectar efectos
    de composición: los departamentos grandes se concentran en barrios caros.
    """
    datos = df.assign(ambientes_grupo=agrupar_ambientes(df["ambientes"])).dropna(subset=["ambientes_grupo"])
    resumen = datos.groupby("ambientes_grupo").agg(
        propiedades=("id", "size"),
        mediana_precio_usd=("precio_usd", "median"),
        p25_precio_usd=("precio_usd", lambda s: s.quantile(0.25)),
        p75_precio_usd=("precio_usd", lambda s: s.quantile(0.75)),
        mediana_m2=("m2", "median"),
        mediana_usd_m2=("precio_usd_m2", "median"),
        pct_publicado_en_usd=("currency", lambda s: (s == "USD").mean() * 100),
        pct_corredor_norte=("barrio", lambda s: s.isin(CORREDOR_NORTE).mean() * 100),
    )
    resumen["aumento_vs_anterior_%"] = resumen["mediana_precio_usd"].pct_change() * 100
    return resumen.round(1)


def usd_m2_por_ambientes_en_barrio(
    df: pd.DataFrame, chico: int = 2, grande: int = 4, min_propiedades: int = 20
) -> pd.DataFrame:
    """Compara la mediana de USD/m² entre dos tipologías dentro de cada barrio.

    Controla el efecto barrio: muestra si, en un mismo barrio, el m² de un
    departamento grande es más caro o más barato que el de uno chico. Solo
    incluye barrios con al menos `min_propiedades` en ambas tipologías.
    """
    datos = df[df["ambientes"].isin([chico, grande])]
    tabla = datos.groupby(["barrio", "ambientes"])["precio_usd_m2"].agg(["median", "size"]).unstack("ambientes")
    suficientes = (tabla["size"][chico] >= min_propiedades) & (tabla["size"][grande] >= min_propiedades)
    comparacion = pd.DataFrame({
        f"usd_m2_{chico}_amb": tabla["median"][chico],
        f"usd_m2_{grande}_amb": tabla["median"][grande],
    })[suficientes]
    comparacion["diferencia_%"] = (comparacion.iloc[:, 1] / comparacion.iloc[:, 0] - 1) * 100
    return comparacion.sort_values("diferencia_%").round(1)
