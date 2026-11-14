"""
Capa de conexión y esquema de la base de datos activa de EduMonitor AI.

Fase A: la base activa es SQL Server 2022 (`MoodleUTADB`), conectada con SQLAlchemy Core sobre
`mssql+pyodbc` (ODBC Driver 18, TrustServerCertificate=yes). El mismo esquema funciona en:
  - SQL Server  -> IDENTITY(1,1), NVARCHAR / NVARCHAR(MAX) (JSON), DATETIME2, BIT
  - PostgreSQL  -> vuelta atrás del Sprint 3 (JSONB)
  - SQLite      -> pruebas unitarias y modo degradado (en memoria)

`get_engine()` al primer uso:
  1. (SQL Server) crea la base MoodleUTADB si no existe, conectándose a `master`.
  2. Crea las 12 tablas que falten y la vista `vista_panel_curso` (idempotente).
  3. Ejecuta los hooks de arranque (restaurar la última sincronización, registrar el inicio, ...).
Si la base configurada no responde tras los reintentos, usa SQLite en memoria; /health lo informa.

Notas de diseño para SQL Server:
  - Las claves foráneas no usan ON DELETE CASCADE: SQL Server rechaza múltiples rutas de cascada
    (p. ej. materias -> actividades directa y vía categorias_unidad). La aplicación no borra padres.
  - La unicidad de alertas es un índice filtrado (WHERE regla IS NOT NULL): en SQL Server una
    restricción UNIQUE sólo admite un NULL.
  - Las fechas se guardan en UTC sin zona (DATETIME2); la API las expone en ISO-8601 con +00:00.
"""

import logging
import re
import threading
import time
from typing import Callable, List, Optional

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, MetaData, Numeric,
    Table, Unicode, UnicodeText, UniqueConstraint, create_engine, func, text,
)
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import StaticPool

from app.config import database_url, settings

logger = logging.getLogger("edumonitor.database")

metadata = MetaData()
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _nota(nombre: str, nullable: bool = False) -> Column:
    return Column(nombre, Numeric(4, 2, asdecimal=False), nullable=nullable)


FechaType = DateTime().with_variant(mssql.DATETIME2(), "mssql")


def _fecha(nombre: str, con_defecto: bool = True) -> Column:
    # DATETIME2 en SQL Server / TIMESTAMP en PostgreSQL / texto ISO en SQLite (siempre UTC)
    return Column(nombre, FechaType, server_default=func.current_timestamp() if con_defecto else None)


# ----------------------------------------------------------------------------- 12 tablas
usuarios = Table(
    "usuarios", metadata,
    Column("id", Integer, primary_key=True),
    Column("nombres", Unicode(120), nullable=False),
    Column("email", Unicode(120), nullable=False, unique=True),
    # Fase A: los docentes se autentican contra Moodle; aquí se guarda el marcador 'MOODLE'
    Column("password_hash", Unicode(255), nullable=False),
    Column("rol", Unicode(20), nullable=False),
    Column("id_number", Unicode(30)),
    Column("activo", Boolean, default=True),
    _fecha("created_at"),
    Column("moodle_user_id", Integer),
    Column("moodle_username", Unicode(100)),
    _fecha("ultimo_acceso", con_defecto=False),
    CheckConstraint("rol IN ('DOCENTE', 'ESTUDIANTE', 'ADMIN')", name="usuarios_rol_check"),
)

materias = Table(
    "materias", metadata,
    Column("id", Integer, primary_key=True),
    Column("codigo", Unicode(20), nullable=False, unique=True),
    Column("nombre", Unicode(150), nullable=False),
    Column("carrera", Unicode(100), default="Ingeniería de Software - FISEI"),
    Column("docente_titular", Unicode(150)),
    Column("creditos", Integer, default=3),
    Column("activo", Boolean, default=True),
    _fecha("created_at"),
    Column("moodle_course_id", Integer),
    Column("docentes", JSONType),   # correos de los docentes del curso en Moodle
)

periodos = Table(
    "periodos", metadata,
    Column("id", Integer, primary_key=True),
    Column("codigo", Unicode(50), nullable=False, unique=True),
    Column("nombre", Unicode(100), nullable=False),
    Column("fecha_inicio", Date, nullable=False),
    Column("fecha_fin", Date, nullable=False),
    Column("activo", Boolean, default=True),
    _fecha("created_at"),
)

