"""Descarga datos macroeconómicos de Argentina usados en el análisis.

Fuente: API pública de ArgentinaDatos (https://argentinadatos.com).
- Cotizaciones de venta del dólar oficial, MEP (bolsa) y blue
  -> `data/external/tipo_cambio.csv`.
- Inflación mensual (IPC, INDEC) -> `data/external/inflacion.csv`.

Uso (desde la raíz del proyecto):
    python -m src.tipo_cambio
"""

from pathlib import Path

import pandas as pd

URL_BASE = "https://api.argentinadatos.com/v1"
CASAS = {"oficial": "oficial", "bolsa": "mep", "blue": "blue"}
FECHA_DESDE = "2024-01-01"
CARPETA_SALIDA = Path(__file__).resolve().parents[1] / "data" / "external"
RUTA_TIPO_CAMBIO = CARPETA_SALIDA / "tipo_cambio.csv"
RUTA_INFLACION = CARPETA_SALIDA / "inflacion.csv"


def _leer_api(endpoint: str) -> pd.DataFrame:
    # La API rechaza (403) el User-Agent por defecto de Python.
    return pd.read_json(f"{URL_BASE}/{endpoint}", storage_options={"User-Agent": "Mozilla/5.0"})


def descargar_tipo_cambio(desde: str = FECHA_DESDE) -> pd.DataFrame:
    """Devuelve una tabla con una fila por fecha y una columna por tipo de dólar."""
    series = []
    for casa, nombre in CASAS.items():
        datos = _leer_api(f"cotizaciones/dolares/{casa}")
        serie = datos.set_index(pd.to_datetime(datos["fecha"]))["venta"].rename(nombre)
        series.append(serie)

    tabla = pd.concat(series, axis=1).sort_index()
    tabla.index.name = "fecha"
    return tabla.loc[desde:]


def descargar_inflacion(desde: str = FECHA_DESDE) -> pd.DataFrame:
    """Inflación mensual en %. `fecha` es el último día del mes que mide."""
    datos = _leer_api("finanzas/indices/inflacion")
    tabla = datos.set_index(pd.to_datetime(datos["fecha"]))["valor"].rename("inflacion_mensual").to_frame()
    tabla.index.name = "fecha"
    return tabla.sort_index().loc[desde:]


if __name__ == "__main__":
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    for tabla, ruta in [(descargar_tipo_cambio(), RUTA_TIPO_CAMBIO), (descargar_inflacion(), RUTA_INFLACION)]:
        tabla.to_csv(ruta)
        print(f"Guardado {ruta.name} ({len(tabla)} filas, {tabla.index.min():%Y-%m-%d} a {tabla.index.max():%Y-%m-%d})")
