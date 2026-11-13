from io import BytesIO

import streamlit as st

from procesamiento import (
    cierres_por_tecnico,
    construir_reporte,
    leer_actividad,
    leer_export_instalaciones,
    leer_tecnicos,
)

st.set_page_config(
    page_title="Operaciones Telconet",
    page_icon="📡",
    layout="wide",
)

MIME_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ACENTO = "#00A9B7"


def a_excel(tabla):
    buffer = BytesIO()
    tabla.to_excel(buffer, index=False)
    return buffer.getvalue()


def miles(numero):
    return f"{numero:,}".replace(",", ".")


# Al cambiar de página Streamlit borra lo que tenía el cuadro de carga, así que el archivo se guarda aparte en la sesión.
def guardar_subida(clave):
    archivo = st.session_state[f"subida_{clave}"]
    st.session_state[clave] = {"nombre": archivo.name, "datos": archivo.getvalue()} if archivo else None


def cuadro_de_carga(columna, clave, etiqueta):
    with columna.container(border=True):
        st.file_uploader(etiqueta, type=["xlsx"], key=f"subida_{clave}", on_change=guardar_subida, args=(clave,))
        guardado = st.session_state.get(clave)
        if guardado and st.session_state.get(f"subida_{clave}") is None:
            st.caption(f"En uso: {guardado['nombre']}. Para cambiarlo, subí otro.")


actividad = tecnicos = export = None
avisos = []
if st.session_state.get("actividad"):
    contenido = st.session_state["actividad"]["datos"]
    try:
        actividad = leer_actividad(BytesIO(contenido))
    except Exception:
        avisos.append((st.error,
            "No pude leer el archivo de actividad. Revisá que tenga el mismo formato de siempre "
            "(con la hoja de actividad del mes) y volvé a subirlo."))
    try:
        tecnicos = leer_tecnicos(BytesIO(contenido))
    except Exception:
        tecnicos = None

if st.session_state.get("export"):
    try:
        export = leer_export_instalaciones(BytesIO(st.session_state["export"]["datos"]))
    except Exception:
        avisos.append((st.warning,
            "No pude leer el archivo de instalaciones. Revisá que sea el de equipos y APK "
            "(con las hojas de materiales y APK). Mientras tanto, Deco adi, Router y APK quedan vacíos."))


def pedir_actividad():
    st.info("Subí el archivo de actividad para empezar.")


def tarjeta(columna, titulo, valor, detalle):
    with columna.container(border=True):
        st.metric(titulo, valor)
        st.caption(detalle)


def mostrar_resumen():
    tipos = actividad["Tipo de tarea"].value_counts()
    total = len(actividad)
    dias = actividad["Fecha Cierre"].dt.normalize().nunique()
    altas = int(tipos.get("Op - Alta", 0))
    adicionales = int(tipos.get("Op - Alta Adicional", 0))
    traslados = int(tipos.get("Op - Traslado de domicilio", 0))
    cambios = int(tipos.get("Op - Cambio plan", 0))
    motivos_adicionales = actividad.loc[
        actividad["Tipo de tarea"] == "Op - Alta Adicional", "Motivo de tarea"
    ].value_counts()

    columnas = st.columns(5)
    tarjeta(columnas[0], "Tareas cerradas", miles(total), f"en {dias} días · {round(total / dias)} por día")
    tarjeta(columnas[1], "Altas", miles(altas), f"{round(altas / total * 100)} % del total")
    tarjeta(
        columnas[2],
        "Altas adicionales",
        miles(adicionales),
        " · ".join(f"{cantidad} {motivo}" for motivo, cantidad in motivos_adicionales.items()) or "ninguna",
    )
    tarjeta(columnas[3], "Traslados", miles(traslados), f"y {cambios} cambios de plan")
    if tecnicos is None:
        tarjeta(columnas[4], "Técnicos activos", "—", "el archivo no trae el listado")
    else:
        sin_inicio = int(tecnicos["Estado inicio"].astype(str).str.lower().str.startswith("sin").sum())
        detalle = "todos iniciaron labores" if sin_inicio == 0 else f"{sin_inicio} sin inicio de labores"
        tarjeta(columnas[4], "Técnicos activos", miles(len(tecnicos)), detalle)

    with st.container(border=True):
        st.subheader("Tareas cerradas por día")
        st.caption("Altas, altas adicionales, traslados y cambios de plan. No incluye SSTT.")
        por_dia = actividad.groupby(actividad["Fecha Cierre"].dt.date).size().rename("Tareas")
        por_dia.index.name = "Día"
        st.bar_chart(por_dia, color=ACENTO)

    izquierda, derecha = st.columns(2)
    with izquierda.container(border=True):
        st.subheader("Técnicos sin inicio de labores")
        if tecnicos is None:
            st.caption("El archivo no trae el listado de técnicos.")
        else:
            sin_inicio = tecnicos["Estado inicio"].astype(str).str.lower().str.startswith("sin")
            if sin_inicio.any():
                st.dataframe(tecnicos.loc[sin_inicio, ["Nombre Tecnico", "CT General"]], hide_index=True, width="stretch")
            else:
                st.caption("Todos los técnicos iniciaron labores.")
    with derecha.container(border=True):
        st.subheader("Técnicos con menos cierres")
        if tecnicos is None:
            st.caption("El archivo no trae el listado de técnicos.")
        else:
            st.caption("Tareas cerradas en el período del archivo.")
            st.dataframe(cierres_por_tecnico(actividad, tecnicos).head(5), hide_index=True, width="stretch")


