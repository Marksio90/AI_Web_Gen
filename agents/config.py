"""
Central configuration for the advanced multi-agent platform.

Extends base settings with:
- Multi-model routing configuration
- Swarm intelligence parameters
- Evolutionary algorithm settings
- Memory system configuration
- Event system settings
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # -----------------------------------------------------------------------
    # Model Configuration — per-agent defaults
    # -----------------------------------------------------------------------
    model_crawler: str = "gpt-4o-mini"
    model_seo: str = "gpt-4o-mini"
    model_content: str = "gpt-4o"
    model_design: str = "gpt-4o-mini"
    model_email: str = "gpt-4o-mini"
    model_qc: str = "gpt-4o"
    model_meta_orchestrator: str = "gpt-4o"
    model_competitive_intel: str = "gpt-4o-mini"

    # Groq fallback model (cost ~3-10x cheaper for content generation)
    groq_model_content: str = "llama-4-scout-17b-16e-instruct"
    use_groq_for_content: bool = True

    # -----------------------------------------------------------------------
    # Multi-Model Router
    # -----------------------------------------------------------------------
    enable_dynamic_routing: bool = True
    default_max_cost_per_1k: float = 0.01
    default_max_latency_s: float = 15.0
    prefer_provider: str = ""  # openai, groq, or empty for auto

    # -----------------------------------------------------------------------
    # Swarm Intelligence
    # -----------------------------------------------------------------------
    enable_swarm: bool = True
    swarm_min_agents: int = 3
    swarm_quorum: float = 0.5
    swarm_default_strategy: str = "weighted_vote"
    debate_max_rounds: int = 2
    tournament_competitors: int = 3

    # -----------------------------------------------------------------------
    # Evolutionary Optimization
    # -----------------------------------------------------------------------
    enable_evolution: bool = True
    evolution_population_size: int = 4
    evolution_max_generations: int = 3
    evolution_mutation_rate: float = 0.3
    evolution_elite_count: int = 2
    evolution_convergence_threshold: float = 0.92

    # -----------------------------------------------------------------------
    # Memory & Learning
    # -----------------------------------------------------------------------
    enable_memory: bool = True
    memory_redis_db: int = 1
    memory_max_episodes: int = 5000
    memory_consolidation_interval: int = 3600  # seconds
    enable_adaptive_tuning: bool = True

    # -----------------------------------------------------------------------
    # Event System
    # -----------------------------------------------------------------------
    enable_events: bool = True
    event_redis_db: int = 2
    event_max_history: int = 10000
    enable_redis_bridge: bool = True

    # -----------------------------------------------------------------------
    # DAG Orchestrator
    # -----------------------------------------------------------------------
    dag_max_parallelism: int = 10
    dag_checkpoint_enabled: bool = True
    circuit_breaker_threshold: int = 3
    circuit_breaker_recovery_s: float = 60.0

    # -----------------------------------------------------------------------
    # API Keys
    # -----------------------------------------------------------------------
    openai_api_key: str = ""
    groq_api_key: str = ""
    google_maps_api_key: str = ""
    pagespeed_api_key: str = ""
    pexels_api_key: str = ""

    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://localhost/ai_web_gen"
    redis_url: str = "redis://localhost:6379/0"

    # -----------------------------------------------------------------------
    # Cloudflare
    # -----------------------------------------------------------------------
    cf_account_id: str = ""
    cf_r2_access_key: str = ""
    cf_r2_secret_key: str = ""
    cf_r2_bucket: str = "demo-sites"
    demo_base_domain: str = "demo.yourplatform.pl"

    # -----------------------------------------------------------------------
    # Pipeline Limits
    # -----------------------------------------------------------------------
    max_qc_retries: int = 3
    batch_size: int = 50
    max_concurrent_agents: int = 10

    # -----------------------------------------------------------------------
    # Pipeline Strategy
    # -----------------------------------------------------------------------
    default_pipeline_strategy: str = "standard"
    auto_select_strategy: bool = True  # Auto-select best strategy per business

    # -----------------------------------------------------------------------
    # Operational
    # -----------------------------------------------------------------------
    log_level: str = "INFO"
    env: str = "development"

    @property
    def memory_redis_url(self) -> str:
        base = self.redis_url.rsplit("/", 1)[0]
        return f"{base}/{self.memory_redis_db}"

    @property
    def event_redis_url(self) -> str:
        base = self.redis_url.rsplit("/", 1)[0]
        return f"{base}/{self.event_redis_db}"


settings = Settings()
