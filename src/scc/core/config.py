from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "sqlite+pysqlite:///./scc.db"
    redis_url: str = "redis://localhost:6379/0"
    youtube_api_key: str | None = None
    telegram_bot_token: str | None = None
    tz: str = "Europe/Moscow"
    daily_brief_time: str = "10:00"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
