from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    builtwith_api_key: Optional[str] = None

    # Real-data pipeline keys
    firecrawl_api_key: str = ""
    openrouter_api_key: str = ""

    # Valuation assumption defaults (configurable, shown in UI)
    valuation_ticket_size: int = 385          # Average HVAC ticket size in USD
    valuation_jobs_per_review: int = 8        # Estimated jobs per Google review
    valuation_ebitda_margin: float = 0.20     # HVAC EBITDA margin assumption
    valuation_multiple_low: float = 3.5       # Acquisition multiple low end
    valuation_multiple_high: float = 5.5      # Acquisition multiple high end

    # Council deliberation settings
    council_models: List[str] = ["anthropic/claude-sonnet-4-5", "openai/gpt-4o-mini", "google/gemini-flash-1.5"]
    council_chairman: str = "anthropic/claude-sonnet-4-5"
    council_min_conviction: int = 60      # Gate: skip council below this score
    council_min_signals: int = 4          # Gate: skip council if fewer non-null content signals

    # Database
    database_url: str = "sqlite+aiosqlite:///./hvac_intel.db"

    # App
    app_secret_key: str = "hvac-intel-secret-change-in-prod"
    debug: bool = False
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Rate Limiting (ms between calls)
    enrichment_delay_ms: int = 300
    claude_api_delay_ms: int = 1000

    # Processing
    batch_size: int = 5
    max_companies_per_run: int = 1000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