parciales = Table(
    "parciales", metadata,
    Column("id", Integer, primary_key=True),
    Column("periodo_id", Integer, ForeignKey("periodos.id"), nullable=False),
    Column("numero_parcial", Integer, nullable=False),
    Column("nombre", Unicode(50), nullable=False),
    Column("fecha_inicio", Date),
    Column("fecha_fin", Date),
    UniqueConstraint("periodo_id", "numero_parcial", name="ux_parciales_periodo_numero"),
)

estudiantes = Table(
    "estudiantes", metadata,
    Column("id", Integer, primary_key=True),
    Column("id_number", Unicode(30), nullable=False, unique=True),
    Column("nombres", Unicode(120), nullable=False),
    Column("email", Unicode(120), nullable=False, unique=True),
    Column("moodle_user_id", Integer),
    Column("activo", Boolean, default=True),
    _fecha("created_at"),
)

categorias_unidad = Table(
    "categorias_unidad", metadata,
    Column("id", Integer, primary_key=True),
    Column("materia_id", Integer, ForeignKey("materias.id"), nullable=False),
    Column("nombre", Unicode(80), nullable=False),
    Column("numero_unidad", Integer, nullable=False),
    Column("titulo", Unicode(150), nullable=False),
    Column("descripcion", UnicodeText),
    UniqueConstraint("materia_id", "numero_unidad", name="ux_unidades_materia_numero"),
)

actividades = Table(
    "actividades", metadata,
    Column("id", Integer, primary_key=True),
    Column("materia_id", Integer, ForeignKey("materias.id"), nullable=False),
    Column("parcial_id", Integer, ForeignKey("parciales.id"), nullable=False),
    Column("unidad_id", Integer, ForeignKey("categorias_unidad.id"), nullable=False),
    Column("id_number_normalizado", Unicode(60), nullable=False, unique=True),
    Column("nombre", Unicode(180), nullable=False),
    Column("tipo_componente", Unicode(20), nullable=False),
    Column("ponderacion_componente", Numeric(4, 2, asdecimal=False), nullable=False),
    Column("tema", Unicode(60), nullable=False),
    Column("moodle_item_id", Integer),
    Column("nota_maxima", Numeric(4, 2, asdecimal=False), default=10.0),
    _fecha("created_at"),
    CheckConstraint("tipo_componente IN ('AUTONOMO', 'TAREAS', 'PAE')", name="actividades_tipo_check"),
)

calificaciones = Table(
    "calificaciones", metadata,
    Column("id", Integer, primary_key=True),
    Column("estudiante_id", Integer, ForeignKey("estudiantes.id"), nullable=False),
    Column("actividad_id", Integer, ForeignKey("actividades.id"), nullable=False),
    _nota("nota", nullable=True),  # NULL cuando la actividad está PENDIENTE de revisión
    Column("entregado", Boolean, default=True),
    _fecha("fecha_calificacion"),
    Column("estado", Unicode(20), default="CALIFICADO"),  # CALIFICADO | SIN_ENTREGA | PENDIENTE
    UniqueConstraint("estudiante_id", "actividad_id", name="ux_calificaciones_estudiante_actividad"),
)

calificaciones_ponderadas = Table(
    "calificaciones_ponderadas", metadata,
    Column("id", Integer, primary_key=True),
    Column("estudiante_id", Integer, ForeignKey("estudiantes.id"), nullable=False),
    Column("materia_id", Integer, ForeignKey("materias.id"), nullable=False),
    Column("parcial_id", Integer, ForeignKey("parciales.id"), nullable=False),
    _nota("nota_autonomo"),
    _nota("nota_tareas"),
    _nota("nota_pae"),
    _nota("nota_final"),
    Column("nivel_riesgo", Unicode(20), nullable=False),
    Column("tendencia", Unicode(20), default="ESTABLE"),
    Column("pendiente_regresion", Numeric(6, 3, asdecimal=False), default=0.0),
    Column("probabilidad_aprobacion", Integer, default=50),
    _fecha("updated_at"),
    UniqueConstraint("estudiante_id", "materia_id", "parcial_id", name="ux_ponderadas_estudiante_materia_parcial"),
)

logs_sistema = Table(
    "logs_sistema", metadata,
    Column("id", Integer, primary_key=True),
    _fecha("timestamp"),
    Column("tipo_proceso", Unicode(60), nullable=False),
    Column("estado", Unicode(20), nullable=False),
    Column("mensaje", UnicodeText, nullable=False),
    Column("detalle", JSONType),
    Column("tiempo_ejecucion_ms", Integer),
    Column("error_stack", UnicodeText),
    CheckConstraint("estado IN ('EXITO', 'ERROR', 'ADVERTENCIA', 'INFO')", name="logs_estado_check"),
)

