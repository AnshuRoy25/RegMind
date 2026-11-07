from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    user: str = Field(validation_alias="USER")
    password: str = Field(validation_alias="PASSWORD")
    host: str = Field(validation_alias="HOST")
    port: int = Field(default=5432, validation_alias="PORT")
    db_name: str = Field(default="postgres", validation_alias="DBNAME")

    app_name: str = "RegMind"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    secret_key: str = "dev-secret-change-me"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    storage_dir: Path = BACKEND_DIR / "storage"
    max_upload_mb: int = 50

    google_api_key: str = ""
    google_genai_use_vertexai: str = "FALSE"
    gemini_model: str = "gemini-3.5-flash-lite"
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768

    use_fake_services: bool = False

    github_token: str = ""
    github_repo: str = ""
    demo_diffs_dir: str = ""

    switch_url: str = ""
    switch_email: str = ""
    switch_password: str = ""
    switch_workspace_name: str = "RegMind"
    switch_tenant_id: str = ""
    switch_registration_key: str = ""
    switch_autoconnect: bool = False
    switch_request_timeout: float = 30.0
    switch_verify_tls: bool = True

    discord_application_id: str = ""
    discord_bot_token: str = ""
    discord_public_key: str = ""

    default_assignee: str = "engineer"
    adk_sessions_db_url: str = ""
    default_organization_name: str = "RegMind"
    default_organization_slug: str = "regmind"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{quote_plus(self.user)}:"
            f"{quote_plus(self.password)}@{self.host}:{self.port}/{self.db_name}"
        )

    @property
    def switch_gateway_url(self) -> str:
        return self.switch_url.rstrip("/") + "/gateway"

    @property
    def switch_api_url(self) -> str:
        return self.switch_url.rstrip("/")

    @property
    def switch_ws_url(self) -> str:
        base = self.switch_url.rstrip("/")
        if base.startswith("https://"):
            return "wss://" + base[len("https://"):]
        if base.startswith("http://"):
            return "ws://" + base[len("http://"):]
        return base

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

settings.storage_dir.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", settings.google_genai_use_vertexai)
