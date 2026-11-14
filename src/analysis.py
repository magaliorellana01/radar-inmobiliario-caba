"""Funciones de análisis sobre el dataset limpio de alquileres."""

import numpy as np
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


BANDAS_M2 = [15, 30, 40, 50, 70, 100, 150, 1_000]


def usd_m2_por_superficie(df: pd.DataFrame, bandas: list[int] = BANDAS_M2) -> pd.DataFrame:
    """Mediana de USD/m² por rango de superficie."""
    rango = pd.cut(df["m2"].astype(float), bandas, include_lowest=True)
    etiquetas = {i: (f"{i.left:.0f}+" if i.right == bandas[-1] else f"{i.left:.0f}-{i.right:.0f}") for i in rango.cat.categories}
    resumen = df.groupby(rango, observed=True).agg(
        propiedades=("id", "size"),
        mediana_usd_m2=("precio_usd_m2", "median"),
        mediana_precio_usd=("precio_usd", "median"),
    )
    resumen.index = [etiquetas[i] + " m²" for i in resumen.index]
    resumen.index.name = "superficie"
    return resumen.round(1)


def elasticidad_precio_superficie(df: pd.DataFrame, por_barrio: bool = False) -> float:
    """Pendiente de log(precio) sobre log(m²): % que sube el precio si la superficie sube 1%.

    Con `por_barrio=True` se resta la media de cada barrio antes de ajustar,
    así la estimación compara departamentos dentro de un mismo barrio.
    """
    log_precio = np.log(df["precio_usd"])
    log_m2 = np.log(df["m2"].astype(float))
    if por_barrio:
        log_precio = log_precio - log_precio.groupby(df["barrio"]).transform("mean")
        log_m2 = log_m2 - log_m2.groupby(df["barrio"]).transform("mean")
    return float(np.polyfit(log_m2, log_precio, 1)[0])


def m2_por_presupuesto(
    df: pd.DataFrame, minimo: float = 450, maximo: float = 550, min_propiedades: int = MIN_PROPIEDADES
) -> pd.DataFrame:
    """Mediana de m² que se consigue en cada barrio con un alquiler entre `minimo` y `maximo` USD."""
    en_presupuesto = df[df["precio_usd"].between(minimo, maximo)]
    resumen = (
        en_presupuesto.groupby("barrio")
        .agg(propiedades=("id", "size"), mediana_m2=("m2", "median"), mediana_ambientes=("ambientes", "median"))
        .query("propiedades >= @min_propiedades")
        .sort_values("mediana_m2", ascending=False)
    )
    return resumen.astype({"mediana_m2": float}).round(1)


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


# --- Evolución temporal -------------------------------------------------------

def una_por_periodo(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega `periodo` (año-mes del scraping) y deja una fila por `id` y período.

    Los tres scrapings de septiembre de 2024 (23, 24 y 29) se tratan como un
    único período; de cada aviso se conserva la publicación más reciente.
    """
    df = df.assign(periodo=df["fecha_scraping"].dt.strftime("%Y-%m"))
    return df.sort_values("scrap_date").drop_duplicates(["id", "periodo"], keep="last").reset_index(drop=True)


def variacion_composicion_fija(
    df: pd.DataFrame, columna: str, base: str, comparar: str, min_propiedades: int = MIN_PROPIEDADES
) -> dict:
    """Variación % de la mediana de `columna` entre dos períodos, comparando cada barrio consigo mismo.

    Evita que un cambio en la mezcla de barrios (por ejemplo, más avisos de
    Puerto Madero en un período) se confunda con un cambio de precios. Se
    calcula la mediana por barrio en cada período y se promedian los barrios
    con los pesos (cantidad de avisos) del período base. Solo entran barrios
    con al menos `min_propiedades` avisos en ambos períodos.
    """
    datos = df[df["periodo"].isin([base, comparar])]
    tabla = datos.groupby(["barrio", "periodo"])[columna].agg(["median", "size"]).unstack("periodo")
    tabla = tabla[(tabla["size"][[base, comparar]] >= min_propiedades).all(axis=1)]
    pesos = tabla["size"][base]
    valor_base = (tabla["median"][base] * pesos).sum() / pesos.sum()
    valor_comparar = (tabla["median"][comparar] * pesos).sum() / pesos.sum()
    return {
        "variacion_%": round(float(valor_comparar / valor_base - 1) * 100, 1),
        "barrios": len(tabla),
        "avisos_base": int(pesos.sum()),
    }


def inflacion_acumulada(inflacion: pd.DataFrame, desde: str, hasta: str) -> float:
    """Inflación acumulada en % de los meses `desde` a `hasta` (formato 'AAAA-MM', ambos incluidos)."""
    mensual = inflacion.assign(mes=pd.to_datetime(inflacion["fecha"]).dt.strftime("%Y-%m")).set_index("mes")
    tramo = mensual.loc[desde:hasta, "inflacion_mensual"]
    return round(((1 + tramo / 100).prod() - 1) * 100, 1)


def cambios_mismo_aviso(df: pd.DataFrame, base: str, comparar: str) -> pd.DataFrame:
    """Qué pasó con el precio de los avisos publicados en ambos períodos, en la misma moneda.

    Ojo: los avisos que siguen publicados meses después suelen ser los que no
    se alquilaron, por lo que esta muestra NO representa al mercado
    (sesgo de supervivencia).
    """
    a = df[df["periodo"] == base].set_index("id")
    b = df[df["periodo"] == comparar].set_index("id")
    ids = a.index.intersection(b.index)
    a, b = a.loc[ids], b.loc[ids]
    misma_moneda = a["currency"] == b["currency"]
    cambio = (b["price_value"] / a["price_value"] - 1)[misma_moneda]
    moneda = a.loc[misma_moneda, "currency"].map({"$": "Pesos", "USD": "Dólares"})
    return pd.DataFrame({
        "avisos": cambio.groupby(moneda).size(),
        "% sin cambio de precio": (cambio == 0).groupby(moneda).mean() * 100,
        "% suben": (cambio > 0).groupby(moneda).mean() * 100,
        "% bajan": (cambio < 0).groupby(moneda).mean() * 100,
    }).round(1)


def pct_en_usd_composicion_fija(df: pd.DataFrame, base: str, comparar: str) -> dict:
    """% de avisos publicados en USD en cada período, comparando cada barrio consigo mismo."""
    datos = df.assign(en_usd=(df["currency"] == "USD").astype(float))
    datos = datos[datos["periodo"].isin([base, comparar])]
    tabla = datos.groupby(["barrio", "periodo"])["en_usd"].agg(["mean", "size"]).unstack("periodo")
    tabla = tabla[(tabla["size"][[base, comparar]] >= MIN_PROPIEDADES).all(axis=1)]
    pesos = tabla["size"][base]
    return {p: round(float((tabla["mean"][p] * pesos).sum() / pesos.sum() * 100), 1) for p in [base, comparar]}


def pct_en_usd_por_ambientes(df: pd.DataFrame) -> pd.DataFrame:
    """% de avisos publicados en USD por tipología (1 a 4+ ambientes) y período."""
    datos = df.dropna(subset=["ambientes"]).assign(
        en_usd=lambda d: (d["currency"] == "USD") * 100.0,
        tipologia=lambda d: d["ambientes"].clip(upper=4).astype(int).astype(str).replace({"4": "4+"}) + " amb.",
    )
    return datos.pivot_table(index="tipologia", columns="periodo", values="en_usd", aggfunc="mean").round(1)