alertas_tempranas = Table(
    "alertas_tempranas", metadata,
    Column("id", Integer, primary_key=True),
    Column("estudiante_id", Integer, ForeignKey("estudiantes.id"), nullable=False),
    Column("materia_id", Integer, ForeignKey("materias.id"), nullable=False),
    Column("parcial_id", Integer, ForeignKey("parciales.id"), nullable=False),
    Column("nivel", Unicode(20), nullable=False),
    Column("unidad_critica", Unicode(80)),
    Column("tema_critico", Unicode(80)),
    Column("motivo", UnicodeText, nullable=False),
    Column("diagnostico_ia", UnicodeText),
    Column("tipo_accion_sugerida", Unicode(100)),
    Column("resuelto", Boolean, default=False),
    _fecha("fecha_alerta"),
    _fecha("fecha_resolucion", con_defecto=False),
    Column("regla", Unicode(30)),       # R1_NOTA_CRITICA | R2_DESCENSO
    Column("estado", Unicode(20), default="ABIERTA"),  # ABIERTA | ATENDIDA | PUBLICADO | CERRADA | RESUELTA
    _nota("nota_final", nullable=True),
    Column("pendiente", Numeric(6, 3, asdecimal=False)),
    _fecha("fecha_actualizacion"),
)

# Unicidad (estudiante, materia, parcial, regla) sólo para alertas con regla: índice filtrado
Index(
    "ux_alertas_estudiante_regla",
    alertas_tempranas.c.estudiante_id, alertas_tempranas.c.materia_id,
    alertas_tempranas.c.parcial_id, alertas_tempranas.c.regla,
    unique=True,
    mssql_where=alertas_tempranas.c.regla.is_not(None),
    postgresql_where=alertas_tempranas.c.regla.is_not(None),
    sqlite_where=alertas_tempranas.c.regla.is_not(None),
)

refuerzos = Table(
    "refuerzos", metadata,
    Column("id", Integer, primary_key=True),
    Column("alerta_id", Integer, ForeignKey("alertas_tempranas.id"), nullable=False, unique=True),
    Column("titulo", Unicode(200), nullable=False),
    Column("descripcion", UnicodeText),
    Column("instrucciones", UnicodeText),
    Column("actividades", JSONType),
    Column("origen", Unicode(40), nullable=False),
    Column("estado", Unicode(20), default="BORRADOR"),   # BORRADOR | PUBLICADO
    Column("cmid", Integer),                              # ID real del módulo creado en Moodle
    Column("moodle_url", Unicode(255)),
    _fecha("fecha_creacion"),
    _fecha("fecha_publicacion", con_defecto=False),
    _fecha("fecha_entrega", con_defecto=False),
)

_VISTA_PANEL = """
SELECT cp.id AS resumen_id, m.codigo AS materia_codigo, m.nombre AS materia_nombre, p.numero_parcial,
       e.id_number AS estudiante_id_number, e.nombres AS estudiante_nombre, e.email AS estudiante_email,
       cp.nota_autonomo, cp.nota_tareas, cp.nota_pae, cp.nota_final, cp.nivel_riesgo, cp.tendencia,
       cp.probabilidad_aprobacion, cp.updated_at
FROM calificaciones_ponderadas cp
JOIN estudiantes e ON cp.estudiante_id = e.id
JOIN materias m ON cp.materia_id = m.id
JOIN parciales p ON cp.parcial_id = p.id
"""

# Columnas añadidas después de la creación inicial (idempotente en volúmenes existentes)
_COLUMNAS_NUEVAS = [
    ("usuarios", "moodle_user_id", "INT"),
    ("usuarios", "moodle_username", "NVARCHAR(100)"),
    ("usuarios", "ultimo_acceso", "DATETIME2"),
    ("refuerzos", "moodle_url", "NVARCHAR(255)"),
    ("refuerzos", "fecha_entrega", "DATETIME2"),
]


def _migrar_columnas(conn, dialecto: str) -> None:
    for tabla, columna, tipo_mssql in _COLUMNAS_NUEVAS:
        if dialecto == "mssql":
            conn.execute(text(
                f"IF COL_LENGTH('{tabla}', '{columna}') IS NULL ALTER TABLE {tabla} ADD {columna} {tipo_mssql}"))
        elif dialecto == "postgresql":
            tipo = {"NVARCHAR(100)": "VARCHAR(100)", "NVARCHAR(255)": "VARCHAR(255)",
                    "DATETIME2": "TIMESTAMP"}.get(tipo_mssql, tipo_mssql)
            conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {columna} {tipo}"))


