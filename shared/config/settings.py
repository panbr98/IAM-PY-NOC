from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOCTRIX_",
        env_file=".env",
        extra="ignore",
    )

    product_name: str = "Noctrix"
    api_host: str = "127.0.0.1"
    api_port: int = 8787
    api_base_path: str = "/api/v1"
    environment: str = "demo"
    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{Path('noctrix_demo.db').resolve()}"
    )
    jwt_secret: str = "change-me-in-production-32-byte-key"
    jwt_algorithm: str = "HS256"
    token_expiry_minutes: int = 120
    company_name: str = "Example Company"
    server_fingerprint: str = "DEMO-FINGERPRINT"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
