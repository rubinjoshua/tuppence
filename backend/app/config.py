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

    # Apple (Sign In + StoreKit 2 / App Store Server API)
    # Bundle ID is the iOS app bundle ID; both Apple Sign In token audience checks
    # and StoreKit signed-transaction verification compare against this value.
    APPLE_BUNDLE_ID: str = "com.joshuarubin.tuppence"
    APPLE_APP_APPLE_ID: int = 0  # Numeric App Store app ID (from App Store Connect)
    APPLE_ISSUER_ID: str = ""  # UUID from ASC > Users and Access > Keys > In-App Purchase
    APPLE_KEY_ID: str = ""  # 10-char key ID from the same page
    APPLE_PRIVATE_KEY: str = ""  # Multi-line PEM contents of the .p8 file
    APPLE_ENVIRONMENT: str = "Sandbox"  # "Sandbox" or "Production"

    # Subscription product IDs (must match App Store Connect exactly).
    APPLE_PRODUCT_ID_PREMIUM_MONTHLY: str = "com.joshuarubin.tuppence.premium.monthly"
    APPLE_PRODUCT_ID_PREMIUM_YEARLY: str = "com.joshuarubin.tuppence.premium.yearly"
    APPLE_PRODUCT_ID_PRO_MONTHLY: str = "com.joshuarubin.tuppence.pro.monthly"
    APPLE_PRODUCT_ID_PRO_YEARLY: str = "com.joshuarubin.tuppence.pro.yearly"

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
