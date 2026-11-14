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


def formato_usd(valor: float) -> str:
    """1310.5 -> 'USD 1.311' (separador de miles argentino)."""
    return f"USD {valor:,.0f}".replace(",", ".")


def precio_por_ambientes(resumen: pd.DataFrame) -> plt.Figure:
    """Barras con la mediana del alquiler mensual por ambientes y el rango P25-P75.

    `resumen` es la salida de `analysis.resumen_por_ambientes`.
    """
    aplicar_estilo()
    fig, ax = plt.subplots(figsize=(8, 5.5))
    x = range(len(resumen))
    medianas = resumen["mediana_precio_usd"]

    ax.bar(x, medianas, color=AZUL, width=0.6)
    ax.vlines(x, resumen["p25_precio_usd"], resumen["p75_precio_usd"], color=TEXTO, linewidth=1.5)
    ax.scatter(x, resumen["p25_precio_usd"], marker="_", s=120, color=TEXTO, linewidths=1.5)
    ax.scatter(x, resumen["p75_precio_usd"], marker="_", s=120, color=TEXTO, linewidths=1.5)

    for i, (mediana, m2) in enumerate(zip(medianas, resumen["mediana_m2"])):
        ax.text(i + 0.33, mediana, f"{formato_usd(mediana)}\n{m2:.0f} m²", va="center", ha="left",
                fontsize=9, color=TEXTO, linespacing=1.3)

    ax.set_xticks(list(x), [f"{a} amb." for a in resumen.index])
    ax.set_ylabel("Alquiler mensual (USD)")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}".replace(",", "."))
    ax.grid(axis="y", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.5, len(resumen) - 0.1)
    ax.set_title("El alquiler crece más rápido que la cantidad de ambientes")
    agregar_nota(ax,
                 "Barra: mediana del alquiler mensual. Línea: rango del 50% central (percentiles 25 a 75).\n"
                 "Junto a cada barra: mediana de alquiler y de superficie. Una publicación por departamento.\n"
                 "Precios en pesos convertidos a USD con dólar MEP del día. Fuente: avisos sep-2024 a jul-2025.")
    return fig


def usd_m2_chico_vs_grande(comparacion: pd.DataFrame, excluir: list[str] | None = None) -> plt.Figure:
    """Gráfico de pesas: USD/m² de un departamento chico vs. uno grande en cada barrio.

    `comparacion` es la salida de `analysis.usd_m2_por_ambientes_en_barrio`.
    """
    aplicar_estilo()
    datos = comparacion.drop(index=excluir or [], errors="ignore")
    col_chico, col_grande, col_dif = datos.columns[:3]
    chico, grande = (c.split("_")[2] for c in (col_chico, col_grande))
    color_chico, color_grande = "#86b6ef", "#1c5cab"

    fig, ax = plt.subplots(figsize=(8, 6.5))
    y = range(len(datos))
    ax.hlines(y, datos[col_chico], datos[col_grande], color=GRILLA, linewidth=3, zorder=1)
    ax.scatter(datos[col_chico], y, s=70, color=color_chico, zorder=2, label=f"{chico} ambientes",
               edgecolors=FONDO, linewidths=2)
    ax.scatter(datos[col_grande], y, s=70, color=color_grande, zorder=3, label=f"{grande} ambientes",
               edgecolors=FONDO, linewidths=2)

    borde = datos[[col_chico, col_grande]].max(axis=1)
    for i, (x_fin, dif) in enumerate(zip(borde, datos[col_dif])):
        ax.text(x_fin + 0.35, i, f"{dif:+.0f}%", va="center", fontsize=9,
                color=TEXTO if dif > 0 else TEXTO_SECUNDARIO, fontweight="bold" if dif > 0 else "normal")

    ax.set_yticks(list(y), datos.index)
    ax.set_xlabel("Mediana de alquiler mensual (USD por m²)")
    ax.grid(axis="x", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(left=datos[[col_chico, col_grande]].min().min() - 1, right=borde.max() + 2)
    ax.legend(loc="lower right", frameon=False, ncols=2, bbox_to_anchor=(1, 1.0), fontsize=9)
    ax.set_title(f"¿El m² de un {grande} ambientes es más caro que el de un {chico}?", pad=24)
    nota = (f"Mediana de USD/m² por tipología dentro de cada barrio. Porcentaje: diferencia del {grande} amb. "
            f"respecto del {chico} amb.\nBarrios con al menos 20 departamentos de cada tipología.")
    if excluir:
        nota += f" Se excluye {', '.join(excluir)} (escala muy superior, diferencia < 1%)."
    agregar_nota(ax, nota + "\nUna publicación por departamento. Fuente: avisos sep-2024 a jul-2025.")
    return fig


def agregar_nota(ax: plt.Axes, texto: str) -> None:
    """Nota metodológica debajo del eje x, alineada con el inicio del eje."""
    ax.annotate(texto, xy=(0, 0), xycoords="axes fraction", xytext=(0, -42),
                textcoords="offset points", fontsize=8, color=TEXTO_SECUNDARIO, va="top")
