"""Domain entities and dataclasses for Follow-the-Green Leaders."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Region(BaseModel):
    id: str  # e.g. "ap-south-1"
    name: str  # e.g. "Mumbai"
    location: str  # e.g. "Asia Pacific (Mumbai)"
    carbon_intensity_g_per_kwh: float  # e.g. 600.0
    electricity_price_usd_per_kwh: Optional[float] = None  # e.g. 0.095
    base_write_latency_ms: float  # e.g. 25.0
    is_healthy: bool = True
    is_leader: bool = False
    replica_count: int = 1
    current_tps: float = 0.0
    energy_mix: str = "Grid Average (Coal + Solar)"
    data_source_label: str = "Simulated Grid Model"
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkloadConfig(BaseModel):
    id: str  # "CHECKOUT" or "BACKGROUND_ANALYTICS"
    name: str
    description: str
    tps: float  # Transactions per second
    assumed_kwh_per_tx: float = 0.000008  # ~8 mWh per typical distributed SQL read/write
    max_p99_latency_ms: float  # Strict budget e.g. 40ms for Checkout, 80ms for Analytics
    priority: str = "PERFORMANCE_FIRST"  # or "CARBON_FLEXIBLE"


class CarbonEstimate(BaseModel):
    tx_count_per_hour: float
    total_energy_kwh_per_hour: float
    source_intensity_g_per_kwh: float
    target_intensity_g_per_kwh: float
    source_emissions_g_per_hour: float
    target_emissions_g_per_hour: float
    reduction_g_per_hour: float
    reduction_percentage: float
    assumed_kwh_per_tx: float
    assumptions_note: str = (
        "Model covers estimated database server compute and storage energy only; "
        "does not include external WAN network transit. Energy-per-transaction is an assumed heuristic."
    )


class OptimizationDecision(BaseModel):
    id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    workload_id: str
    workload_name: str
    current_region_id: str
    current_region_name: str
    target_region_id: str
    target_region_name: str
    current_carbon_intensity: float
    target_carbon_intensity: float
    current_emissions_g_per_hr: float
    target_emissions_g_per_hr: float
    carbon_reduction_g_per_hr: float
    carbon_reduction_pct: float
    current_p99_latency_ms: float
    target_p99_latency_ms: float
    latency_delta_ms: float
    latency_budget_ms: float
    status: str  # RECOMMENDED, APPROVED, REJECTED, BLOCKED BY LATENCY, BLOCKED BY HEALTH, BLOCKED BY COOLDOWN, NO ACTION NEEDED
    explanation: str
    historical_warning: Optional[str] = None
    is_simulated: bool = True
    is_dry_run: bool = False
    cost_delta_usd_per_hr: Optional[float] = None
    operator_action_at: Optional[str] = None
    rejection_reason: Optional[str] = None

    # Meko Context & Gemini AI Intelligence Fields
    ai_model: Optional[str] = "Gemini 1.5 Flash (Meko Grounded)"
    ai_confidence_score: Optional[float] = 0.95
    ai_reasoning_steps: Optional[List[str]] = None
    peak_hour_analysis: Optional[str] = None
    rollback_plan: Optional[str] = None
    meko_context_summary: Optional[str] = None


class RegionalPeakSchedule(BaseModel):
    region_id: str
    name: str
    timezone_label: str
    utc_offset_hours: float
    peak_traffic_window: str
    is_peak_now: bool
    local_time_display: str
    traffic_surge_factor: float
    carbon_surge_window: str
    grid_condition: str  # e.g. "CLEAN_RENEWABLE_WINDOW", "DIRTY_FOSSIL_PEAK", "OFF_PEAK_BASELOAD"


class RegionalTelemetryStatus(BaseModel):
    region_id: str
    name: str
    is_healthy: bool
    is_leader: bool
    base_write_latency_ms: float
    carbon_intensity_now: float
    carbon_intensity_in_4h: float
    carbon_trend: str  # FALLING_CLEANER, RISING_DIRTIER, STABLE
    local_time: str
    is_peak_traffic: bool
    peak_phase: str
    traffic_surge_factor: float


class MekoContextDossier(BaseModel):
    context_id: str
    generated_at: str
    workload_id: str
    workload_name: str
    workload_priority: str
    max_p99_latency_budget_ms: float
    current_tps: float
    current_leader_id: str
    current_leader_name: str
    regional_telemetry: List[RegionalTelemetryStatus]
    historical_warnings: List[str]
    candidate_options: List[Dict[str, Any]]
    context_prompt_for_ai: str


class GeminiDecisionOutput(BaseModel):
    decision: str  # RECOMMEND_MIGRATION, MAINTAIN_PLACEMENT, BLOCKED_BY_SLA, BLOCKED_BY_COOLDOWN
    target_region_id: str
    target_region_name: str
    confidence_score: float
    reasoning_steps: List[str]
    peak_hour_impact_assessment: str
    carbon_benefit_assessment: str
    rollback_plan: str
    ai_model: str

