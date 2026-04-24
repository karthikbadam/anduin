from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://redis:6379/0"
    postgres_dsn: str = "postgresql://anduin:anduin-dev@postgres:5432/anduin"
    service_name: str = "query-api"
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
