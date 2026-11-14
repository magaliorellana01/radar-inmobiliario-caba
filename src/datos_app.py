"""Genera el dataset liviano que usa el dashboard de Streamlit.

Toma el dataset limpio, deja una fila por departamento (su publicación más
reciente) y solo las columnas que usa la app. Sin descripción, dirección ni
link del aviso.

Uso (desde la raíz del proyecto, después de `python -m src.cleaning`):
    python -m src.datos_app
"""

from pathlib import Path

import pandas as pd

from src.analysis import ultima_publicacion
from src.cleaning import RAIZ, RUTA_LIMPIO

RUTA_APP = RAIZ / "app" / "data" / "departamentos.parquet"
COLUMNAS_APP = [
    "id", "barrio", "comuna", "zona", "ambientes", "dormitorios", "banos", "cocheras",
    "m2", "precio_usd", "precio_usd_m2", "currency", "fecha_scraping",
]


def generar_datos_app(ruta_limpio: Path = RUTA_LIMPIO) -> pd.DataFrame:
    deptos = ultima_publicacion(pd.read_parquet(ruta_limpio))
    datos = deptos[COLUMNAS_APP].copy()
    datos["moneda_publicacion"] = datos.pop("currency").map({"$": "Pesos", "USD": "Dólares"})
    return datos


if __name__ == "__main__":
    datos = generar_datos_app()
    RUTA_APP.parent.mkdir(parents=True, exist_ok=True)
    datos.to_parquet(RUTA_APP, index=False)
    tamano_kb = RUTA_APP.stat().st_size / 1024
    print(f"Guardado {RUTA_APP.relative_to(RAIZ)}: {len(datos):,} departamentos, {tamano_kb:,.0f} KB")
