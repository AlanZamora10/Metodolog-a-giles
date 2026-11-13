import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Capa Inteligente de Seguimiento Académico para Moodle"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Base de datos analítica (PostgreSQL). Sin valor por defecto: las credenciales llegan sólo por entorno.
    # Si está vacía o PostgreSQL no responde, el middleware usa SQLite en memoria (pruebas / modo degradado).
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
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

    # Contraseñas de las cuentas semilla (docente, estudiante y administrador). Si falta una, esa cuenta no se crea.
    SEED_DOCENTE_PASSWORD: str = os.getenv("SEED_DOCENTE_PASSWORD", "")
    SEED_ESTUDIANTE_PASSWORD: str = os.getenv("SEED_ESTUDIANTE_PASSWORD", "")
    SEED_ADMIN_PASSWORD: str = os.getenv("SEED_ADMIN_PASSWORD", "")

    # Configuración de Servidor
    HOST: str = os.getenv("MIDDLEWARE_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MIDDLEWARE_PORT", "8000"))

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
