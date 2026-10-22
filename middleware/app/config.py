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
    MOODLE_WS_TOKEN: str = os.getenv("MOODLE_WS_TOKEN", "ws_mock_token_uta_fisei_sprint1")
    MOODLE_ENDPOINT: str = "/webservice/rest/server.php"

    # Ollama Agent
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10"))

    # Configuración de Servidor
    HOST: str = os.getenv("MIDDLEWARE_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MIDDLEWARE_PORT", "8000"))

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
