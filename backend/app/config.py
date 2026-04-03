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

# Debug logging for Railway deployment
import os
print("=" * 80)
print("ENVIRONMENT VARIABLE CHECK:")
print(f"DATABASE_URL from env: {os.environ.get('DATABASE_URL', 'NOT SET')}")
print(f"DATABASE_URL in settings: {settings.DATABASE_URL}")
print(f"OPENAI_API_KEY set: {'Yes' if settings.OPENAI_API_KEY != 'sk-test-key' else 'No (using default)'}")
print("=" * 80)
