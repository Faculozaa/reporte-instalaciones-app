"""Piezas visuales de la app: encabezado, tira de cifras, secciones, gráficos y formato de tablas.

Identidad (23/11): un "parte de producción". Letra Archivo (ancha para titulares y cifras), tinta azul petróleo
sacada del turquesa de Mundo, secciones separadas por líneas finas en vez de tarjetas.
"""
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

MAXIMO_BARRAS = 15
LETRA = "Archivo"

# Mismos colores que .streamlit/config.toml: el HTML propio y los gráficos no siguen el tema solos.
PALETA = {
    "light": {"tinta": "#102A33", "suave": "#56686F", "linea": "#D5DFE2", "fondo": "#FFFFFF",
              # El turquesa de la marca (#00A9B7) no llega a 3:1 sobre blanco: en claro las barras van más oscuras.
              "barras": "#0096A3", "ok": "#1E7F4F"},
    "dark": {"tinta": "#E3ECEE", "suave": "#93A7AD", "linea": "#24393F", "fondo": "#0E1D22",
             "barras": "#00A9B7", "ok": "#4CC38A"},
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def colores():
    return PALETA["dark" if st.context.theme.type == "dark" else "light"]


def miles(numero):
    return f"{numero:,}".replace(",", ".")


def periodo_en_palabras(desde, hasta):
    """'2 al 12 de noviembre', '28 de octubre al 3 de noviembre' o '30 de diciembre de 2026 al 2 de enero de 2027'."""
    if desde.year != hasta.year:
        return f"{desde.day} de {MESES[desde.month - 1]} de {desde.year} al {hasta.day} de {MESES[hasta.month - 1]} de {hasta.year}"
    if desde.month != hasta.month:
        return f"{desde.day} de {MESES[desde.month - 1]} al {hasta.day} de {MESES[hasta.month - 1]}"
    if desde.day == hasta.day:
        return f"{desde.day} de {MESES[desde.month - 1]}"
    return f"{desde.day} al {hasta.day} de {MESES[desde.month - 1]}"


def estilos():
    """Clases de las piezas propias. Se llama una vez por recarga, antes de dibujar la página."""
    c = colores()
    st.html(f"""<style>
    .tc-marca {{ font-family:{LETRA},sans-serif; font-stretch:112%; font-weight:700; font-size:0.95rem; color:{c["tinta"]}; }}
    .tc-titular {{ font-family:{LETRA},sans-serif; font-stretch:115%; font-weight:700; color:{c["tinta"]};
                   font-size:clamp(1.55rem, 2.6vw, 2.3rem); line-height:1.12; letter-spacing:-0.01em;
                   max-width:30ch; margin:0.4rem 0 0.55rem; }}
    .tc-bajada {{ color:{c["suave"]}; font-size:0.95rem; line-height:1.5; max-width:78ch; margin:0; overflow-wrap:anywhere; }}
    .tc-tira {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(165px, 1fr));
                border-top:2px solid {c["tinta"]}; border-bottom:1px solid {c["linea"]}; margin:1.1rem 0 0.4rem; }}
    .tc-tira-secundaria {{ border-top:1px solid {c["linea"]}; margin-top:0.6rem; }}
    .tc-tira-secundaria .tc-valor {{ font-size:1.55rem; }}
    .tc-cifra {{ padding:0.85rem 1.1rem 0.95rem; border-left:1px solid {c["linea"]}; }}
    .tc-cifra:first-child {{ border-left:0; padding-left:0; }}
    .tc-valor {{ font-family:{LETRA},sans-serif; font-stretch:112%; font-weight:700; font-size:1.9rem; line-height:1.1;
                 color:{c["tinta"]}; }}
    .tc-vacia .tc-valor {{ color:{c["suave"]}; font-weight:500; }}
    .tc-nombre {{ font-weight:600; font-size:0.92rem; color:{c["tinta"]}; margin-top:0.3rem; }}
    .tc-detalle {{ font-size:0.85rem; color:{c["suave"]}; line-height:1.35; margin-top:0.15rem; }}
    .tc-seccion {{ border-top:1px solid {c["linea"]}; padding-top:0.9rem; margin-top:0.5rem; }}
    .tc-seccion-titulo {{ font-family:{LETRA},sans-serif; font-weight:650; font-size:1.08rem; color:{c["tinta"]}; }}
    .tc-seccion-nota {{ font-size:0.88rem; color:{c["suave"]}; line-height:1.45; margin-top:0.2rem; max-width:80ch; }}
    .tc-ok {{ color:{c["tinta"]}; font-size:0.95rem; margin:0.2rem 0; }}
    /* Celular y tablet: la tira pasa a dos columnas parejas, con líneas entre filas en vez de entre columnas. */
    @media (max-width: 900px) {{
      .tc-tira {{ grid-template-columns:1fr 1fr; }}
      .tc-cifra, .tc-cifra:first-child {{ border-left:0; padding:0.75rem 0.75rem 0.8rem 0; }}
      .tc-cifra:nth-child(n+3) {{ border-top:1px solid {c["linea"]}; }}
      .tc-valor {{ font-size:1.6rem; }}
      .tc-tira-secundaria .tc-valor {{ font-size:1.4rem; }}
    }}
    .tc-ok b {{ color:{c["ok"]}; font-weight:700; margin-right:0.35rem; }}
    </style>""")


def encabezado(titular, bajada=None):
    """Nombre de la app, titular en frase y, si hace falta, una bajada corta."""
    st.html(
        '<div class="tc-marca">Operaciones Telconet</div>'
        f'<div class="tc-titular">{escape(titular)}</div>'
        + (f'<p class="tc-bajada">{escape(bajada)}</p>' if bajada else "")
    )


def tira(cifras, principal=True):
    """Fila de cifras separadas por líneas finas. cifras: (nombre, valor, detalle); valor None = sin dato.
    La principal (arriba de la página) lleva la línea gruesa; las de adentro de una pestaña, una fina."""
    piezas = []
    for nombre, valor, detalle in cifras:
        piezas.append(
            f'<div class="tc-cifra{" tc-vacia" if valor is None else ""}">'
            f'<div class="tc-valor">{"—" if valor is None else escape(str(valor))}</div>'
            f'<div class="tc-nombre">{escape(nombre)}</div>'
            f'<div class="tc-detalle">{escape(detalle)}</div></div>'
        )
    clase = "tc-tira" if principal else "tc-tira tc-tira-secundaria"
    st.html(f'<div class="{clase}">{"".join(piezas)}</div>')


def seccion(titulo, nota=None):
    st.html(
        f'<div class="tc-seccion"><div class="tc-seccion-titulo">{escape(titulo)}</div>'
        + (f'<div class="tc-seccion-nota">{escape(nota)}</div>' if nota else "")
        + "</div>"
    )


def linea_ok(texto):
    """Confirmación en una línea: el tilde lleva el color, el texto queda en tinta."""
    st.html(f'<div class="tc-ok"><b>✓</b>{escape(texto)}</div>')


DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
# Vega escribe los miles con coma (2,511); en Chile se usa punto (2.511).
PUNTO_DE_MILES = "replace(datum.label, /,/g, '.')"


def _estilo(grafico, descripcion):
    c = colores()
    return (
        grafico.properties(description=descripcion)  # lo leen los lectores de pantalla
        .configure(font=LETRA)
        .configure_axis(labelFontSize=12, labelColor=c["suave"], gridColor=c["linea"], domain=False, ticks=False,
                        titleFontSize=12)
        .configure_view(strokeWidth=0)
    )


def _con_signo(numero):
    return ("+" if numero >= 0 else "−") + miles(abs(numero))


def grafico_por_dia(serie, medida):
    """Columnas por día: todos los días del período (los que no tuvieron cierres en 0), pico marcado y promedio.

    Al pasar el mouse o tocar un día, ese día queda resaltado y el resto se atenúa. La zona que reacciona es la
    franja entera del día (no solo la columna), así también se puede tocar un día con muy pocas tareas.
    """
    dias = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
    datos = serie.reindex(dias, fill_value=0).rename_axis("fecha").reset_index(name=medida)
    promedio = round(serie.mean())
    datos["Día"] = datos["fecha"].dt.strftime("%d-%m")
    datos["Fecha"] = [f"{DIAS_SEMANA[f.weekday()].capitalize()} {f:%d-%m-%Y}" for f in datos["fecha"]]
    datos["Valor"] = datos[medida].map(miles)
    datos["Diferencia"] = (datos[medida] - promedio).map(_con_signo)
    datos["tope"] = max(int(datos[medida].max()), 1) * 1.1
    c = colores()

    encima = alt.selection_point(on="pointerover", clear="pointerout", fields=["Día"], empty=True)
    x = alt.X("Día:O", sort=None, title=None, axis=alt.Axis(labelAngle=0))
    eje_y = alt.Axis(tickCount=5, labelExpr=PUNTO_DE_MILES)
    y = alt.Y(f"{medida}:Q", title=None, axis=eje_y)
    ayuda = [alt.Tooltip("Fecha:N"), alt.Tooltip("Valor:N", title=medida),
             alt.Tooltip("Diferencia:N", title="Contra el promedio")]

    zona = alt.Chart(datos).mark_bar(opacity=0).encode(
        x=x, y=alt.Y("tope:Q", title=None, axis=eje_y), tooltip=ayuda
    ).add_params(encima)
    columnas = alt.Chart(datos).mark_bar(
        color=c["barras"], size=24, cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
    ).encode(x=x, y=y, opacity=alt.condition(encima, alt.value(1), alt.value(0.35)), tooltip=ayuda)
    pico = alt.Chart(datos.nlargest(1, medida)).mark_text(dy=-9, fontWeight="bold", fontSize=12, color=c["tinta"]).encode(
        x=x, y=y, text="Valor:N"
    )
    # Línea de referencia (no es grilla): punteada para que se lea como "nivel promedio", no como un dato más.
    linea = alt.Chart(pd.DataFrame({"Promedio": [promedio]})).mark_rule(
        color=c["suave"], strokeWidth=1, strokeDash=[4, 3]
    ).encode(y="Promedio:Q")
    descripcion = f"Columnas de {medida.lower()} por día; promedio {promedio} por día; máximo {datos[medida].max()}."
    return _estilo((zona + columnas + linea + pico).properties(height=300), descripcion)


def grafico_ranking(tabla, categoria, medida, titulo_medida):
    """Barras horizontales de mayor a menor (las primeras MAXIMO_BARRAS), con el valor en la punta.

    Como cada barra lleva su número, no hace falta eje ni grilla abajo: sería repetir lo mismo.
    """
    c = colores()
    datos = tabla.nlargest(MAXIMO_BARRAS, medida).copy()
    datos["Valor"] = datos[medida].map(miles)
    # 15 % de aire a la derecha para que el número de la barra más larga no se corte en pantallas angostas.
    tope = max(float(datos[medida].max()), 1) * 1.15
    datos["tope"] = tope

    encima = alt.selection_point(on="pointerover", clear="pointerout", fields=[categoria], empty=True)
    # Orden explícito (de mayor a menor): con la capa invisible de largo fijo, sort="-x" ya no ordena bien.
    orden = datos[categoria].astype(str).tolist()
    y = alt.Y(f"{categoria}:N", sort=orden, title=None, axis=alt.Axis(labelLimit=170, labelColor=c["tinta"]))
    escala = alt.Scale(domain=[0, tope], nice=False)
    x = alt.X(f"{medida}:Q", title=None, axis=None, scale=escala)
    ayuda = [alt.Tooltip(f"{categoria}:N"), alt.Tooltip("Valor:N", title=titulo_medida)]

    # La fila entera reacciona al mouse o al dedo, no solo la barra.
    zona = alt.Chart(datos).mark_bar(opacity=0, size=30).encode(
        x=alt.X("tope:Q", axis=None, scale=escala), y=y, tooltip=ayuda
    ).add_params(encima)
    barras = alt.Chart(datos).mark_bar(
        color=c["barras"], size=20, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
    ).encode(x=x, y=y, opacity=alt.condition(encima, alt.value(1), alt.value(0.35)), tooltip=ayuda)
    valores = alt.Chart(datos).mark_text(align="left", dx=6, fontSize=12, color=c["tinta"]).encode(
        x=x, y=y, text="Valor:N"
    )
    descripcion = f"Barras de {titulo_medida.lower()} por {categoria}, de mayor a menor."
    return _estilo((zona + barras + valores).properties(height=32 * len(datos) + 8), descripcion)


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
ANCHOS = {"Fecha cierre": 115, "CT General": 115, "CT Original": 135, "Tecnico ID": 70, "Cod OF": 135, "MTA": 135, "Tipo tarea": 190, "Motivo": 230, "Técnico": 250, "Técnico adi": 200, "MTA adi": 150,
          "Nombre Tecnico": 250, "Correo": 280, "Ultima fecha/hora cierre": 170}


def tabla(datos, alto=None):
    """Tabla sin números de fila, con encabezados en español, fechas dd-mm-aaaa y celdas vacías en blanco."""
    vista = datos.copy()
    config = {}
    for col in vista.columns:
        etiqueta = ETIQUETAS.get(col, col)
        if col == "Fecha cierre":
            vista[col] = pd.to_datetime(vista[col])
            config[col] = st.column_config.DateColumn(etiqueta, format="DD-MM-YYYY", width=ANCHOS.get(col))
        elif col in COLUMNAS_NUMERICAS:
            config[col] = st.column_config.NumberColumn(etiqueta, format="localized")
        else:
            if not pd.api.types.is_numeric_dtype(vista[col]):
                vista[col] = vista[col].astype(object).where(vista[col].notna(), "")
            config[col] = st.column_config.Column(etiqueta, width=ANCHOS.get(col))
    st.dataframe(vista, hide_index=True, width="stretch", column_config=config, **({"height": alto} if alto else {}))
