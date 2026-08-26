import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Reporte de Instalaciones",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Reporte de instalaciones")
st.caption("Una fila por instalación, con el producto y los equipos instalados — sin cruzar planillas a mano.")

def encontrar_hoja(archivo, columnas_requeridas):
    excel = pd.ExcelFile(archivo)
    for nombre_hoja in excel.sheet_names:
        columnas = set(pd.read_excel(archivo, sheet_name=nombre_hoja, nrows=0).columns)
        if columnas_requeridas.issubset(columnas):
            return nombre_hoja
    raise ValueError(
        f"No encontré ninguna hoja con las columnas {columnas_requeridas}. "
        f"Hojas disponibles: {excel.sheet_names}"
    )


with st.container(border=True):
    archivo_subido = st.file_uploader("Excel de instalaciones", type=["xlsx"])

if archivo_subido is not None:
    hoja_instalaciones = encontrar_hoja(archivo_subido, {"cod_oferta", "producto", "region"})
    hoja_materiales = encontrar_hoja(archivo_subido, {"contrato_codigo", "material_unificado", "material_usado_cantidad"})

    instalaciones = pd.read_excel(archivo_subido, sheet_name=hoja_instalaciones)
    instalaciones = instalaciones.dropna(subset=["cod_oferta"])
    materiales = pd.read_excel(archivo_subido, sheet_name=hoja_materiales)

    resumen_materiales = materiales.groupby(["contrato_codigo", "material_unificado"])["material_usado_cantidad"].sum()
    tabla_materiales = resumen_materiales.unstack(fill_value=0).reset_index()

    reporte = instalaciones.merge(
        tabla_materiales,
        left_on="cod_oferta",
        right_on="contrato_codigo",
        how="left",
    )

    columnas_materiales = [c for c in tabla_materiales.columns if c != "contrato_codigo"]
    reporte[columnas_materiales] = reporte[columnas_materiales].fillna(0)

    columnas_finales = [
        "region", "comuna", "rut", "cod_oferta", "cod_tarea",
        "tipo_tarea", "producto", "fecha_ejecucion", "usuario",
    ] + columnas_materiales

    reporte_final = reporte[columnas_finales]

    st.success(f"Reporte generado a partir de {len(reporte_final)} instalaciones.")

    columna1, columna2, columna3 = st.columns(3)
    columna1.metric("Instalaciones procesadas", len(reporte_final))
    columna2.metric("Equipos totales instalados", int(reporte_final[columnas_materiales].sum().sum()))
    columna3.metric("Tipos de producto distintos", reporte_final["producto"].nunique())

    tab_reporte, tab_dinamica = st.tabs(["📋 Reporte", "📊 Tabla dinámica"])

    with tab_reporte:
        with st.container(border=True):
            st.subheader("Detalle por instalación")
            st.dataframe(reporte_final, use_container_width=True)

        buffer = BytesIO()
        reporte_final.to_excel(buffer, index=False)

        st.download_button(
            label="⬇️ Descargar reporte en Excel",
            data=buffer.getvalue(),
            file_name="reporte_instalaciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    with tab_dinamica:
        columnas_agrupables = ["region", "comuna", "producto", "tipo_tarea", "usuario"]
        agrupar_por = st.selectbox("Agrupar por", columnas_agrupables)

        agregaciones = {"instalaciones": ("cod_oferta", "count")}
        for columna in columnas_materiales:
            agregaciones[columna] = (columna, "sum")

        resumen_dinamico = reporte_final.groupby(agrupar_por).agg(**agregaciones).reset_index()
        resumen_dinamico = resumen_dinamico.sort_values("instalaciones", ascending=False)

        with st.container(border=True):
            st.subheader(f"Resumen por {agrupar_por}")
            st.dataframe(resumen_dinamico, use_container_width=True)
            st.bar_chart(resumen_dinamico.set_index(agrupar_por)["instalaciones"])