def pagina_reportes():
    columna_actividad, columna_export = st.columns(2)
    cuadro_de_carga(columna_actividad, "actividad", "Archivo de actividad")
    cuadro_de_carga(columna_export, "export", "Archivo de instalaciones (equipos y APK) — opcional")
    for mostrar, mensaje in avisos:
        mostrar(mensaje)

    if actividad is None:
        pedir_actividad()
        return
    if actividad.empty:
        st.warning("El archivo de actividad no tiene altas, altas adicionales, traslados ni cambios de plan.")
        return

    reporte = construir_reporte(actividad, export)

    def total(columna):
        return int(reporte[columna].sum()) if reporte[columna].notna().any() else "—"

    columnas_extra = ["Deco adi", "Router", "APK"]
    tab_resumen, tab_reporte, tab_dinamica = st.tabs(["Resumen", "Detalle por orden", "Tabla dinámica"])

    with tab_resumen:
        mostrar_resumen()

    with tab_reporte:
        st.success(f"Reporte generado: {len(reporte)} órdenes (OF) a partir de {len(actividad)} tareas.")

        if not st.session_state.get("export"):
            st.info(
                "Deco adi sale del motivo de la tarea (cada Alta Adicional \"Deco Mundo Go\" cuenta 1). "
                "Router y APK quedan vacíos: no vienen en el archivo de actividad."
            )
        elif export is not None:
            sin_dato = int(reporte["APK"].isna().sum())
            if sin_dato:
                st.warning(
                    f"{sin_dato} órdenes quedaron sin Router ni APK (su Deco adi sale del motivo) porque su fecha de cierre está fuera del "
                    f"período que cubre el archivo de instalaciones ({export['desde'].date()} al {export['hasta'].date()})."
                )

        tipos_presentes = sum(1 for columna in columnas_extra if reporte[columna].fillna(0).gt(0).any())
        hay_datos_extra = any(reporte[columna].notna().any() for columna in columnas_extra)

        metrica1, metrica2, metrica3, metrica4, metrica5 = st.columns(5)
        metrica1.metric("Órdenes (OF) procesadas", miles(len(reporte)), border=True)
        metrica2.metric("Deco adi", total("Deco adi"), border=True)
        metrica3.metric("Router", total("Router"), border=True)
        metrica4.metric("APK", total("APK"), border=True)
        metrica5.metric("Tipos de producto distintos", tipos_presentes if hay_datos_extra else "—", border=True)

        with st.container(border=True):
            st.subheader("Detalle por orden")
            st.dataframe(reporte, width="stretch")

        st.download_button(
            label="Descargar reporte en Excel",
            data=a_excel(reporte),
            file_name="reporte_instalaciones.xlsx",
            mime=MIME_EXCEL,
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
                label="Descargar tabla dinámica",
                data=a_excel(resumen_dinamico),
                file_name="tabla_dinamica.xlsx",
                mime=MIME_EXCEL,
            )

        st.write("")

        with st.container(border=True):
            st.subheader(f"Órdenes por {agrupar_por}")
            st.bar_chart(resumen_dinamico.set_index(agrupar_por)["OF"], color=ACENTO)


def pagina_tecnicos():
    if tecnicos is None:
        st.info("Subí el archivo de actividad en Reportes: trae el listado de técnicos.")
        return

    sin_inicio = tecnicos["Estado inicio"].astype(str).str.lower().str.startswith("sin")

    metrica1, metrica2, metrica3, metrica4 = st.columns(4)
    metrica1.metric("Técnicos activos", len(tecnicos), border=True)
    metrica2.metric("Con inicio de labores", int((~sin_inicio).sum()), border=True)
    metrica3.metric("Sin inicio de labores", int(sin_inicio.sum()), border=True)
    metrica4.metric("Centros técnicos", tecnicos["CT General"].nunique(), border=True)

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
        coincide = coincide | vista["Correo"].astype(str).str.lower().str.contains(texto, regex=False)
        vista = vista[coincide]

    with st.container(border=True):
        st.subheader(f"Listado de técnicos ({len(vista)})")
        st.dataframe(vista, width="stretch")
        st.download_button(
            label="Descargar listado de técnicos",
            data=a_excel(vista),
            file_name="tecnicos.xlsx",
            mime=MIME_EXCEL,
        )


pagina = st.navigation([
    st.Page(pagina_reportes, title="Reportes", icon=":material/table_chart:", default=True),
    st.Page(pagina_tecnicos, title="Técnicos", icon=":material/group:"),
])
st.title("Operaciones Telconet")
pagina.run()
