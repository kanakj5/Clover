"""Configuration and settings for Follow-the-Green Leaders."""
import os
from enum import Enum
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env if present
load_dotenv()


class OperatingMode(str, Enum):
    SIMULATION = "SIMULATION"
    LIVE = "LIVE"


class WorkloadProfileType(str, Enum):
    CHECKOUT = "CHECKOUT"
    BACKGROUND_ANALYTICS = "BACKGROUND_ANALYTICS"


class CarbonProviderType(str, Enum):
    DEMO = "DEMO"
    EXTERNAL = "EXTERNAL"


class Settings(BaseModel):
    # App
    app_name: str = "Follow-the-Green Leaders API"
    app_version: str = "1.0.0"
    operating_mode: OperatingMode = Field(
        default_factory=lambda: OperatingMode(os.getenv("OPERATING_MODE", "SIMULATION").upper())
    )

    # YugabyteDB live configuration
    yugabytedb_host: str = Field(default_factory=lambda: os.getenv("YUGABYTEDB_HOST", "localhost"))
    yugabytedb_port: int = Field(default_factory=lambda: int(os.getenv("YUGABYTEDB_PORT", "5433")))
    yugabytedb_database: str = Field(default_factory=lambda: os.getenv("YUGABYTEDB_DATABASE", "yugabyte"))
    yugabytedb_user: str = Field(default_factory=lambda: os.getenv("YUGABYTEDB_USER", "yugabyte"))
    yugabytedb_password: str = Field(default_factory=lambda: os.getenv("YUGABYTEDB_PASSWORD", ""))
    yugabytedb_sslmode: str = Field(default_factory=lambda: os.getenv("YUGABYTEDB_SSLMODE", "prefer"))
    yugabytedb_connect_timeout: int = Field(default_factory=lambda: int(os.getenv("YUGABYTEDB_CONNECT_TIMEOUT", "4")))

    # Optimization engine thresholds
    max_latency_increase_ms: float = Field(default=20.0, ge=1.0, le=200.0)
    min_carbon_reduction_pct: float = Field(default=10.0, ge=1.0, le=90.0)
    cooldown_seconds: int = Field(default=120, ge=0, le=3600)
    cost_aware_enabled: bool = False
    dry_run_enabled: bool = False
    auto_recommendations_enabled: bool = False
    active_workload: WorkloadProfileType = Field(
        default_factory=lambda: WorkloadProfileType(os.getenv("ACTIVE_WORKLOAD", "CHECKOUT"))
    )

    # Carbon data provider
    carbon_provider: CarbonProviderType = Field(
        default_factory=lambda: CarbonProviderType(os.getenv("CARBON_PROVIDER", "DEMO").upper())
    )
    carbon_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("CARBON_API_KEY"))
    carbon_api_url: Optional[str] = Field(default_factory=lambda: os.getenv("CARBON_API_URL"))
    carbon_update_interval_sec: int = 60

    # Local persistence fallback
    sqlite_db_path: str = Field(default_factory=lambda: os.getenv("SQLITE_DB_PATH", "follow_the_green.db"))

    # Meko integration
    meko_enabled: bool = Field(default_factory=lambda: os.getenv("MEKO_ENABLED", "false").lower() == "true")
    meko_api_endpoint: Optional[str] = Field(default_factory=lambda: os.getenv("MEKO_API_ENDPOINT"))
    meko_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("MEKO_API_KEY"))

    # Gemini AI Decision Engine
    gemini_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))



# Global singleton settings
settings = Settings()

