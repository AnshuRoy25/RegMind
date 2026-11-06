import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    google_api_key: str = ""
    google_genai_use_vertexai: str = "FALSE"
    gemini_model: str = "gemini-2.5-flash"

    # Data
    database_url: str = ""
    use_fake_services: bool = True

    # Integrations
    github_token: str = ""
    github_repo: str = ""          # e.g. "team-square/regmind-demo-service"
    switch_url: str = ""

    # Agents
    default_assignee: str = "engineer"   # chat name used when nobody is named
    demo_diffs_dir: str = ""             # e.g. "samples/diffs" for offline auditor demos
    adk_sessions_db_url: str = ""        # optional: persist ADK sessions (sqlite/postgres URL)


settings = Settings()

# ADK reads these straight from the environment, so make sure they are there.
os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", settings.google_genai_use_vertexai)
