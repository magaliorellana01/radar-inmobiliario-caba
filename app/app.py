"""Dashboard de alquileres de departamentos en CABA.

Uso (desde la raíz del proyecto):
    streamlit run app/app.py
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RUTA_DATOS = Path(__file__).parent / "data" / "departamentos.parquet"
URL_REPO = "https://github.com/magaliorellana01/radar-inmobiliario-caba"
URL_DATASET = "https://www.kaggle.com/datasets/martinbasualdo/property-prices-in-caba-zonaprop-data"
AZUL = "#2a78d6"
MIN_DEPTOS_DEFECTO = 10

st.set_page_config(page_title="Radar inmobiliario CABA", page_icon="🏙️", layout="wide")


@st.cache_data
def cargar_datos() -> pd.DataFrame:
    datos = pd.read_parquet(RUTA_DATOS)
    datos["tipologia"] = datos["ambientes"].clip(upper=5).astype("Int64").astype(str).replace({"5": "5+", "<NA>": "Sin dato"})
    return datos


def formato_usd(valor: float) -> str:
    return f"USD {valor:,.0f}".replace(",", ".")


def resumen_por_barrio(datos: pd.DataFrame, min_deptos: int) -> pd.DataFrame:
    resumen = (
        datos.groupby("barrio")
        .agg(
            departamentos=("id", "size"),
            mediana_m2=("m2", "median"),
            mediana_precio_usd=("precio_usd", "median"),
            mediana_usd_m2=("precio_usd_m2", "median"),
            comuna=("comuna", "first"),
        )
        .reset_index()
    )
    resumen["mediana_m2"] = resumen["mediana_m2"].astype(float)
    return resumen[resumen["departamentos"] >= min_deptos]


def grafico_barras(resumen: pd.DataFrame, columna: str, titulo_eje: str, formato: str) -> alt.Chart:
    """Barras horizontales ordenadas de mayor a menor, con tooltip por barrio."""
    alto = max(220, 24 * len(resumen))
    return (
        alt.Chart(resumen)
        .mark_bar(color=AZUL, cornerRadiusEnd=4, height={"band": 0.7})
        .encode(
            x=alt.X(f"{columna}:Q", title=titulo_eje),
            y=alt.Y("barrio:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("barrio:N", title="Barrio"),
                alt.Tooltip("mediana_m2:Q", title="Superficie mediana (m²)", format=".0f"),
                alt.Tooltip("mediana_precio_usd:Q", title="Alquiler mediano (USD)", format=",.0f"),
                alt.Tooltip("mediana_usd_m2:Q", title="USD por m²", format=".1f"),
                alt.Tooltip("departamentos:Q", title="Departamentos"),
            ],
        )
        .properties(height=alto)
    )


datos = cargar_datos()

# --- Encabezado ---------------------------------------------------------------
st.title("Radar inmobiliario CABA")
st.markdown(
    "¿Cuánto cuesta alquilar un departamento en cada barrio de Buenos Aires? "
    f"Elegí tu presupuesto y lo que necesitás. Datos de **{len(datos):,}** departamentos publicados en Zonaprop "
    "entre septiembre de 2024 y julio de 2025.".replace(",", ".")
)

# --- Filtros ------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    presupuesto = st.slider(
        "Presupuesto mensual (USD)", min_value=100, max_value=5000, value=(400, 700), step=50,
        help="Los precios publicados en pesos se convirtieron a dólares con el dólar MEP del día del relevamiento.",
    )
    tipologias = ["1", "2", "3", "4", "5+"]
    ambientes = st.multiselect("Ambientes", tipologias, default=tipologias, format_func=lambda a: f"{a} amb.")
    barrios = st.multiselect("Barrios", sorted(datos["barrio"].unique()), placeholder="Todos los barrios")
    min_deptos = st.number_input(
        "Mínimo de departamentos por barrio", min_value=1, max_value=100, value=MIN_DEPTOS_DEFECTO,
        help="Los barrios con menos departamentos que este número no se muestran en los gráficos: "
             "con pocos datos la mediana no es confiable.",
    )

filtro = datos["precio_usd"].between(*presupuesto) & datos["tipologia"].isin(ambientes)
if barrios:
    filtro &= datos["barrio"].isin(barrios)
seleccion = datos[filtro]

if seleccion.empty:
    st.warning("No hay departamentos con esos filtros. Probá ampliar el presupuesto o los ambientes.")
    st.stop()

# --- Indicadores --------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Departamentos", f"{len(seleccion):,}".replace(",", "."))
c2.metric("Alquiler mediano", formato_usd(seleccion["precio_usd"].median()))
c3.metric("Superficie mediana", f"{seleccion['m2'].median():.0f} m²")
c4.metric("Mediana por m²", f"USD {seleccion['precio_usd_m2'].median():.1f}".replace(".", ","))

resumen = resumen_por_barrio(seleccion, min_deptos)
excluidos = seleccion["barrio"].nunique() - len(resumen)

# --- Pestañas -----------------------------------------------------------------
tab_espacio, tab_m2, tab_tabla = st.tabs(["¿Cuánto espacio consigo?", "Precio por m²", "Tabla por barrio"])

with tab_espacio:
    st.subheader("Superficie mediana que se consigue en cada barrio")
    st.caption("Con el presupuesto y los ambientes elegidos. Pasá el mouse sobre una barra para ver el detalle.")
    if resumen.empty:
        st.info("Ningún barrio alcanza el mínimo de departamentos. Bajá el mínimo en el panel de filtros.")
    else:
        st.altair_chart(grafico_barras(resumen, "mediana_m2", "Superficie mediana (m²)", ".0f"), width="stretch")

with tab_m2:
    st.subheader("Precio mediano por m² en cada barrio")
    st.caption("Alquiler mensual en USD dividido por la superficie, con los filtros elegidos.")
    if resumen.empty:
        st.info("Ningún barrio alcanza el mínimo de departamentos. Bajá el mínimo en el panel de filtros.")
    else:
        st.altair_chart(grafico_barras(resumen, "mediana_usd_m2", "USD por m²", ".1f"), width="stretch")

with tab_tabla:
    tabla = resumen.sort_values("mediana_m2", ascending=False).rename(columns={
        "barrio": "Barrio", "comuna": "Comuna", "departamentos": "Departamentos",
        "mediana_m2": "Superficie mediana (m²)", "mediana_precio_usd": "Alquiler mediano (USD)",
        "mediana_usd_m2": "USD por m²",
    })[["Barrio", "Comuna", "Departamentos", "Superficie mediana (m²)", "Alquiler mediano (USD)", "USD por m²"]]
    st.dataframe(tabla, hide_index=True, width="stretch", column_config={
        "Superficie mediana (m²)": st.column_config.NumberColumn(format="%.0f"),
        "Alquiler mediano (USD)": st.column_config.NumberColumn(format="%.0f"),
        "USD por m²": st.column_config.NumberColumn(format="%.1f"),
    })
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8"), "radar_inmobiliario_caba.csv", "text/csv")

if excluidos > 0:
    st.caption(f"{excluidos} barrio(s) con menos de {min_deptos} departamentos no se muestran.")

# --- Pie ----------------------------------------------------------------------
st.divider()
st.caption(
    "Precios publicados (no de cierre). Una publicación por departamento: la más reciente. "
    "Precios en pesos convertidos a USD con el dólar MEP del día. "
    f"Metodología y análisis completo en [GitHub]({URL_REPO}). "
    f"Datos: [Property prices in CABA - Zonaprop data]({URL_DATASET}) (martinbasualdo, licencia MIT)."
)
