import re
from io import BytesIO

import pandas as pd
import streamlit as st

import historial
from componentes import (
    MAXIMO_BARRAS, encabezado, estilos, grafico_por_dia, grafico_ranking, linea_ok, miles, periodo_en_palabras,
    seccion, tabla, tira,
)
from procesamiento import (
    cierres_por_tecnico,
    construir_reporte,
    leer_actividad,
    leer_export_instalaciones,
    leer_tecnicos,
    sin_cruce,
)

st.set_page_config(
    page_title="Operaciones Telconet",
    page_icon="📡",
    layout="wide",
)

MIME_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPOS = {"actividad": "Actividad", "export": "Instalaciones"}


def login_configurado():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def control_de_acceso():
    """Devuelve el rol del usuario: "administrador" o "lector"."""
    if not login_configurado():
        return "administrador"  # sin inicio de sesión configurado (uso local) la app queda abierta como antes
    if not st.user.is_logged_in:
        st.title("Operaciones Telconet")
        st.write("Ingresá con tu correo para ver los reportes.")
        st.button("Iniciar sesión", on_click=st.login, type="primary")
        st.stop()
    acceso = st.secrets.get("acceso", {})
    correo = (st.user.email or "").lower()
    for rol, lista in (("administrador", "administradores"), ("lector", "lectores")):
        if correo in [c.lower() for c in acceso.get(lista, [])]:
            return rol
    st.title("Operaciones Telconet")
    st.error(f"{correo} no tiene acceso a esta app. Pedile al administrador que te agregue.")
    st.button("Cerrar sesión", on_click=st.logout)
    st.stop()


rol = control_de_acceso()
es_admin = rol == "administrador"

url_base = historial.url_configurada()
if url_base and not url_base.startswith("sqlite") and not login_configurado():
    base = None
    st.warning("La base de datos en la nube queda apagada hasta configurar el inicio de sesión, para no exponer los datos.")
else:
    try:
        base = historial.conectar()
    except Exception as error:
        base = None
        st.warning("No pude conectarme a la base de datos: el historial no está disponible por ahora.")
        if es_admin:
            # La contraseña de la base viene dentro de la dirección (usuario:clave@servidor): se tapa antes de mostrarla.
            detalle = re.sub(r"://[^\s@]*@", "://***@", f"{type(error).__name__}: {error}")
            with st.expander("Detalle técnico (solo administradores)"):
                st.code(detalle[:600])


def a_excel(datos):
    buffer = BytesIO()
    datos.to_excel(buffer, index=False)
    return buffer.getvalue()


# Al cambiar de página Streamlit borra lo que tenía el cuadro de carga, así que el archivo se guarda aparte en la sesión.
def periodo(clave, datos):
    """Fechas que cubre el archivo, o None si no es del tipo esperado."""
    try:
        if clave == "actividad":
            fechas = leer_actividad(BytesIO(datos))["Fecha Cierre"]
            return fechas.min().date(), fechas.max().date()
        partes = leer_export_instalaciones([BytesIO(datos)])
        desdes = [d for d in (partes["materiales_desde"], partes["apk_desde"]) if pd.notna(d)]
        hastas = [h for h in (partes["materiales_hasta"], partes["apk_hasta"]) if pd.notna(h)]
        return min(desdes).date(), max(hastas).date()
    except Exception:
        return None


def guardar_subida(clave):
    subida = st.session_state[f"subida_{clave}"]
    archivos = [subida] if clave == "actividad" and subida else (subida or [])
    st.session_state[clave] = [{"nombre": a.name, "datos": a.getvalue()} for a in archivos] or None
    if base is None:
        return
    for archivo in archivos:
        # Solo se guarda lo que se pudo leer, para no llenar el historial de archivos equivocados.
        fechas = periodo(clave, archivo.getvalue())
        if fechas is None:
            st.toast(f"{archivo.name}: no es del tipo esperado, no lo guardé en el historial.")
            continue
        try:
            nuevo = historial.guardar(base, archivo.name, clave, archivo.getvalue(), *fechas)
            st.toast(f"{archivo.name}: " + ("guardado en el historial." if nuevo else "ya estaba en el historial."))
        except Exception:
            st.toast(f"{archivo.name}: no pude guardarlo en el historial; el reporte funciona igual.")


