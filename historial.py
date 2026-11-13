import hashlib
from datetime import datetime

import pandas as pd
import sqlalchemy as sa
import streamlit as st

metadata = sa.MetaData()
archivos = sa.Table(
    "archivos",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("nombre", sa.String(255), nullable=False),
    sa.Column("tipo", sa.String(20), nullable=False),
    sa.Column("subido_en", sa.DateTime, nullable=False),
    sa.Column("huella", sa.String(64), nullable=False, unique=True),
    sa.Column("datos", sa.LargeBinary, nullable=False),
)


@st.cache_resource
def conectar():
    # Sin base configurada en los secretos no hay historial: guardar en el disco de Streamlit Cloud se perdería al reiniciar.
    try:
        configurada = "sql" in st.secrets.get("connections", {})
    except Exception:
        configurada = False
    if not configurada:
        return None
    motor = st.connection("sql").engine
    metadata.create_all(motor)
    return motor


def guardar(motor, nombre, tipo, datos):
    """Devuelve False si ese mismo archivo ya estaba guardado."""
    huella = hashlib.sha256(datos).hexdigest()
    with motor.begin() as conexion:
        if conexion.execute(sa.select(archivos.c.id).where(archivos.c.huella == huella)).first():
            return False
        # shortcut: hora del servidor (en Streamlit Cloud es UTC, 3 h más que Chile); convertir al pasar a la nube.
        conexion.execute(archivos.insert().values(
            nombre=nombre, tipo=tipo, subido_en=datetime.now(), huella=huella, datos=datos,
        ))
    return True


def listar(motor):
    consulta = sa.select(archivos.c.id, archivos.c.nombre, archivos.c.tipo, archivos.c.subido_en).order_by(
        archivos.c.subido_en.desc()
    )
    with motor.connect() as conexion:
        return pd.read_sql(consulta, conexion)


def leer(motor, id_archivo):
    with motor.connect() as conexion:
        return conexion.execute(
            sa.select(archivos.c.nombre, archivos.c.tipo, archivos.c.datos).where(archivos.c.id == id_archivo)
        ).one()
