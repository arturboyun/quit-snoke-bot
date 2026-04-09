from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "BOT_"}

    token: str
    db_url: str = "postgresql+asyncpg://bot:bot@localhost:5432/quit_smoke"
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()  # type: ignore[call-arg]