def cuadro_de_carga(columna, clave, etiqueta, varios=False):
    with columna.container(border=True):
        st.file_uploader(etiqueta, type=["xlsx"], accept_multiple_files=varios, key=f"subida_{clave}",
                         on_change=guardar_subida, args=(clave,))
        guardados = st.session_state.get(clave)
        if guardados and not st.session_state.get(f"subida_{clave}"):
            st.caption(f"En uso: {', '.join(a['nombre'] for a in guardados)}. Para cambiarlo, subí otro.")


def cargar_del_historial(ids):
    cargados = {}
    for id_archivo in ids:
        nombre, tipo, datos = historial.leer(base, int(id_archivo))
        cargados.setdefault(tipo, []).append({"nombre": nombre, "datos": datos})
    if "actividad" in cargados:
        cargados["actividad"] = cargados["actividad"][:1]
    st.session_state.update(cargados)


# Al entrar, cada persona ve los últimos archivos guardados; después puede elegir otros en Historial.
if base is not None and not st.session_state.get("carga_inicial_hecha"):
    st.session_state["carga_inicial_hecha"] = True
    try:
        cargar_del_historial(historial.ultimos(base))
    except Exception:
        # Un corte de la base no tiene que impedir entrar: se avisa y se puede subir el archivo a mano.
        st.warning("No pude traer los últimos archivos del historial. Recargá la página en unos segundos.")

actividad = tecnicos = export = None
avisos = []
if st.session_state.get("actividad"):
    contenido = st.session_state["actividad"][0]["datos"]
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
        export = leer_export_instalaciones([BytesIO(a["datos"]) for a in st.session_state["export"]])
    except Exception:
        avisos.append((st.warning,
            "No pude leer los archivos de equipos y APK. Revisá que sean el de Materiales Utilizados y/o el de APK "
            "(o el Excel que trae los dos). Mientras tanto, Router y APK quedan vacíos."))


def pedir_actividad():
    if es_admin:
        st.info("Subí el archivo de actividad para ver el reporte.")
    else:
        st.info("Todavía no hay archivos cargados. Cuando el administrador suba uno, lo vas a ver acá.")


def plural(cantidad, singular, varios):
    return f"{miles(cantidad)} {singular if cantidad == 1 else varios}"


def sin_inicio_de_labores():
    return tecnicos["Estado inicio"].astype(str).str.lower().str.startswith("sin")


def nombres_en_uso(clave):
    return [a["nombre"] for a in (st.session_state.get(clave) or [])]


def lista_en_palabras(nombres):
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def encabezado_reportes():
    fechas = actividad["Fecha Cierre"]
    desde, hasta = fechas.min(), fechas.max()
    inicio = "El" if desde.date() == hasta.date() else "Del"
    bajada = (f"Altas, altas adicionales, traslados y cambios de plan, sin SSTT. "
              f"Archivo de actividad: {lista_en_palabras(nombres_en_uso('actividad'))}.")
    if nombres_en_uso("export"):
        bajada += f" Equipos: {lista_en_palabras(nombres_en_uso('export'))}."
    if not es_admin:
        bajada += " Para ver otros archivos, entrá a Historial."
    encabezado(f"{inicio} {periodo_en_palabras(desde, hasta)} se cerraron {plural(len(actividad), 'tarea', 'tareas')}",
               bajada)


def tira_operativa():
    """Las cifras del período, siempre visibles arriba de las pestañas de Reportes."""
    tipos = actividad["Tipo de tarea"].value_counts()
    total = len(actividad)
    dias = actividad["Fecha Cierre"].dt.normalize().nunique()
    altas = int(tipos.get("Op - Alta", 0))
    adicionales = int(tipos.get("Op - Alta Adicional", 0))
    cambios = int(tipos.get("Op - Cambio plan", 0))
    motivos = actividad.loc[actividad["Tipo de tarea"] == "Op - Alta Adicional", "Motivo de tarea"].value_counts()
    detalle_adicionales = lista_en_palabras([f"{cantidad} {motivo}" for motivo, cantidad in motivos.items()]) if len(motivos) else "ninguna"
    if tecnicos is None:
        cifra_tecnicos = ("Técnicos activos", None, "el archivo no trae el listado")
    else:
        faltan = int(sin_inicio_de_labores().sum())
        cifra_tecnicos = ("Técnicos activos", miles(len(tecnicos)),
                          "todos iniciaron labores" if faltan == 0 else f"{faltan} sin inicio de labores")
    tira([
        ("Altas", miles(altas), f"{round(altas / total * 100)} % de las tareas"),
        ("Altas adicionales", miles(adicionales), detalle_adicionales),
        ("Traslados", miles(int(tipos.get("Op - Traslado de domicilio", 0))), f"y {plural(cambios, 'cambio', 'cambios')} de plan"),
        ("Promedio diario", miles(round(total / dias)), f"en {plural(dias, 'día', 'días')} con cierres"),
        cifra_tecnicos,
    ])


