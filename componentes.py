"""Piezas visuales de la app: tarjetas de indicadores, gráficos y formato de tablas."""
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

MAXIMO_BARRAS = 15

# Mismos colores que .streamlit/config.toml. Las tarjetas y las etiquetas de los gráficos no siguen el tema solas.
PALETA = {
    "light": {"texto": "#1F2328", "suave": "#5B6470", "borde": "#E3E6EA", "fondo": "#FFFFFF", "barras": "#0096A3"},
    # El turquesa de la marca (#00A9B7) no llega a 3:1 sobre blanco; en claro las barras van un paso más oscuras.
    "dark": {"texto": "#E6E8EB", "suave": "#A3AAB4", "borde": "#30343B", "fondo": "#1C1F25", "barras": "#00A9B7"},
}


def colores():
    return PALETA["dark" if st.context.theme.type == "dark" else "light"]


def miles(numero):
    return f"{numero:,}".replace(",", ".")


def tarjetas(items):
    """Fila de indicadores de igual altura. items: (etiqueta, valor, detalle); valor None = sin dato."""
    c = colores()
    piezas = []
    for etiqueta, valor, detalle in items:
        sin_dato = valor is None
        piezas.append(
            f'<div style="border:1px solid {c["borde"]};border-radius:8px;padding:14px 18px;background:{c["fondo"]};">'
            f'<div style="font-size:0.75rem;letter-spacing:0.05em;text-transform:uppercase;color:{c["suave"]};">{escape(etiqueta)}</div>'
            f'<div style="font-size:1.85rem;font-weight:700;line-height:1.25;margin:6px 0 4px;'
            f'color:{c["suave"] if sin_dato else c["texto"]};">{"—" if sin_dato else escape(str(valor))}</div>'
            f'<div style="font-size:0.85rem;color:{c["suave"]};">{escape(detalle)}</div>'
            "</div>"
        )
    st.html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;">'
        + "".join(piezas) + "</div>"
    )


def _estilo(grafico):
    c = colores()
    return (
        grafico.configure_axis(
            labelFontSize=12, labelColor=c["suave"], gridColor=c["borde"], domain=False, ticks=False, titleFontSize=12,
        )
        .configure_view(strokeWidth=0)
    )


def grafico_por_dia(serie, medida):
    """Columnas por día: todos los días del período (los que no tuvieron cierres en 0), pico marcado y promedio."""
    dias = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
    datos = serie.reindex(dias, fill_value=0).rename_axis("fecha").reset_index(name=medida)
    datos["Día"] = datos["fecha"].dt.strftime("%d-%m")
    datos["Fecha"] = datos["fecha"].dt.strftime("%d-%m-%Y")
    c = colores()
    x = alt.X("Día:O", sort=None, title=None, axis=alt.Axis(labelAngle=0))
    y = alt.Y(f"{medida}:Q", title=None, axis=alt.Axis(tickCount=5))
    columnas = alt.Chart(datos).mark_bar(
        color=c["barras"], size=24, cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
    ).encode(x=x, y=y, tooltip=[alt.Tooltip("Fecha:N"), alt.Tooltip(f"{medida}:Q")])
    pico = alt.Chart(datos.nlargest(1, medida)).mark_text(dy=-9, fontWeight="bold", fontSize=12, color=c["texto"]).encode(
        x=x, y=y, text=f"{medida}:Q"
    )
    promedio = alt.Chart(pd.DataFrame({"Promedio": [round(serie.mean())]})).mark_rule(
        color=c["suave"], strokeWidth=1, opacity=0.8
    ).encode(y="Promedio:Q", tooltip=[alt.Tooltip("Promedio:Q")])
    return _estilo((columnas + promedio + pico).properties(height=300))


def grafico_ranking(tabla, categoria, medida, titulo_medida):
    """Barras horizontales de mayor a menor (las primeras MAXIMO_BARRAS), con el valor en la punta."""
    c = colores()
    datos = tabla.nlargest(MAXIMO_BARRAS, medida)
    y = alt.Y(f"{categoria}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240, labelColor=c["texto"]))
    x = alt.X(f"{medida}:Q", title=None, axis=alt.Axis(tickCount=4))
    barras = alt.Chart(datos).mark_bar(
        color=c["barras"], size=20, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
    ).encode(x=x, y=y, tooltip=[alt.Tooltip(f"{categoria}:N"), alt.Tooltip(f"{medida}:Q", title=titulo_medida)])
    valores = barras.mark_text(align="left", dx=6, fontSize=12, color=c["texto"]).encode(text=f"{medida}:Q")
    return _estilo((barras + valores).properties(height=32 * len(datos) + 24))


# Nombres para mostrar en pantalla. El Excel descargado mantiene los nombres de columna acordados con el papá.
ETIQUETAS = {
    "Fecha cierre": "Fecha de cierre",
    "Cod OF": "Oferta (OF)",
    "MTA": "Tarea (MTA)",
    "MTA adi": "Tarea adicional",
    "Tipo tarea": "Tipo de tarea",
    "Motivo": "Motivo",
    "Técnico": "Técnico",
    "Técnico adi": "Técnico adicional",
    "CT específico": "Centro técnico",
    "Deco adi": "Decos adicionales",
    "Router": "Routers",
    "APK": "APK",
    "OF": "Órdenes (OF)",
    "Tareas": "Tareas",
    "Nombre Tecnico": "Técnico",
    "CT General": "Centro técnico",
    "CT Original": "CT original",
    "Tecnico ID": "ID",
    "Estado inicio": "Inicio de labores",
    "Cantidad tareas cerradas": "Tareas del día",
    "Instalaciones": "Instalaciones",
    "Ultima hora cierre": "Último cierre",
    "Ultima fecha/hora cierre": "Fecha del último cierre",
}

COLUMNAS_NUMERICAS = {"Deco adi", "Router", "APK", "OF", "Tareas", "Cantidad tareas cerradas", "Instalaciones", "SSTT", "PV"}

# Ancho en píxeles de las columnas de texto largo, para que no se corten.
ANCHOS = {"Tipo tarea": 190, "Motivo": 230, "Técnico": 250, "Técnico adi": 200, "MTA adi": 150,
          "Nombre Tecnico": 250, "Correo": 280, "Ultima fecha/hora cierre": 170}


def tabla(datos, alto=None):
    """Tabla sin números de fila, con encabezados en español, fechas dd-mm-aaaa y celdas vacías en blanco."""
    vista = datos.copy()
    config = {}
    for col in vista.columns:
        etiqueta = ETIQUETAS.get(col, col)
        if col == "Fecha cierre":
            vista[col] = pd.to_datetime(vista[col])
            config[col] = st.column_config.DateColumn(etiqueta, format="DD-MM-YYYY")
        elif col in COLUMNAS_NUMERICAS:
            config[col] = st.column_config.NumberColumn(etiqueta, format="localized")
        else:
            if not pd.api.types.is_numeric_dtype(vista[col]):
                vista[col] = vista[col].astype(object).where(vista[col].notna(), "")
            config[col] = st.column_config.Column(etiqueta, width=ANCHOS.get(col))
    st.dataframe(vista, hide_index=True, width="stretch", column_config=config, **({"height": alto} if alto else {}))