def init_schema(engine: Engine) -> None:
    """Crea las tablas e índices que falten, añade columnas nuevas y (re)crea la vista. Idempotente."""
    metadata.create_all(engine)
    dialecto = engine.dialect.name
    with engine.begin() as conn:
        _migrar_columnas(conn, dialecto)
        if dialecto == "mssql":
            conn.execute(text(f"CREATE OR ALTER VIEW vista_panel_curso AS {_VISTA_PANEL}"))
        elif dialecto == "postgresql":
            conn.execute(text(f"CREATE OR REPLACE VIEW vista_panel_curso AS {_VISTA_PANEL}"))
        else:
            conn.execute(text(f"CREATE VIEW IF NOT EXISTS vista_panel_curso AS {_VISTA_PANEL}"))


# ----------------------------------------------------------------------------- Motor
_engine: Optional[Engine] = None
_backend: str = "sin_inicializar"
_lock = threading.RLock()
_hooks: List[Callable[[Engine], None]] = []


def on_ready(hook: Callable[[Engine], None]) -> Callable[[Engine], None]:
    """Registra una función que se ejecuta cuando el esquema está listo."""
    _hooks.append(hook)
    return hook


def _engine_sqlite() -> Engine:
    return create_engine(
        "sqlite+pysqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}, future=True
    )


def _normalizar_url(url: str) -> str:
    """postgresql:// -> postgresql+psycopg2:// (driver instalado; SQLAlchemy 2.1 asume psycopg 3)."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


def _crear_base_mssql(url: str) -> None:
    """Crea la base de datos de SQL Server si no existe (conectándose a master en modo autocommit)."""
    destino = make_url(url)
    nombre = destino.database or ""
    if not re.fullmatch(r"[A-Za-z0-9_]+", nombre):
        raise ValueError(f"Nombre de base de datos no válido para SQL Server: {nombre!r}")
    master = create_engine(destino.set(database="master"), isolation_level="AUTOCOMMIT",
                           connect_args={"timeout": 5}, future=True)
    try:
        with master.connect() as conn:
            conn.execute(text(f"IF DB_ID(N'{nombre}') IS NULL CREATE DATABASE [{nombre}]"))
    finally:
        master.dispose()


def _engine_remoto(url: str) -> Optional[Engine]:
    url = _normalizar_url(url)
    dialecto = make_url(url).get_backend_name()
    connect_args = {"timeout": 5} if dialecto == "mssql" else {"connect_timeout": 5}
    intentos = max(1, settings.DB_CONNECT_RETRIES)
    for intento in range(1, intentos + 1):
        try:
            if dialecto == "mssql":
                _crear_base_mssql(url)
            engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args, future=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as ex:  # base iniciando, credenciales o driver: se reintenta y luego hay respaldo
            logger.warning("Base %s no disponible (intento %s/%s): %s: %s",
                           dialecto, intento, intentos, ex.__class__.__name__, str(ex)[:200])
            if intento < intentos:
                time.sleep(settings.DB_CONNECT_RETRY_SECONDS)
    return None


def _inicializar(engine: Engine, backend: str) -> Engine:
    global _engine, _backend
    init_schema(engine)
    _engine, _backend = engine, backend
    for hook in _hooks:
        try:
            hook(engine)
        except Exception:  # un hook fallido no impide arrancar
            logger.exception("Falló el hook de arranque %s", getattr(hook, "__name__", hook))
    return engine


def get_engine() -> Engine:
    """Motor activo; la primera llamada conecta, crea/migra el esquema y ejecuta los hooks de arranque."""
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        url = database_url()
        if url:
            engine = _engine_remoto(url)
            if engine is not None:
                return _inicializar(engine, engine.dialect.name)
            logger.error("No se pudo conectar a la base configurada; se usa SQLite en memoria (no persistente).")
            return _inicializar(_engine_sqlite(), "sqlite_memoria_respaldo")
        return _inicializar(_engine_sqlite(), "sqlite_memoria")


def use_engine(engine: Engine, backend: str = "personalizado") -> Engine:
    """Inyección de dependencias para pruebas: reemplaza el motor activo y re-ejecuta el arranque."""
    global _engine
    with _lock:
        _engine = None
        return _inicializar(engine, backend)


def new_sqlite_engine() -> Engine:
    return _engine_sqlite()


def backend_name() -> str:
    return _backend