def mostrar_resumen():
    por_dia = actividad.groupby(actividad["Fecha Cierre"].dt.normalize()).size()
    seccion("Tareas cerradas por día",
            f"La línea punteada es el promedio: {round(por_dia.mean())} por día. Pasá el mouse por una columna para ver la fecha.")
    st.altair_chart(grafico_por_dia(por_dia, "Tareas"), theme="streamlit", width="stretch")

    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        seccion("Técnicos sin inicio de labores")
        if tecnicos is None:
            st.caption("El archivo no trae el listado de técnicos.")
        elif sin_inicio_de_labores().any():
            tabla(tecnicos.loc[sin_inicio_de_labores(), ["Nombre Tecnico", "CT General"]])
        else:
            linea_ok("Todos los técnicos iniciaron labores.")
    with derecha:
        seccion("Técnicos con menos cierres", "Los 5 con menos tareas cerradas en el período.")
        if tecnicos is None:
            st.caption("El archivo no trae el listado de técnicos.")
        else:
            tabla(cierres_por_tecnico(actividad, tecnicos).head(5))


def mostrar_cuadre(export):
    faltan = sin_cruce(actividad, export)
    apk_total = export["apk_por_oferta"]
    if apk_total is not None:
        falta = faltan["apk"]
        suma = int(apk_total.sum())
        if falta.empty:
            linea_ok(f"APK: las {len(apk_total)} ofertas del archivo cruzan con la actividad ({miles(suma)} de {miles(suma)}).")
        else:
            st.warning(
                f"APK: {len(falta)} de {len(apk_total)} ofertas del archivo de APK no aparecen en la actividad, "
                f"así que el reporte suma {miles(int(suma - falta.sum()))} APK de {miles(suma)}."
            )
            with st.expander("Ver ofertas de APK que no cruzan"):
                tabla(falta.rename("APK").rename_axis("Cod OF").reset_index())
    materiales = export["materiales"]
    if materiales is not None:
        falta = faltan["materiales"]
        routers = int(materiales.clip(lower=0).sum())
        if falta.empty:
            linea_ok(f"Routers: las {len(materiales)} tareas con routers cruzan con la actividad ({routers} de {routers}).")
        else:
            st.warning(
                f"Routers: {len(falta)} de {len(materiales)} tareas con routers no aparecen en la actividad, "
                f"así que el reporte suma {routers - int(falta.clip(lower=0).sum())} routers de {routers}."
            )
            with st.expander("Ver tareas con routers que no cruzan"):
                tabla(falta.astype(int).rename("Router").rename_axis("MTA").reset_index())


# Opción que ve el usuario -> columna del reporte.
AGRUPACIONES = {
    "Centro técnico": "CT específico",
    "Tipo de tarea": "Tipo tarea",
    "Motivo": "Motivo",
    "Técnico": "Técnico",
    "Fecha de cierre": "Fecha cierre",
}


def mostrar_detalle(reporte):
    def total(columna, fuente):
        if reporte[columna].notna().any():
            return miles(int(reporte[columna].sum())), fuente
        return None, "sin archivo"

    tira([
        ("Órdenes (OF)", miles(len(reporte)), f"a partir de {miles(len(actividad))} tareas"),
        ("Decos adicionales", *total("Deco adi", "según el motivo del alta adicional")),
        ("Routers", *total("Router", "del archivo de Materiales")),
        ("APK", *total("APK", "del archivo de APK")),
    ], principal=False)

    seccion("Cuadre con los archivos fuente")
    if not st.session_state.get("export"):
        st.caption("Router y APK quedan vacíos porque no vienen en el archivo de actividad. "
                   "Subí los archivos de Materiales y APK para completarlos.")
    elif export is not None:
        for parte, columna, nombre in (("materiales", "Router", "Materiales"), ("apk", "APK", "APK")):
            desde, hasta = export[f"{parte}_desde"], export[f"{parte}_hasta"]
            if pd.isna(desde):
                st.caption(f"No hay archivo de {nombre}: la columna {columna} queda vacía.")
                continue
            fuera = int(reporte[columna].isna().sum())
            if fuera:
                st.warning(
                    f"{fuera} órdenes quedaron sin {columna} porque su fecha de cierre está fuera del período "
                    f"del archivo de {nombre} ({desde:%d-%m-%Y} al {hasta:%d-%m-%Y})."
                )
        mostrar_cuadre(export)

    seccion("Detalle por orden", f"{plural(len(reporte), 'orden', 'órdenes')}, una fila por oferta.")
    tabla(reporte, alto=460)
    st.download_button("Descargar en Excel", data=a_excel(reporte), file_name="reporte_instalaciones.xlsx",
                       mime=MIME_EXCEL, type="primary", icon=":material/download:")


