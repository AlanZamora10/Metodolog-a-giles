import sys
import os

# Asegurar que el directorio de middleware esté en sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MIDDLEWARE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../.."))

if MIDDLEWARE_DIR not in sys.path:
    sys.path.insert(0, MIDDLEWARE_DIR)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Entorno de pruebas (antes de importar la app): sin PostgreSQL -> SQLite en memoria, secretos sólo de prueba.
# TEST_DATABASE_URL permite ejecutar la misma suite contra un PostgreSQL real si se desea.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")
os.environ["DB_CONNECT_RETRIES"] = "1"
os.environ["JWT_SECRET"] = "jwt-secreto-solo-para-pruebas-automatizadas-2026"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["MSSQL_HOST"] = ""  # sin SQL Server en pruebas unitarias (TEST_DATABASE_URL para pruebas reales)
os.environ["AGENT_URL"] = "http://agente-inexistente.invalid:8001"  # fuerza el respaldo determinista
os.environ["AGENT_INFERENCE_TIMEOUT_SECONDS"] = "2"


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def moodle_login_simulado(monkeypatch):
    """El login se valida contra Moodle: en pruebas se usa un Moodle simulado (tests/moodle_fake.py)."""
    from app.services import auth_service
    from moodle_fake import FakeMoodleAuth

    FakeMoodleAuth.caido = False
    monkeypatch.setattr(auth_service, "MoodleClient", FakeMoodleAuth)
    yield


@pytest.fixture(autouse=True)
def motor_real_en_pruebas_integradas(monkeypatch):
    """
    Con TEST_DATABASE_URL (p. ej. SQL Server en Docker), las pruebas que piden un motor "nuevo" reciben la
    base de PRUEBAS real vaciada en vez de SQLite, para validar todo el código contra ese motor.
    Nunca se usa con la base de producción: sólo con la URL de pruebas indicada explícitamente.
    """
    if not os.environ.get("TEST_DATABASE_URL"):
        yield
        return
    from sqlalchemy import text
    from app import database

    def base_de_pruebas_vacia():
        engine = database.get_engine()
        with engine.begin() as conn:
            conn.execute(text("DROP VIEW IF EXISTS vista_panel_curso"))
        database.metadata.drop_all(engine)
        return engine

    monkeypatch.setattr(database, "new_sqlite_engine", base_de_pruebas_vacia)
    yield
