from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://legis:legis_dev@localhost:5432/legis"
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    congress_api_key: str = ""
    openstates_api_key: str = ""

    # API security
    api_key: str = ""  # Required in production; empty = dev mode (no auth)
    cors_origins: str = "http://localhost:3000"  # Comma-separated allowed origins

    # LLM defaults
    summary_model: str = "claude-sonnet-4-6"
    classify_model: str = "claude-haiku-4-5"

    # Search
    bm25_max_corpus: int = 100_000  # Max bills to load into BM25 index
    bm25_stream_batch: int = 5000  # Rows per streaming batch during BM25 build

    # Ingestion
    govinfo_base_url: str = "https://www.govinfo.gov"
    openstates_api_url: str = "https://v3.openstates.org"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
