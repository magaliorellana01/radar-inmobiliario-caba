"""Gráficos del proyecto con un estilo común."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

RUTA_FIGURAS = Path(__file__).resolve().parents[1] / "reports" / "figures"

# Paleta: un solo tono para magnitudes, tinta neutra para textos y ejes.
AZUL = "#2a78d6"
AZUL_CLARO = "#9ec5f4"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRILLA = "#e4e3df"
FONDO = "#fcfcfb"


def aplicar_estilo() -> None:
    """Estilo base: ejes y grilla discretos, sin bordes innecesarios."""
    plt.rcParams.update({
        "figure.facecolor": FONDO,
        "axes.facecolor": FONDO,
        "axes.edgecolor": GRILLA,
        "axes.labelcolor": TEXTO_SECUNDARIO,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlecolor": TEXTO,
        "axes.titlelocation": "left",
        "xtick.color": TEXTO_SECUNDARIO,
        "ytick.color": TEXTO,
        "font.size": 10,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.facecolor": FONDO,
    })


def guardar(fig: plt.Figure, nombre: str) -> Path:
    """Guarda la figura en reports/figures/<nombre>.png."""
    RUTA_FIGURAS.mkdir(parents=True, exist_ok=True)
    ruta = RUTA_FIGURAS / f"{nombre}.png"
    fig.savefig(ruta)
    return ruta


def ranking_usd_m2_por_barrio(resumen: pd.DataFrame, mediana_caba: float) -> plt.Figure:
    """Barras horizontales: mediana de USD/m² por barrio, de mayor a menor.

    `resumen` es la salida de `analysis.resumen_por_barrio`.
    """
    aplicar_estilo()
    datos = resumen.sort_values("mediana_usd_m2")
    etiquetas = [f"{b}  ({n:,})".replace(",", ".") for b, n in zip(datos.index, datos["propiedades"])]

    fig, ax = plt.subplots(figsize=(8, 11))
    colores = [AZUL if v >= mediana_caba else AZUL_CLARO for v in datos["mediana_usd_m2"]]
    ax.barh(etiquetas, datos["mediana_usd_m2"], color=colores, height=0.7)

    ax.axvline(mediana_caba, color=TEXTO_SECUNDARIO, linestyle="--", linewidth=1)
    # Etiqueta de la mediana a la altura de la barra más corta, donde no se superpone.
    ax.text(mediana_caba + 0.2, 0, f"Mediana CABA: USD {mediana_caba:.1f}".replace(".", ","),
            color=TEXTO_SECUNDARIO, fontsize=9, va="center")

    top = datos.iloc[-1]
    ax.text(top["mediana_usd_m2"] + 0.2, len(datos) - 1, f"USD {top['mediana_usd_m2']:.1f}".replace(".", ","),
            va="center", color=TEXTO, fontsize=9, fontweight="bold")

    ax.set_xlabel("Mediana de alquiler mensual (USD por m²)")
    ax.grid(axis="x", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.margins(y=0.01)
    ax.set_title("¿Cuánto cuesta alquilar un m² en cada barrio de CABA?")
    agregar_nota(ax,
                 "Una publicación por departamento (la más reciente). Entre paréntesis: cantidad de departamentos.\n"
                 "Barrios con al menos 30 departamentos. Precios en pesos convertidos a USD con dólar MEP del día.\n"
                 "Fuente: avisos de alquiler de departamentos en CABA, sep-2024 a jul-2025.")
    return fig


def agregar_nota(ax: plt.Axes, texto: str) -> None:
    """Nota metodológica debajo del eje x, alineada con el inicio del eje."""
    ax.annotate(texto, xy=(0, 0), xycoords="axes fraction", xytext=(0, -42),
                textcoords="offset points", fontsize=8, color=TEXTO_SECUNDARIO, va="top")
