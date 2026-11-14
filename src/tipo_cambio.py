"""Descarga la cotización histórica del dólar en Argentina.

Fuente: API pública de ArgentinaDatos (https://argentinadatos.com).
Se guardan las cotizaciones de venta oficial, MEP (bolsa) y blue en
`data/external/tipo_cambio.csv`.

Uso (desde la raíz del proyecto):
    python -m src.tipo_cambio
"""

from pathlib import Path

import pandas as pd

URL_API = "https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}"
CASAS = {"oficial": "oficial", "bolsa": "mep", "blue": "blue"}
FECHA_DESDE = "2024-01-01"
RUTA_SALIDA = Path(__file__).resolve().parents[1] / "data" / "external" / "tipo_cambio.csv"


def descargar_tipo_cambio(desde: str = FECHA_DESDE) -> pd.DataFrame:
    """Devuelve una tabla con una fila por fecha y una columna por tipo de dólar."""
    series = []
    for casa, nombre in CASAS.items():
        # La API rechaza (403) el User-Agent por defecto de Python.
        datos = pd.read_json(URL_API.format(casa=casa), storage_options={"User-Agent": "Mozilla/5.0"})
        serie = datos.set_index(pd.to_datetime(datos["fecha"]))["venta"].rename(nombre)
        series.append(serie)

    tabla = pd.concat(series, axis=1).sort_index()
    tabla.index.name = "fecha"
    return tabla.loc[desde:]


if __name__ == "__main__":
    tabla = descargar_tipo_cambio()
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(RUTA_SALIDA)
    print(f"Guardado {RUTA_SALIDA} ({len(tabla)} filas, {tabla.index.min():%Y-%m-%d} a {tabla.index.max():%Y-%m-%d})")
