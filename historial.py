import hashlib
from datetime import datetime, timezone

import pandas as pd
import sqlalchemy as sa
import streamlit as st

ZONA_CHILE = "America/Santiago"

metadata = sa.MetaData()
archivos = sa.Table(
    "archivos",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("nombre", sa.String(255), nullable=False),
    sa.Column("tipo", sa.String(20), nullable=False),
    sa.Column("subido_en", sa.DateTime, nullable=False),  # en UTC
    sa.Column("huella", sa.String(64), nullable=False, unique=True),
    sa.Column("datos", sa.LargeBinary, nullable=False),
    sa.Column("desde", sa.Date),  # período que cubre el archivo
    sa.Column("hasta", sa.Date),
)


def url_configurada():
    try:
        return st.secrets["connections"]["sql"]["url"]
    except Exception:
        return None


@st.cache_resource
def conectar():
    # Sin base configurada en los secretos no hay historial: guardar en el disco de Streamlit Cloud se perdería al reiniciar.
    if url_configurada() is None:
        return None
    motor = st.connection("sql").engine
    metadata.create_all(motor)
    return motor


def guardar(motor, nombre, tipo, datos, desde=None, hasta=None):
    """Devuelve False si ese mismo archivo ya estaba guardado."""
    huella = hashlib.sha256(datos).hexdigest()
    with motor.begin() as conexion:
        if conexion.execute(sa.select(archivos.c.id).where(archivos.c.huella == huella)).first():
            return False
        conexion.execute(archivos.insert().values(
            nombre=nombre, tipo=tipo, subido_en=datetime.now(timezone.utc).replace(tzinfo=None),
            huella=huella, datos=datos, desde=desde, hasta=hasta,
        ))
    return True


def listar(motor):
    consulta = sa.select(
        archivos.c.id, archivos.c.nombre, archivos.c.tipo, archivos.c.desde, archivos.c.hasta, archivos.c.subido_en
    ).order_by(archivos.c.subido_en.desc())
    with motor.connect() as conexion:
        tabla = pd.read_sql(consulta, conexion)
    tabla["subido_en"] = pd.to_datetime(tabla["subido_en"]).dt.tz_localize("UTC").dt.tz_convert(ZONA_CHILE).dt.tz_localize(None)
    return tabla


def ultimos(motor):
    """El archivo de actividad más reciente y los de equipos que caen dentro de su período."""
    with motor.connect() as conexion:
        actividad = conexion.execute(
            sa.select(archivos.c.id, archivos.c.desde, archivos.c.hasta)
            .where(archivos.c.tipo == "actividad", archivos.c.hasta.is_not(None))
            .order_by(archivos.c.hasta.desc(), archivos.c.subido_en.desc())
            .limit(1)
        ).first()
        if actividad is None:
            return []
        equipos = conexion.execute(
            sa.select(archivos.c.id).where(
                archivos.c.tipo == "export", archivos.c.desde <= actividad.hasta, archivos.c.hasta >= actividad.desde
            )
        ).scalars().all()
    return [actividad.id, *equipos]


def leer(motor, id_archivo):
    with motor.connect() as conexion:
        return conexion.execute(
            sa.select(archivos.c.nombre, archivos.c.tipo, archivos.c.datos).where(archivos.c.id == id_archivo)
        ).one()
