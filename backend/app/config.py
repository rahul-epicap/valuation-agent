from pathlib import Path

from pydantic_settings import BaseSettings

# Default SQLite path: backend/valuation.db
_DEFAULT_DB = "sqlite+aiosqlite:///" + str(
    Path(__file__).resolve().parent.parent / "valuation.db"
)


class Settings(BaseSettings):
    DATABASE_URL: str = _DEFAULT_DB

    # TurboPuffer vector search
    TURBOPUFFER_API_KEY: str = ""
    TURBOPUFFER_NAMESPACE: str = "valuation-descriptions"

    # Voyage AI embeddings
    VOYAGEAI_API_KEY: str = ""
    VOYAGEAI_MODEL: str = "voyage-3"

    @property
    def sync_database_url(self) -> str:
        """Return a synchronous database URL derived from the async one."""
        url = self.DATABASE_URL
        if "asyncpg" in url:
            return url.replace("asyncpg", "psycopg2")
        if "aiosqlite" in url:
            return url.replace("aiosqlite", "pysqlite")
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
