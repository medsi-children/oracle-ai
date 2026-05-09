from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Oracle AI"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://oracle:oracle@localhost:5432/oracle_ai"
    sync_database_url: str = "postgresql+psycopg://oracle:oracle@localhost:5432/oracle_ai"

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-oss-120b:free"

    admin_telegram_username: str = "medsi_children"
    admin_telegram_ids: str = "7659888703"
    public_webapp_url: str = "http://localhost:8000/app/shop"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
