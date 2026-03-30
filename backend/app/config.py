"""Application configuration using Pydantic Settings"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Environment variables can be set in .env file or via system env vars.
    """

    # Database (defaults to SQLite for testing if psycopg2 not available)
    DATABASE_URL: str = "sqlite:///./test.db"

    # OpenAI
    OPENAI_API_KEY: str = "sk-test-key"  # Default for testing, override in production

    # Application
    DEBUG: bool = False
    APP_NAME: str = "Tuppence Backend"
    VERSION: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
