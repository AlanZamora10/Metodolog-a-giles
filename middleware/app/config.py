import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Capa Inteligente de Seguimiento Académico para Moodle"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Base de datos
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://analytics_user:analytics_password_secret123@analytics-db:5432/moodle_analytics"
    )

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

    # Configuración de Servidor
    HOST: str = os.getenv("MIDDLEWARE_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MIDDLEWARE_PORT", "8000"))

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
