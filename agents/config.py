"""Central configuration for the agent pipeline."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI models
    model_crawler: str = "gpt-4o-mini"
    model_seo: str = "gpt-4o-mini"
    model_content: str = "gpt-4o"
    model_design: str = "gpt-4o-mini"
    model_email: str = "gpt-4o-mini"
    model_qc: str = "gpt-4o"

    # Groq fallback model (cost ~3-10x cheaper)
    groq_model_content: str = "llama-4-scout-17b-16e-instruct"
    use_groq_for_content: bool = True

    # API keys
    openai_api_key: str = ""
    groq_api_key: str = ""
    google_maps_api_key: str = ""
    pagespeed_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://localhost/ai_web_gen"
    redis_url: str = "redis://localhost:6379/0"

    # Cloudflare
    cf_account_id: str = ""
    cf_r2_access_key: str = ""
    cf_r2_secret_key: str = ""
    cf_r2_bucket: str = "demo-sites"
    demo_base_domain: str = "demo.yourplatform.pl"

    # Pipeline limits
    max_qc_retries: int = 3
    batch_size: int = 50  # Batch API batch size
    max_concurrent_agents: int = 10

    log_level: str = "INFO"


settings = Settings()
