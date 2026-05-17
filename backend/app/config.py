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

    # JWT Authentication
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"  # Must be 256-bit random in production
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Stripe
    STRIPE_SECRET_KEY: str = "sk_test_default"  # Default for testing, override in production
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_default"  # Frontend needs this
    STRIPE_WEBHOOK_SECRET: str = "whsec_test_default"  # Webhook signature verification
    STRIPE_PREMIUM_MONTHLY_PRICE_ID: str = ""  # Set in Stripe dashboard
    STRIPE_PREMIUM_YEARLY_PRICE_ID: str = ""  # Set in Stripe dashboard
    STRIPE_PRO_MONTHLY_PRICE_ID: str = ""  # Set in Stripe dashboard
    STRIPE_PRO_YEARLY_PRICE_ID: str = ""  # Set in Stripe dashboard

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
