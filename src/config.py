from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://legis:legis_dev@localhost:5432/legis"
    llm_provider: str = "claude-sdk"  # openai | anthropic | claude-sdk
    agentic_provider: str = "codex-local"  # codex-local | empty = use llm_provider path
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_auth_token: str = ""  # OAuth token (subscription auth via claude login)
    voyage_api_key: str = ""
    congress_api_key: str = ""
    openstates_api_key: str = ""
    legiscan_api_key: str = ""

    # API security
    api_key: str = ""  # Required in production; empty = dev mode (no auth)
    cors_origins: str = "http://localhost:3000"  # Comma-separated allowed origins
    webhook_encryption_key: str = ""  # Fernet key for encrypting webhook secrets at rest

    # LLM defaults
    summary_model: str = "gpt-4o-mini"
    classify_model: str = "gpt-4o-mini"

    # Search
    bm25_max_corpus: int = 100_000  # Max bills to load into BM25 index
    bm25_stream_batch: int = 5000  # Rows per streaming batch during BM25 build
    prewarm_bm25: bool = True  # Build BM25 index on startup (set False in CI/test)

    # GovInfo
    govinfo_base_url: str = "https://www.govinfo.gov"
    govinfo_api_url: str = "https://api.govinfo.gov"
    govinfo_api_key: str = ""

    # Ingestion
    openstates_api_url: str = "https://v3.openstates.org"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
