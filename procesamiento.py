import numpy as np
import pandas as pd

TIPO_ADICIONAL = "Op - Alta Adicional"
TIPOS_VALIDOS = [
    "Op - Alta",
    "Op - Alta Adicional",
    "Op - Traslado de domicilio",
    "Op - Cambio plan",
]

COLUMNAS_ACTIVIDAD = {"MTA", "Código Oferta", "Tipo de tarea", "Motivo de tarea", "Fecha Cierre", "Técnico Cierre", "Correo Técnico Cierre", "CT Específico"}
COLUMNAS_TECNICOS = {"Nombre Tecnico", "Correo", "Tecnico ID", "Estado inicio", "CT General"}
COLUMNAS_MATERIALES = {"codigo_tarea", "material_unificado", "material_usado_cantidad", "created_at"}
COLUMNAS_APK = {"cod_oferta", "p_apk_mundogo", "fecha_fin"}


def leer_hoja(archivo, columnas_requeridas):
    # Los nombres de pestana cambian entre exportaciones, asi que se busca la hoja por sus columnas.
    excel = pd.ExcelFile(archivo)
    for nombre_hoja in excel.sheet_names:
        encabezado = set(excel.parse(nombre_hoja, nrows=0).columns)
        if columnas_requeridas.issubset(encabezado):
            return excel.parse(nombre_hoja)
    raise ValueError(
        f"No encontré ninguna hoja con las columnas {sorted(columnas_requeridas)}. "
        f"Hojas disponibles: {excel.sheet_names}"
    )


def leer_actividad(archivo):
    actividad = leer_hoja(archivo, COLUMNAS_ACTIVIDAD)
    actividad = actividad[actividad["Tipo de tarea"].isin(TIPOS_VALIDOS)]
    actividad = actividad.dropna(subset=["MTA", "Código Oferta"]).drop_duplicates(subset="MTA").copy()
    actividad["Fecha Cierre"] = pd.to_datetime(actividad["Fecha Cierre"])
    return actividad


def leer_tecnicos(archivo):
    return leer_hoja(archivo, COLUMNAS_TECNICOS)


def cierres_por_tecnico(actividad, tecnicos):
    # Se cruza por correo porque el nombre puede venir escrito distinto en cada hoja.
    cierres = actividad["Correo Técnico Cierre"].str.lower().value_counts()
    lista = tecnicos[["Nombre Tecnico", "CT General"]].copy()
    lista["Tareas"] = tecnicos["Correo"].str.lower().map(cierres).fillna(0).astype(int)
    return lista.sort_values("Tareas", kind="stable").reset_index(drop=True)


def buscar_hoja(archivo, columnas_requeridas):
    try:
        return leer_hoja(archivo, columnas_requeridas)
    except ValueError:
        return None


def leer_export_instalaciones(archivos):
    """Acepta el Excel combinado de antes o los archivos de Materiales y de APK por separado, uno o varios."""
    materiales = [hoja for hoja in (buscar_hoja(a, COLUMNAS_MATERIALES) for a in archivos) if hoja is not None]
    apks = [hoja for hoja in (buscar_hoja(a, COLUMNAS_APK) for a in archivos) if hoja is not None]
    if not materiales and not apks:
        raise ValueError("Ningún archivo tiene la hoja de materiales ni la de APK.")

    export = {"materiales": None, "materiales_desde": None, "materiales_hasta": None,
              "ofertas_con_apk": None, "apk_desde": None, "apk_hasta": None}

    if materiales:
        materiales = pd.concat(materiales)
        nombre = materiales["material_unificado"].astype(str).str.upper()
        cantidad = materiales["material_usado_cantidad"]
        # material_usado_cantidad es +1 al instalar y -1 al retirar, por eso se suma.
        deco = cantidad[nombre.str.contains("DECODIFICADOR")].groupby(materiales["codigo_tarea"]).sum()
        router = cantidad[nombre.str.contains("ROUTER")].groupby(materiales["codigo_tarea"]).sum()
        por_mta = pd.concat([deco.rename("deco_neto"), router.rename("router_neto")], axis=1)
        fechas = pd.to_datetime(materiales["created_at"]).dt.normalize()
        export.update(materiales=por_mta.reindex(columns=["deco_neto", "router_neto"]).fillna(0),
                      materiales_desde=fechas.min(), materiales_hasta=fechas.max())

    if apks:
        apk = pd.concat(apks)
        fechas = pd.to_datetime(apk["fecha_fin"]).dt.normalize()
        export.update(ofertas_con_apk=set(apk.loc[apk["p_apk_mundogo"] > 0, "cod_oferta"].dropna()),
                      apk_desde=fechas.min(), apk_hasta=fechas.max())

    return export


