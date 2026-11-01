"""Data transfer objects (DTOs) and request/response schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from ..models.entities import Region, OptimizationDecision, WorkloadConfig


class HealthResponse(BaseModel):
    status: str
    operating_mode: str
    is_live_db_connected: bool
    db_status_details: Dict[str, Any]
    memory_status: Dict[str, Any]
    carbon_provider: str
    carbon_data_label: str
    app_version: str
    timestamp: str


class KPISummaryResponse(BaseModel):
    operating_mode: str
    carbon_data_label: str
    current_leader_region: str
    current_carbon_intensity_g_per_kwh: float
    current_p99_latency_ms: float
    hourly_emissions_gco2: float
    baseline_hourly_emissions_gco2: float
    carbon_reduction_pct: float
    active_workload_name: str
    eligible_regions_count: int
    total_recommendations_count: int
    approved_changes_count: int
    rejected_changes_count: int
    is_simulated: bool


class OptimizationRunRequest(BaseModel):
    workload_id: Optional[str] = None
    max_latency_ms: Optional[float] = None
    min_carbon_pct: Optional[float] = None
    dry_run: Optional[bool] = None


class ApproveRequest(BaseModel):
    operator_notes: Optional[str] = None
    operator_confirmed: bool = True


class RejectRequest(BaseModel):
    reason: Optional[str] = "Operator declined recommendation."


class SettingsUpdateRequest(BaseModel):
    operating_mode: Optional[str] = None
    max_latency_increase_ms: Optional[float] = Field(default=None, ge=1.0, le=200.0)
    min_carbon_reduction_pct: Optional[float] = Field(default=None, ge=1.0, le=90.0)
    cooldown_seconds: Optional[int] = Field(default=None, ge=10, le=3600)
    cost_aware_enabled: Optional[bool] = None
    dry_run_enabled: Optional[bool] = None
    auto_recommendations_enabled: Optional[bool] = None
    active_workload: Optional[str] = None
    carbon_provider: Optional[str] = None
