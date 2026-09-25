from io import BytesIO

import pandas as pd
import streamlit as st

from procesamiento import (
    construir_reporte,
    leer_actividad,
    leer_export_instalaciones,
    leer_tecnicos,
)

st.set_page_config(
    page_title="Reporte de Instalaciones",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Reporte de instalaciones")


def a_excel(tabla):
    buffer = BytesIO()
    tabla.to_excel(buffer, index=False)
    return buffer.getvalue()


def seccion_reportes():
    st.caption("Actividad del mes por oferta, con equipos adicionales y APK — sin cruzar planillas a mano.")

    columna_actividad, columna_export = st.columns(2)
    with columna_actividad:
        with st.container(border=True):
            archivo_actividad = st.file_uploader("Archivo de actividad", type=["xlsx"], key="actividad")
    with columna_export:
        with st.container(border=True):
            archivo_export = st.file_uploader(
                "Archivo de instalaciones (equipos y APK) — opcional", type=["xlsx"], key="export"
            )

    if archivo_actividad is None:
        st.info("Subí el archivo de actividad para generar el reporte.")
        return

    try:
        actividad = leer_actividad(BytesIO(archivo_actividad.getvalue()))
    except Exception:
        st.error(
            "⚠️ No pude leer el archivo de actividad. Revisá que tenga el mismo formato de siempre "
            "(con la hoja de actividad del mes) y volvé a subirlo."
        )
        return

    export = None
    if archivo_export is not None:
        try:
            export = leer_export_instalaciones(BytesIO(archivo_export.getvalue()))
        except Exception:
            st.warning(
                "⚠️ No pude leer el archivo de instalaciones (equipos y APK). Revisá que tenga el mismo formato "
                "de siempre. Mientras tanto el reporte se muestra sin Deco adi, Router y APK."
            )

    reporte = construir_reporte(actividad, export)

    st.success(f"Reporte generado: {len(reporte)} órdenes (OF) a partir de {len(actividad)} tareas.")

    if archivo_export is None:
        st.info("Sin el archivo de instalaciones, las columnas Deco adi, Router y APK quedan vacías.")
    elif export is not None:
        sin_dato = int(reporte["APK"].isna().sum())
        if sin_dato:
            st.warning(
                f"{sin_dato} órdenes quedaron sin datos de equipos y APK porque su fecha de cierre está fuera del "
                f"período que cubre el archivo de instalaciones ({export['desde'].date()} al {export['hasta'].date()})."
            )

    def total(columna):
        return int(reporte[columna].sum()) if reporte[columna].notna().any() else "—"

    columnas_extra = ["Deco adi", "Router", "APK"]
    tipos_presentes = sum(1 for columna in columnas_extra if reporte[columna].fillna(0).gt(0).any())
    hay_datos_extra = any(reporte[columna].notna().any() for columna in columnas_extra)

    metrica1, metrica2, metrica3, metrica4, metrica5 = st.columns(5)
    metrica1.metric("Órdenes (OF) procesadas", len(reporte))
    metrica2.metric("Deco adi", total("Deco adi"))
    metrica3.metric("Router", total("Router"))
    metrica4.metric("APK", total("APK"))
    metrica5.metric("Tipos de producto distintos", tipos_presentes if hay_datos_extra else "—")

    tab_reporte, tab_dinamica = st.tabs(["📋 Reporte", "📊 Tabla dinámica"])

    with tab_reporte:
        with st.container(border=True):
            st.subheader("Detalle por orden")
            st.dataframe(reporte, width="stretch")

        st.download_button(
            label="⬇️ Descargar reporte en Excel",
            data=a_excel(reporte),
            file_name="reporte_instalaciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    with tab_dinamica:
        columnas_agrupables = ["CT específico", "Tipo tarea", "Motivo", "Técnico", "Fecha cierre"]

        with st.container(border=True):
            columna_selector, _ = st.columns([1, 2])
            with columna_selector:
                agrupar_por = st.selectbox("Agrupar por", columnas_agrupables)

        st.write("")

        base = reporte.copy()
        base[agrupar_por] = base[agrupar_por].fillna("(sin dato)")

        agregaciones = {"OF": ("Cod OF", "count")}
        for columna in columnas_extra:
            if reporte[columna].notna().any():
                agregaciones[columna] = (columna, "sum")

        resumen_dinamico = base.groupby(agrupar_por).agg(**agregaciones).reset_index()
        if agrupar_por == "Fecha cierre":
            resumen_dinamico = resumen_dinamico.sort_values(agrupar_por)
        else:
            resumen_dinamico = resumen_dinamico.sort_values("OF", ascending=False)

        st.write("")

        with st.container(border=True):
            st.subheader(f"Resumen por {agrupar_por}")
            st.dataframe(resumen_dinamico, width="stretch")
            st.download_button(
                label="⬇️ Descargar tabla dinámica",
                data=a_excel(resumen_dinamico),
                file_name="tabla_dinamica.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.write("")

        with st.container(border=True):
            st.subheader(f"Órdenes por {agrupar_por}")
            st.bar_chart(resumen_dinamico.set_index(agrupar_por)["OF"])


def seccion_tecnicos():
    st.caption("Listado de todos los técnicos con su centro técnico y su estado de inicio de labores.")

    with st.container(border=True):
        archivo_tecnicos = st.file_uploader("Archivo de técnicos", type=["xlsx"], key="tecnicos")

    if archivo_tecnicos is None:
        st.info("Subí el archivo de técnicos para ver el listado.")
        return

    try:
        tecnicos = leer_tecnicos(BytesIO(archivo_tecnicos.getvalue()))
    except Exception:
        st.error(
            "⚠️ No pude leer el archivo de técnicos. Revisá que tenga el mismo formato de siempre "
            "(con la hoja del listado de técnicos) y volvé a subirlo."
        )
        return

    sin_inicio = tecnicos["Estado inicio"].astype(str).str.lower().str.startswith("sin")

    metrica1, metrica2, metrica3, metrica4 = st.columns(4)
    metrica1.metric("Técnicos activos", len(tecnicos))
    metrica2.metric("Con inicio de labores", int((~sin_inicio).sum()))
    metrica3.metric("Sin inicio de labores", int(sin_inicio.sum()))
    metrica4.metric("Centros técnicos", tecnicos["CT General"].nunique())

    with st.container(border=True):
        busqueda = st.text_input("Buscar técnico (nombre o correo)")
        filtro1, filtro2 = st.columns(2)
        centros = filtro1.multiselect("CT General", sorted(tecnicos["CT General"].dropna().unique()))
        estados = filtro2.multiselect("Estado inicio", sorted(tecnicos["Estado inicio"].dropna().unique()))

    vista = tecnicos
    if centros:
        vista = vista[vista["CT General"].isin(centros)]
    if estados:
        vista = vista[vista["Estado inicio"].isin(estados)]
    if busqueda:
        texto = busqueda.lower()
        coincide = vista["Nombre Tecnico"].astype(str).str.lower().str.contains(texto, regex=False)
        if "Correo" in vista.columns:
            coincide = coincide | vista["Correo"].astype(str).str.lower().str.contains(texto, regex=False)
        vista = vista[coincide]

    with st.container(border=True):
        st.subheader(f"Listado de técnicos ({len(vista)})")
        st.dataframe(vista, width="stretch")
        st.download_button(
            label="⬇️ Descargar listado de técnicos",
            data=a_excel(vista),
            file_name="tecnicos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


pestana_reportes, pestana_tecnicos = st.tabs(["📋 Reportes", "👷 Técnicos"])

with pestana_reportes:
    seccion_reportes()

with pestana_tecnicos:
    seccion_tecnicos()