def mostrar_dinamica(reporte):
    columna_selector, _ = st.columns([1, 2])
    opcion = columna_selector.selectbox("Agrupar por", list(AGRUPACIONES))
    agrupar_por, nombre = AGRUPACIONES[opcion], opcion.lower()

    datos = reporte.copy()
    datos[agrupar_por] = datos[agrupar_por].fillna("(sin dato)")
    agregaciones = {"OF": ("Cod OF", "count")}
    for columna in ("Deco adi", "Router", "APK"):
        if reporte[columna].notna().any():
            agregaciones[columna] = (columna, "sum")
    resumen = datos.groupby(agrupar_por).agg(**agregaciones).reset_index()
    por_fecha = agrupar_por == "Fecha cierre"
    resumen = resumen.sort_values(agrupar_por) if por_fecha else resumen.sort_values("OF", ascending=False)

    if por_fecha:
        seccion("Órdenes por día")
        serie = resumen.set_index(pd.to_datetime(resumen["Fecha cierre"]))["OF"]
        st.altair_chart(grafico_por_dia(serie, "Órdenes"), theme="streamlit", width="stretch")
        lado_tabla = st.container()
    else:
        lado_grafico, lado_tabla = st.columns([3, 2], gap="large")
        with lado_grafico:
            nota = f"Los {MAXIMO_BARRAS} con más órdenes; la tabla tiene los {len(resumen)}." if len(resumen) > MAXIMO_BARRAS else None
            seccion(f"Órdenes por {nombre}", nota)
            st.altair_chart(grafico_ranking(resumen, agrupar_por, "OF", "Órdenes"), theme="streamlit", width="stretch")
    with lado_tabla:
        seccion(f"Resumen por {nombre}")
        tabla(resumen, alto=min(460, 35 * len(resumen) + 40))
        st.download_button("Descargar en Excel", data=a_excel(resumen), file_name="tabla_dinamica.xlsx",
                           mime=MIME_EXCEL, icon=":material/download:")


def carga_de_archivos():
    with st.expander("Cargar o reemplazar archivos", expanded=actividad is None, icon=":material/upload_file:"):
        columna_actividad, columna_export = st.columns(2)
        cuadro_de_carga(columna_actividad, "actividad", "Archivo de actividad")
        cuadro_de_carga(columna_export, "export", "Archivos de Materiales y APK (opcional, podés subir varios)",
                        varios=True)


def pagina_reportes():
    if actividad is None or actividad.empty:
        encabezado("Reporte de instalaciones",
                   "Cruza la actividad del CRM con los archivos de Materiales y APK, y cuadra los totales contra cada archivo.")
        if es_admin:
            carga_de_archivos()
        for mostrar, mensaje in avisos:
            mostrar(mensaje)
        if actividad is None:
            pedir_actividad()
        else:
            st.warning("El archivo de actividad no tiene altas, altas adicionales, traslados ni cambios de plan.")
        return

    encabezado_reportes()
    for mostrar, mensaje in avisos:
        mostrar(mensaje)
    tira_operativa()
    if es_admin:
        carga_de_archivos()

    reporte = construir_reporte(actividad, export)
    tab_resumen, tab_detalle, tab_dinamica = st.tabs(["Resumen", "Detalle por orden", "Tabla dinámica"])
    with tab_resumen:
        mostrar_resumen()
    with tab_detalle:
        mostrar_detalle(reporte)
    with tab_dinamica:
        mostrar_dinamica(reporte)


