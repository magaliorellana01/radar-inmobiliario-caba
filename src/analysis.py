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
