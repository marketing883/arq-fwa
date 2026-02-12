from pydantic import model_validator
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

    # Security
    allowed_origins: str = "http://localhost:3000,http://localhost:80,http://localhost"
    rate_limit_per_minute: int = 60
    encryption_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _validate_production(self):
        if self.environment == "production":
            if self.secret_key == "dev-secret-key-change-in-production":
                raise ValueError(
                    "Production requires a non-default SECRET_KEY"
                )
            if "arqai_dev_password" in self.database_url:
                raise ValueError(
                    "Production must not use the default dev database password"
                )
            if not self.encryption_key:
                raise ValueError(
                    "Production requires ENCRYPTION_KEY for PII encryption"
                )
        return self


settings = Settings()