def pagina_tecnicos():
    if tecnicos is None:
        encabezado("Técnicos")
        st.info("Subí el archivo de actividad en Reportes: trae el listado de técnicos.")
        return

    sin_inicio = sin_inicio_de_labores()
    centros_total = tecnicos["CT General"].nunique()
    encabezado(f"{plural(len(tecnicos), 'técnico activo', 'técnicos activos')} en "
               f"{plural(centros_total, 'centro técnico', 'centros técnicos')}",
               "Listado que trae el archivo de actividad.")
    cifras = [
        ("Con inicio de labores", miles(int((~sin_inicio).sum())), f"{round((~sin_inicio).mean() * 100)} % del listado"),
        ("Sin inicio de labores", miles(int(sin_inicio.sum())), "según el archivo"),
    ]
    if actividad is not None and not actividad.empty:
        cierres = cierres_por_tecnico(actividad, tecnicos)["Tareas"]
        cifras.append(("Tareas por técnico", miles(round(cierres.mean())), f"promedio del período, mínimo {cierres.min()}"))
    tira(cifras)

    busqueda, filtro1, filtro2 = st.columns([2, 1, 1])
    texto = busqueda.text_input("Buscar técnico", placeholder="Nombre o correo")
    centros = filtro1.multiselect("Centro técnico", sorted(tecnicos["CT General"].dropna().unique()), placeholder="Todos")
    estados = filtro2.multiselect("Inicio de labores", sorted(tecnicos["Estado inicio"].dropna().unique()), placeholder="Todos")

    vista = tecnicos
    if centros:
        vista = vista[vista["CT General"].isin(centros)]
    if estados:
        vista = vista[vista["Estado inicio"].isin(estados)]
    if texto:
        texto = texto.lower()
        coincide = vista["Nombre Tecnico"].astype(str).str.lower().str.contains(texto, regex=False)
        coincide = coincide | vista["Correo"].astype(str).str.lower().str.contains(texto, regex=False)
        vista = vista[coincide]

    seccion("Listado de técnicos", f"Se muestran {plural(len(vista), 'técnico', 'técnicos')}.")
    tabla(vista, alto=520)
    st.download_button("Descargar en Excel", data=a_excel(vista), file_name="tecnicos.xlsx",
                       mime=MIME_EXCEL, icon=":material/download:")


def pagina_historial():
    if base is None:
        encabezado("Historial de archivos")
        st.info("El historial no está configurado: falta la base de datos en la configuración privada de la app.")
        return

    guardados = historial.listar(base)
    if guardados.empty:
        encabezado("Historial de archivos")
        st.info("Todavía no hay archivos guardados. Se guardan solos al subirlos en Reportes.")
        return

    encabezado("Historial de archivos",
               f"{plural(len(guardados), 'archivo guardado', 'archivos guardados')}. "
               "Elegí cuáles usar y la app vuelve a Reportes con esos datos.")
    guardados["tipo"] = guardados["tipo"].map(TIPOS)
    guardados["subido_en"] = guardados["subido_en"].dt.strftime("%d-%m-%Y %H:%M")
    for columna in ("desde", "hasta"):
        guardados[columna] = pd.to_datetime(guardados[columna]).dt.strftime("%d-%m-%Y").fillna("—")

    seccion("Archivos guardados")
    st.dataframe(
        guardados.drop(columns="id").rename(columns={
            "nombre": "Archivo", "tipo": "Tipo", "desde": "Desde", "hasta": "Hasta", "subido_en": "Subido el",
        }),
        hide_index=True,
        width="stretch",
    )

    seccion("Usar otros archivos", "Uno de actividad y, si querés, los de Materiales y APK del mismo período.")
    etiquetas = {
        str(fila.id): f"{fila.nombre} ({fila.tipo}, {fila.desde} al {fila.hasta})" for fila in guardados.itertuples()
    }
    elegidos = st.multiselect("Archivos", list(etiquetas), format_func=etiquetas.get, placeholder="Elegí uno o más")
    if st.button("Usar estos archivos", type="primary", disabled=not elegidos):
        cargar_del_historial(elegidos)
        st.switch_page(reportes)


reportes = st.Page(pagina_reportes, title="Reportes", icon=":material/table_chart:", default=True)
pagina = st.navigation([
    reportes,
    st.Page(pagina_tecnicos, title="Técnicos", icon=":material/group:"),
    st.Page(pagina_historial, title="Historial", icon=":material/history:"),
])
if login_configurado():
    with st.sidebar:
        st.caption(f"Sesión de {st.user.email} ({rol})")
        st.button("Cerrar sesión", on_click=st.logout)
estilos()
pagina.run()
