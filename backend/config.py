from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # API Keys
    google_places_api_key: str = ""
    anthropic_api_key: str = ""
    builtwith_api_key: Optional[str] = None

    # Database
    database_url: str = "sqlite+aiosqlite:///./hvac_intel.db"

    # App
    app_secret_key: str = "hvac-intel-secret-change-in-prod"
    debug: bool = False
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Rate Limiting (ms between calls)
    google_api_delay_ms: int = 200
    enrichment_delay_ms: int = 300
    claude_api_delay_ms: int = 1000

    # Processing
    batch_size: int = 5
    max_companies_per_run: int = 1000

    # Demo mode – generates synthetic data when no API keys configured
    use_mock_data: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
