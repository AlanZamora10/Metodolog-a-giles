"""
Capa de conexión y esquema de la base analítica (Sprint 3).

- Motor SQLAlchemy Core construido desde DATABASE_URL (PostgreSQL `analytics-db`).
- Las tablas reflejan `database/init.sql` (11 tablas) + la tabla 12 `refuerzos`.
- `init_schema()` aplica una migración idempotente al arrancar: crea las tablas que falten y
  añade las columnas nuevas del Sprint 3 sin borrar el volumen existente.
- Respaldo limpio: si DATABASE_URL está vacía (pruebas unitarias) o PostgreSQL no responde tras
  los reintentos, se usa SQLite en memoria con el mismo esquema. /health informa qué motor está activo.
"""

import logging
import threading
import time
from typing import Callable, List, Optional

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, MetaData, Numeric,
    String, Table, Text, UniqueConstraint, create_engine, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.config import settings

logger = logging.getLogger("edumonitor.database")

metadata = MetaData()
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _nota(nombre: str, nullable: bool = False) -> Column:
    return Column(nombre, Numeric(4, 2, asdecimal=False), nullable=nullable)


def _creado(nombre: str = "created_at") -> Column:
    return Column(nombre, DateTime(timezone=True), server_default=func.now())


# ----------------------------------------------------------------------------- Tablas (init.sql)
usuarios = Table(
    "usuarios", metadata,
    Column("id", Integer, primary_key=True),
    Column("nombres", String(120), nullable=False),
    Column("email", String(120), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("rol", String(20), nullable=False),
    Column("id_number", String(30)),
    Column("activo", Boolean, default=True),
    _creado(),
    CheckConstraint("rol IN ('DOCENTE', 'ESTUDIANTE', 'ADMIN')", name="usuarios_rol_check"),
)

materias = Table(
    "materias", metadata,
    Column("id", Integer, primary_key=True),
    Column("codigo", String(20), nullable=False, unique=True),
    Column("nombre", String(150), nullable=False),
    Column("carrera", String(100), default="Ingeniería de Software - FISEI"),
    Column("docente_titular", String(150)),
    Column("creditos", Integer, default=3),
    Column("activo", Boolean, default=True),
    _creado(),
    # Sprint 3: vínculo con el curso de Moodle y docentes (emails) con permiso sobre la materia
    Column("moodle_course_id", Integer),
    Column("docentes", JSONType),
)

periodos = Table(
    "periodos", metadata,
    Column("id", Integer, primary_key=True),
    Column("codigo", String(50), nullable=False, unique=True),
    Column("nombre", String(100), nullable=False),
    Column("fecha_inicio", Date, nullable=False),
    Column("fecha_fin", Date, nullable=False),
    Column("activo", Boolean, default=True),
    _creado(),
)

parciales = Table(
    "parciales", metadata,
    Column("id", Integer, primary_key=True),
    Column("periodo_id", Integer, ForeignKey("periodos.id", ondelete="CASCADE"), nullable=False),
    Column("numero_parcial", Integer, nullable=False),
    Column("nombre", String(50), nullable=False),
    Column("fecha_inicio", Date),
    Column("fecha_fin", Date),
    UniqueConstraint("periodo_id", "numero_parcial"),
)

estudiantes = Table(
    "estudiantes", metadata,
    Column("id", Integer, primary_key=True),
    Column("id_number", String(30), nullable=False, unique=True),
    Column("nombres", String(120), nullable=False),
    Column("email", String(120), nullable=False, unique=True),
    Column("moodle_user_id", Integer),
    Column("activo", Boolean, default=True),
    _creado(),
)

categorias_unidad = Table(
    "categorias_unidad", metadata,
    Column("id", Integer, primary_key=True),
    Column("materia_id", Integer, ForeignKey("materias.id", ondelete="CASCADE"), nullable=False),
    Column("nombre", String(80), nullable=False),
    Column("numero_unidad", Integer, nullable=False),
    Column("titulo", String(150), nullable=False),
    Column("descripcion", Text),
    UniqueConstraint("materia_id", "numero_unidad"),
)

actividades = Table(
    "actividades", metadata,
    Column("id", Integer, primary_key=True),
    Column("materia_id", Integer, ForeignKey("materias.id", ondelete="CASCADE"), nullable=False),
    Column("parcial_id", Integer, ForeignKey("parciales.id", ondelete="CASCADE"), nullable=False),
    Column("unidad_id", Integer, ForeignKey("categorias_unidad.id", ondelete="CASCADE"), nullable=False),
    Column("id_number_normalizado", String(60), nullable=False, unique=True),
    Column("nombre", String(180), nullable=False),
    Column("tipo_componente", String(20), nullable=False),
    Column("ponderacion_componente", Numeric(4, 2, asdecimal=False), nullable=False),
    Column("tema", String(60), nullable=False),
    Column("moodle_item_id", Integer),
    Column("nota_maxima", Numeric(4, 2, asdecimal=False), default=10.0),
    _creado(),
    CheckConstraint("tipo_componente IN ('AUTONOMO', 'TAREAS', 'PAE')", name="actividades_tipo_check"),
)

calificaciones = Table(
    "calificaciones", metadata,
    Column("id", Integer, primary_key=True),
    Column("estudiante_id", Integer, ForeignKey("estudiantes.id", ondelete="CASCADE"), nullable=False),
    Column("actividad_id", Integer, ForeignKey("actividades.id", ondelete="CASCADE"), nullable=False),
    _nota("nota", nullable=True),  # Sprint 3: NULL cuando la actividad está PENDIENTE de revisión
    Column("entregado", Boolean, default=True),
    Column("fecha_calificacion", DateTime(timezone=True), server_default=func.now()),
    Column("estado", String(20), default="CALIFICADO"),  # CALIFICADO | SIN_ENTREGA | PENDIENTE
    UniqueConstraint("estudiante_id", "actividad_id"),
)

calificaciones_ponderadas = Table(
    "calificaciones_ponderadas", metadata,
    Column("id", Integer, primary_key=True),
    Column("estudiante_id", Integer, ForeignKey("estudiantes.id", ondelete="CASCADE"), nullable=False),
    Column("materia_id", Integer, ForeignKey("materias.id", ondelete="CASCADE"), nullable=False),
    Column("parcial_id", Integer, ForeignKey("parciales.id", ondelete="CASCADE"), nullable=False),
    _nota("nota_autonomo"),
    _nota("nota_tareas"),
    _nota("nota_pae"),
    _nota("nota_final"),
    Column("nivel_riesgo", String(20), nullable=False),
    Column("tendencia", String(20), default="ESTABLE"),
    Column("pendiente_regresion", Numeric(6, 3, asdecimal=False), default=0.0),
    Column("probabilidad_aprobacion", Integer, default=50),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("estudiante_id", "materia_id", "parcial_id"),
)

logs_sistema = Table(
    "logs_sistema", metadata,
    Column("id", Integer, primary_key=True),
    Column("timestamp", DateTime(timezone=True), server_default=func.now()),
    Column("tipo_proceso", String(60), nullable=False),
    Column("estado", String(20), nullable=False),
    Column("mensaje", Text, nullable=False),
    Column("detalle", JSONType),
    Column("tiempo_ejecucion_ms", Integer),
    Column("error_stack", Text),
    CheckConstraint("estado IN ('EXITO', 'ERROR', 'ADVERTENCIA', 'INFO')", name="logs_estado_check"),
)

alertas_tempranas = Table(
    "alertas_tempranas", metadata,
    Column("id", Integer, primary_key=True),
    Column("estudiante_id", Integer, ForeignKey("estudiantes.id", ondelete="CASCADE"), nullable=False),
    Column("materia_id", Integer, ForeignKey("materias.id", ondelete="CASCADE"), nullable=False),
    Column("parcial_id", Integer, ForeignKey("parciales.id", ondelete="CASCADE"), nullable=False),
    Column("nivel", String(20), nullable=False),
    Column("unidad_critica", String(80)),
    Column("tema_critico", String(80)),
    Column("motivo", Text, nullable=False),
    Column("diagnostico_ia", Text),
    Column("tipo_accion_sugerida", String(100)),
    Column("resuelto", Boolean, default=False),
    Column("fecha_alerta", DateTime(timezone=True), server_default=func.now()),
    Column("fecha_resolucion", DateTime(timezone=True)),
    # Sprint 3: regla que la disparó y ciclo de vida (ABIERTA, ATENDIDA, PUBLICADO, CERRADA, RESUELTA)
    Column("regla", String(30)),
    Column("estado", String(20), default="ABIERTA"),
    _nota("nota_final", nullable=True),
    Column("pendiente", Numeric(6, 3, asdecimal=False)),
    Column("fecha_actualizacion", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("estudiante_id", "materia_id", "parcial_id", "regla", name="ux_alertas_estudiante_regla"),
)

# Tabla 12 (Sprint 3): borradores de refuerzo pedagógico generados al atender una alerta
refuerzos = Table(
    "refuerzos", metadata,
    Column("id", Integer, primary_key=True),
    Column("alerta_id", Integer, ForeignKey("alertas_tempranas.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("titulo", String(200), nullable=False),
    Column("descripcion", Text),
    Column("instrucciones", Text),
    Column("actividades", JSONType),
    Column("origen", String(40), nullable=False),
    Column("estado", String(20), default="BORRADOR"),
    Column("cmid", Integer),
    Column("fecha_creacion", DateTime(timezone=True), server_default=func.now()),
    Column("fecha_publicacion", DateTime(timezone=True)),
)

# Migración idempotente para volúmenes creados con el init.sql del Sprint 1/2 (sólo PostgreSQL)
_MIGRACIONES_POSTGRES = [
    "ALTER TABLE materias ADD COLUMN IF NOT EXISTS moodle_course_id INT",
    "ALTER TABLE materias ADD COLUMN IF NOT EXISTS docentes JSONB",
    "ALTER TABLE calificaciones ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'CALIFICADO'",
    "ALTER TABLE calificaciones ALTER COLUMN nota DROP NOT NULL",
    "ALTER TABLE alertas_tempranas ADD COLUMN IF NOT EXISTS regla VARCHAR(30)",
    "ALTER TABLE alertas_tempranas ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'ABIERTA'",
    "ALTER TABLE alertas_tempranas ADD COLUMN IF NOT EXISTS nota_final NUMERIC(4, 2)",
    "ALTER TABLE alertas_tempranas ADD COLUMN IF NOT EXISTS pendiente NUMERIC(6, 3)",
    "ALTER TABLE alertas_tempranas ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMP WITH TIME ZONE "
    "DEFAULT CURRENT_TIMESTAMP",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_alertas_estudiante_regla "
    "ON alertas_tempranas (estudiante_id, materia_id, parcial_id, regla)",
]


def init_schema(engine: Engine) -> None:
    """Crea las tablas que falten y aplica las columnas nuevas (idempotente)."""
    metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for sentencia in _MIGRACIONES_POSTGRES:
                conn.execute(text(sentencia))


# ----------------------------------------------------------------------------- Motor
_engine: Optional[Engine] = None
_backend: str = "sin_inicializar"
_lock = threading.RLock()
_hooks: List[Callable[[Engine], None]] = []


def on_ready(hook: Callable[[Engine], None]) -> Callable[[Engine], None]:
    """Registra una función que se ejecuta una vez cuando el esquema está listo (usuarios semilla, etc.)."""
    _hooks.append(hook)
    return hook


def _engine_sqlite() -> Engine:
    return create_engine(
        "sqlite+pysqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}, future=True
    )


def _normalizar_url(url: str) -> str:
    """postgresql:// -> postgresql+psycopg2:// (driver instalado; SQLAlchemy 2.1 asume psycopg 3 por defecto)."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


def _engine_postgres(url: str) -> Optional[Engine]:
    try:
        engine = create_engine(_normalizar_url(url), pool_pre_ping=True, connect_args={"connect_timeout": 5},
                               future=True)
    except Exception as ex:  # URL inválida o driver ausente: se registra y se usa el respaldo
        logger.error("DATABASE_URL no utilizable (%s: %s)", ex.__class__.__name__, ex)
        return None
    intentos = max(1, settings.DB_CONNECT_RETRIES)
    for intento in range(1, intentos + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as ex:  # PostgreSQL aún iniciando o inaccesible
            logger.warning("PostgreSQL no disponible (intento %s/%s): %s", intento, intentos, ex.__class__.__name__)
            if intento < intentos:
                time.sleep(settings.DB_CONNECT_RETRY_SECONDS)
    engine.dispose()
    return None


def _inicializar(engine: Engine, backend: str) -> Engine:
    global _engine, _backend
    init_schema(engine)
    _engine, _backend = engine, backend
    for hook in _hooks:
        try:
            hook(engine)
        except Exception:  # un hook fallido (p. ej. datos previos inconsistentes) no impide arrancar
            logger.exception("Falló el hook de arranque %s", getattr(hook, "__name__", hook))
    return engine


def get_engine() -> Engine:
    """Motor activo; la primera llamada conecta, migra el esquema y ejecuta los hooks de arranque."""
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        url = (settings.DATABASE_URL or "").strip()
        if url:
            engine = _engine_postgres(url)
            if engine is not None:
                return _inicializar(engine, engine.dialect.name)
            logger.error("No se pudo conectar a la base analítica; se usa SQLite en memoria (datos no persistentes).")
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
