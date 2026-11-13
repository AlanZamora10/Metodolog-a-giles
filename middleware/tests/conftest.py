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
os.environ["SEED_DOCENTE_PASSWORD"] = "Docente2026!"
os.environ["SEED_ESTUDIANTE_PASSWORD"] = "Estudiante2026!"
os.environ["SEED_ADMIN_PASSWORD"] = "Admin2026!"
os.environ["AGENT_URL"] = "http://agente-inexistente.invalid:8001"  # fuerza el respaldo determinista
os.environ["AGENT_INFERENCE_TIMEOUT_SECONDS"] = "2"
