from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://arqai:arqai_dev_password@localhost:5432/arqai_fwa"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:8b"

    # App
    secret_key: str = "dev-secret-key-change-in-production"
    environment: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
