from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://rahulkishore@localhost:5432/valuation"

    @property
    def sync_database_url(self) -> str:
        """Return a synchronous database URL (psycopg2) derived from the async one."""
        return self.DATABASE_URL.replace("asyncpg", "psycopg2")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
