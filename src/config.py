from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://legis:legis_dev@localhost:5432/legis"
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    congress_api_key: str = ""
    openstates_api_key: str = ""

    # LLM defaults
    summary_model: str = "claude-sonnet-4-6"
    classify_model: str = "claude-haiku-4-5"

    # Ingestion
    govinfo_base_url: str = "https://www.govinfo.gov"
    openstates_api_url: str = "https://v3.openstates.org"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
