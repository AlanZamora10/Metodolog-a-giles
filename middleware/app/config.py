import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Capa Inteligente de Seguimiento Académico para Moodle"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Base de datos activa (Fase A): SQL Server MoodleUTADB, construida desde MSSQL_* (sólo entorno).
    # DATABASE_URL explícita tiene prioridad (p. ej. pruebas contra otro motor). Si no hay ninguna o la base
    # no responde, el middleware usa SQLite en memoria (pruebas unitarias / modo degradado).
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    MSSQL_HOST: str = os.getenv("MSSQL_HOST", "")
    MSSQL_PORT: int = int(os.getenv("MSSQL_PORT", "1433") or 1433)
    MSSQL_USER: str = os.getenv("MSSQL_USER", "")
    MSSQL_PASSWORD: str = os.getenv("MSSQL_PASSWORD", "")
    MSSQL_DB: str = os.getenv("MSSQL_DB", "MoodleUTADB")
    MSSQL_DRIVER: str = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")
    DB_CONNECT_RETRIES: int = int(os.getenv("DB_CONNECT_RETRIES", "10"))
    DB_CONNECT_RETRY_SECONDS: float = float(os.getenv("DB_CONNECT_RETRY_SECONDS", "2"))

    # Periodo académico al que se asocian los parciales sincronizados desde Moodle
    PERIODO_CODIGO: str = os.getenv("PERIODO_CODIGO", "2026-JD")
    PERIODO_NOMBRE: str = os.getenv("PERIODO_NOMBRE", "Julio a Diciembre 2026")
    PERIODO_INICIO: str = os.getenv("PERIODO_INICIO", "2026-07-01")
    PERIODO_FIN: str = os.getenv("PERIODO_FIN", "2026-12-31")

    # Moodle
    MOODLE_URL: str = os.getenv("MOODLE_URL", "http://moodle:8080")
    # Moodle (Bitnami) arma su wwwroot con el header Host; dentro de la red Docker
    # se envía el host público (localhost) para que Moodle no rechace la petición.
    MOODLE_HOST_HEADER: str = os.getenv("MOODLE_HOST_HEADER", "")
    MOODLE_TOKEN: str = os.getenv("MOODLE_TOKEN") or os.getenv("MOODLE_WS_TOKEN", "")
    MOODLE_WS_TOKEN: str = os.getenv("MOODLE_WS_TOKEN") or os.getenv("MOODLE_TOKEN", "")
    MOODLE_ENDPOINT: str = "/webservice/rest/server.php"
    # URL pública de Moodle para los enlaces que se devuelven al navegador (Moodle arma los suyos con el Host interno)
    MOODLE_EXTERNAL_URL: str = os.getenv("MOODLE_EXTERNAL_URL", "http://localhost:8080").rstrip("/")
    MOODLE_TIMEOUT_SECONDS: float = float(os.getenv("MOODLE_TIMEOUT_SECONDS", "20"))
    # Prefijo de idnumber de los cursos del portafolio sembrados en Moodle
    MOODLE_COURSE_PREFIX: str = os.getenv("MOODLE_COURSE_PREFIX", "SOF-")

    # Ollama Agent
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10"))

    # Seguridad JWT (sin secreto por defecto: debe venir del entorno)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # Login unificado (Fase A): las credenciales del docente se validan contra Moodle (login/token.php)
    MOODLE_LOGIN_SERVICE: str = os.getenv("MOODLE_LOGIN_SERVICE", "moodle_mobile_app")
    # Días de plazo por defecto para las tareas de refuerzo publicadas en Moodle
    REFUERZO_DIAS_PLAZO: int = int(os.getenv("REFUERZO_DIAS_PLAZO", "7"))

    # Configuración de Servidor
    HOST: str = os.getenv("MIDDLEWARE_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MIDDLEWARE_PORT", "8000"))

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()


def database_url() -> str:
    """URL de la base activa: DATABASE_URL explícita, o SQL Server armado desde MSSQL_* (contraseña escapada)."""
    if settings.DATABASE_URL.strip():
        return settings.DATABASE_URL.strip()
    if settings.MSSQL_HOST.strip():
        from sqlalchemy.engine import URL
        return URL.create(
            "mssql+pyodbc",
            username=settings.MSSQL_USER,
            password=settings.MSSQL_PASSWORD,
            host=settings.MSSQL_HOST,
            port=settings.MSSQL_PORT,
            database=settings.MSSQL_DB,
            query={"driver": settings.MSSQL_DRIVER, "TrustServerCertificate": "yes", "Encrypt": "yes"},
        ).render_as_string(hide_password=False)
    return ""