def construir_reporte(actividad, export=None):
    """Una fila por oferta (OF): la MTA base y, si existe, la MTA adicional."""
    tareas = actividad.copy()
    tareas["es_adicional"] = tareas["Tipo de tarea"] == TIPO_ADICIONAL
    tareas["dia"] = tareas["Fecha Cierre"].dt.normalize()
    tareas["deco_adi"] = np.nan
    tareas["router"] = np.nan

    if export is not None and export["materiales"] is not None:
        # Fuera del periodo que cubre el archivo de materiales no hay dato, y eso no es lo mismo que cero.
        cubierta = ((tareas["dia"] >= export["materiales_desde"]) & (tareas["dia"] <= export["materiales_hasta"])).to_numpy()
        materiales = export["materiales"].reindex(tareas["MTA"].to_numpy()).fillna(0)
        deco_neto = materiales["deco_neto"].to_numpy()
        router_neto = materiales["router_neto"].to_numpy()
        # En una tarea base el primer decodificador viene incluido; en una Alta Adicional todo es adicional.
        deco_adi = np.where(tareas["es_adicional"].to_numpy(), deco_neto, deco_neto - 1)
        tareas["deco_adi"] = np.where(cubierta, np.clip(deco_adi, 0, None), np.nan)
        tareas["router"] = np.where(cubierta, np.clip(router_neto, 0, None), np.nan)

    # shortcut: sin archivo de equipos, el deco adicional sale del motivo (1 por Alta Adicional "Deco Mundo Go");
    # no ve cantidades mayores a 1. Pasar a cantidades reales cuando haya archivo de equipos del mismo período.
    deco_por_motivo = tareas["es_adicional"] & (tareas["Motivo de tarea"].astype(str).str.strip().str.lower() == "deco mundo go")
    tareas["deco_adi"] = tareas["deco_adi"].fillna(deco_por_motivo.astype(float))

    filas = []
    for oferta, grupo in tareas.groupby("Código Oferta", sort=False):
        grupo = grupo.sort_values(["es_adicional", "Fecha Cierre"])
        base = grupo.iloc[0] if not grupo.iloc[0]["es_adicional"] else None
        resto = grupo.iloc[1:] if base is not None else grupo
        referencia = base if base is not None else grupo.iloc[0]

        apk = np.nan
        if export is not None and export["ofertas_con_apk"] is not None and export["apk_desde"] <= referencia["dia"] <= export["apk_hasta"]:
            apk = 1 if oferta in export["ofertas_con_apk"] else 0

        filas.append({
            "Fecha cierre": referencia["Fecha Cierre"].date(),
            "Cod OF": oferta,
            "MTA": base["MTA"] if base is not None else None,
            "MTA adi": " / ".join(resto["MTA"]) if len(resto) else None,
            "Tipo tarea": referencia["Tipo de tarea"],
            "Motivo": referencia["Motivo de tarea"],
            "Técnico": base["Técnico Cierre"] if base is not None else None,
            "Técnico adi": " / ".join(dict.fromkeys(resto["Técnico Cierre"])) if len(resto) else None,
            "CT específico": referencia["CT Específico"],
            "Deco adi": grupo["deco_adi"].sum(min_count=1),
            "Router": grupo["router"].sum(min_count=1),
            "APK": apk,
        })

    reporte = pd.DataFrame(filas).sort_values(["Fecha cierre", "Cod OF"]).reset_index(drop=True)
    columnas_enteras = ["Deco adi", "Router", "APK"]
    reporte[columnas_enteras] = reporte[columnas_enteras].astype("Int64")
    return reporte
