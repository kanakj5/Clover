"""REST API routes for Follow-the-Green Leaders."""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends

from ..models.entities import (
    Region,
    OptimizationDecision,
    WorkloadConfig,
    RegionalPeakSchedule,
    MekoContextDossier,
)
from ..schemas.dto import (
    HealthResponse,
    KPISummaryResponse,
    OptimizationRunRequest,
    ApproveRequest,
    RejectRequest,
    SettingsUpdateRequest,
)
from ..services.database_service import DatabaseService
from ..services.memory_service import MemoryService
from ..services.carbon_calculator import CarbonCalculator
from ..services.optimization_engine import OptimizationEngine
from ..services.carbon_provider import DemoCarbonProvider, ExternalCarbonProvider
from ..services.meko_context_tool import MekoContextTool
from ..services.gemini_ai_service import GeminiAIService
from ..adapters.meko_adapter import MekoMemoryAdapter
from ..simulation.seed_data import WORKLOAD_PROFILES, generate_time_series_data
from ..core.config import settings, OperatingMode, WorkloadProfileType, CarbonProviderType

router = APIRouter()

# Global service singletons
db_service = DatabaseService()
memory_service = MemoryService()
meko_context_tool = MekoContextTool(memory_service)
gemini_ai_service = GeminiAIService()
meko_adapter = MekoMemoryAdapter(memory_service)
optimization_engine = OptimizationEngine(
    db_service,
    memory_service,
    meko_context_tool=meko_context_tool,
    gemini_ai_service=gemini_ai_service,
)
demo_carbon = DemoCarbonProvider()
ext_carbon = ExternalCarbonProvider()



@router.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint exposing operating mode, cluster connectivity, and provider provenance."""
    db_status = db_service.get_connection_status()
    mem_status = meko_adapter.get_status_info()
    return HealthResponse(
        status="HEALTHY",
        operating_mode=settings.operating_mode.value,
        is_live_db_connected=db_status.get("is_connected", False),
        db_status_details=db_status,
        memory_status=mem_status,
        carbon_provider=settings.carbon_provider.value,
        carbon_data_label=DemoCarbonProvider.DATA_SOURCE_NOTICE if settings.carbon_provider == CarbonProviderType.DEMO else "External Grid Provider",
        app_version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/regions", response_model=List[Region])
def get_regions():
    """Return all regions with current simulated or live metrics."""
    return db_service.get_topology()


@router.get("/topology")
def get_topology():
    """Return visual topology nodes and inter-region latency matrix."""
    regions = db_service.get_topology()
    current_leader = db_service.get_current_leader_region()
    return {
        "operating_mode": settings.operating_mode.value,
        "is_simulated": settings.operating_mode != OperatingMode.LIVE,
        "topology_label": "SIMULATED YUGABYTEDB TOPOLOGY" if settings.operating_mode != OperatingMode.LIVE else "LIVE YUGABYTEDB TOPOLOGY",
        "current_leader_id": current_leader.id,
        "regions": regions,
        "connections": [
            {"from": "ap-south-1", "to": "eu-central-1", "latency_ms": 110, "type": "WAN Inter-region"},
            {"from": "ap-south-1", "to": "us-east-1", "latency_ms": 190, "type": "WAN Inter-region"},
            {"from": "eu-central-1", "to": "us-east-1", "latency_ms": 85, "type": "WAN Inter-region"},
        ]
    }


@router.get("/workloads", response_model=List[WorkloadConfig])
def get_workloads():
    """List available workload profiles (Checkout vs Background Analytics)."""
    return list(WORKLOAD_PROFILES.values())


@router.get("/metrics/summary", response_model=KPISummaryResponse)
def get_kpi_summary():
    """Dashboard KPIs aggregating emissions, latency, and placement history."""
    leader = db_service.get_current_leader_region()
    workload = WORKLOAD_PROFILES.get(settings.active_workload.value, WORKLOAD_PROFILES["CHECKOUT"])
    topology = db_service.get_topology()

    # Calculate hourly emissions for current leader
    current_calc = CarbonCalculator.compare_regions(
        source_carbon_intensity=leader.carbon_intensity_g_per_kwh,
        target_carbon_intensity=leader.carbon_intensity_g_per_kwh,
        tps=workload.tps,
        duration_seconds=3600.0,
        energy_kwh_per_tx=workload.assumed_kwh_per_tx,
    )

    # Baseline: assume fixed placement in Mumbai (ap-south-1)
    mumbai = next((r for r in topology if r.id == "ap-south-1"), leader)
    baseline_calc = CarbonCalculator.compare_regions(
        source_carbon_intensity=mumbai.carbon_intensity_g_per_kwh,
        target_carbon_intensity=mumbai.carbon_intensity_g_per_kwh,
        tps=workload.tps,
        duration_seconds=3600.0,
        energy_kwh_per_tx=workload.assumed_kwh_per_tx,
    )

    reduction_pct = 0.0
    if baseline_calc.source_emissions_g_per_hour > 0:
        saved = baseline_calc.source_emissions_g_per_hour - current_calc.source_emissions_g_per_hour
        reduction_pct = round((saved / baseline_calc.source_emissions_g_per_hour) * 100.0, 1)

    # Fetch decision statistics
    all_decisions = memory_service.get_history(limit=500)
    approved = [d for d in all_decisions if d.status == "APPROVED"]
    rejected = [d for d in all_decisions if d.status == "REJECTED"]

    return KPISummaryResponse(
        operating_mode=settings.operating_mode.value,
        carbon_data_label=DemoCarbonProvider.DATA_SOURCE_NOTICE,
        current_leader_region=leader.name,
        current_carbon_intensity_g_per_kwh=leader.carbon_intensity_g_per_kwh,
        current_p99_latency_ms=leader.base_write_latency_ms,
        hourly_emissions_gco2=round(current_calc.source_emissions_g_per_hour, 1),
        baseline_hourly_emissions_gco2=round(baseline_calc.source_emissions_g_per_hour, 1),
        carbon_reduction_pct=reduction_pct,
        active_workload_name=workload.name,
        eligible_regions_count=len([r for r in topology if r.is_healthy]),
        total_recommendations_count=len(all_decisions),
        approved_changes_count=len(approved),
        rejected_changes_count=len(rejected),
        is_simulated=settings.operating_mode != OperatingMode.LIVE,
    )


@router.get("/metrics/history")
def get_metrics_history(time_window: str = Query("1h", pattern="^(15m|1h|24h)$")):
    """Return historical time-series data for carbon emissions and p99 latency."""
    return generate_time_series_data(time_window=time_window)


@router.post("/optimization/run", response_model=OptimizationDecision)
def run_optimization(req: OptimizationRunRequest):
    """Trigger the carbon-aware optimization engine to evaluate leader placement."""
    decision = optimization_engine.run_optimization(
        workload_id=req.workload_id,
        max_latency_ms=req.max_latency_ms,
        min_carbon_pct=req.min_carbon_pct,
        dry_run=req.dry_run,
    )
    return decision


@router.get("/optimization/recommendations", response_model=List[OptimizationDecision])
def get_recommendations(limit: int = 10):
    """Retrieve recent optimization decisions."""
    return memory_service.get_history(limit=limit)


@router.post("/optimization/recommendations/{decision_id}/approve")
def approve_recommendation(decision_id: str, req: ApproveRequest):
    """Approve a proposed recommendation.

    In simulation mode: moves simulated topology leader.
    In live mode: executes validated tablespace placement after verifying operator confirmation.
    """
    decision = memory_service.get_decision_by_id(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision recommendation not found.")

    if decision.status not in ["RECOMMENDED", "NO ACTION NEEDED"]:
        raise HTTPException(status_code=400, detail=f"Cannot approve decision with status '{decision.status}'.")

    # Execute placement change
    migration_result = db_service.update_leader_placement(
        target_region_id=decision.target_region_id,
        is_dry_run=decision.is_dry_run,
        operator_confirmed=req.operator_confirmed,
    )

    if not migration_result.get("success", False):
        raise HTTPException(status_code=500, detail=migration_result.get("error", "Placement execution failed."))

    # Record outcome in persistent memory
    updated = memory_service.record_outcome(
        decision_id=decision_id,
        new_status="APPROVED",
        actual_latency_ms=decision.target_p99_latency_ms,
    )

    return {
        "success": True,
        "decision": updated,
        "migration_details": migration_result,
        "current_topology": db_service.get_topology(),
    }


@router.post("/optimization/recommendations/{decision_id}/reject")
def reject_recommendation(decision_id: str, req: RejectRequest):
    """Reject recommendation and record reason in persistent memory for future warnings."""
    decision = memory_service.get_decision_by_id(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision recommendation not found.")

    updated = memory_service.record_outcome(
        decision_id=decision_id,
        new_status="REJECTED",
        rejection_reason=req.reason,
    )

    return {
        "success": True,
        "decision": updated,
        "message": f"Recommendation rejected and stored in memory: {req.reason}",
    }


@router.get("/memory/history", response_model=List[OptimizationDecision])
def get_memory_history(
    limit: int = 50,
    workload_id: Optional[str] = None,
    region_id: Optional[str] = None,
    status: Optional[str] = None,
):
    """Persistent decision memory table with filtering."""
    return memory_service.get_history(limit=limit, workload_id=workload_id, region_id=region_id, status=status)


@router.get("/memory/similar", response_model=List[OptimizationDecision])
def get_similar_decisions(workload_id: str, target_region_id: str, limit: int = 5):
    """Retrieve similar historical decisions to inform future recommendations."""
    return memory_service.retrieve_similar_decisions(workload_id=workload_id, target_region_id=target_region_id, limit=limit)


@router.get("/memory/failures")
def get_failure_summary(workload_id: str, target_region_id: str):
    """Check if historical records exist warning against a particular workload/region placement."""
    warning = memory_service.summarize_historical_failures(workload_id, target_region_id)
    return {"workload_id": workload_id, "target_region_id": target_region_id, "warning": warning}


@router.get("/meko/peaks", response_model=List[RegionalPeakSchedule])
def get_meko_regional_peaks():
    """Retrieve regional traffic peak hours, diurnal carbon windows, and local clock status."""
    return meko_context_tool.get_peak_schedules()


@router.get("/meko/context", response_model=MekoContextDossier)
def get_meko_context_dossier(workload_id: Optional[str] = None):
    """Retrieve full Meko Context Dossier assembled for Gemini AI."""
    w_id = workload_id or settings.active_workload.value
    workload = WORKLOAD_PROFILES.get(w_id, WORKLOAD_PROFILES["CHECKOUT"])
    topology = db_service.get_topology()
    leader = db_service.get_current_leader_region()

    last_movement = memory_service.get_last_movement_timestamp()
    cooldown_sec = 0
    if last_movement:
        if last_movement.tzinfo is None:
            last_movement = last_movement.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_movement).total_seconds()
        if elapsed < settings.cooldown_seconds:
            cooldown_sec = int(settings.cooldown_seconds - elapsed)

    return meko_context_tool.assemble_context_for_gemini(
        workload=workload,
        topology=topology,
        current_leader=leader,
        latency_budget_ms=workload.max_p99_latency_ms,
        min_carbon_pct=settings.min_carbon_reduction_pct,
        cooldown_remaining_sec=cooldown_sec,
    )


@router.get("/settings")

def get_settings():
    """Get non-secret optimization and system configuration."""
    return {
        "operating_mode": settings.operating_mode.value,
        "max_latency_increase_ms": settings.max_latency_increase_ms,
        "min_carbon_reduction_pct": settings.min_carbon_reduction_pct,
        "cooldown_seconds": settings.cooldown_seconds,
        "cost_aware_enabled": settings.cost_aware_enabled,
        "dry_run_enabled": settings.dry_run_enabled,
        "auto_recommendations_enabled": settings.auto_recommendations_enabled,
        "active_workload": settings.active_workload.value,
        "carbon_provider": settings.carbon_provider.value,
        "carbon_update_interval_sec": settings.carbon_update_interval_sec,
        "yugabytedb_host": settings.yugabytedb_host,
        "yugabytedb_port": settings.yugabytedb_port,
        "yugabytedb_database": settings.yugabytedb_database,
        "meko_enabled": settings.meko_enabled,
    }


@router.patch("/settings")
def update_settings(req: SettingsUpdateRequest):
    """Update optimization parameters and operating mode."""
    if req.operating_mode is not None:
        try:
            settings.operating_mode = OperatingMode(req.operating_mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid operating mode: {req.operating_mode}")

    if req.max_latency_increase_ms is not None:
        settings.max_latency_increase_ms = req.max_latency_increase_ms
    if req.min_carbon_reduction_pct is not None:
        settings.min_carbon_reduction_pct = req.min_carbon_reduction_pct
    if req.cooldown_seconds is not None:
        settings.cooldown_seconds = req.cooldown_seconds
    if req.cost_aware_enabled is not None:
        settings.cost_aware_enabled = req.cost_aware_enabled
    if req.dry_run_enabled is not None:
        settings.dry_run_enabled = req.dry_run_enabled
    if req.auto_recommendations_enabled is not None:
        settings.auto_recommendations_enabled = req.auto_recommendations_enabled
    if req.active_workload is not None:
        try:
            settings.active_workload = WorkloadProfileType(req.active_workload)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid workload profile: {req.active_workload}")
    if req.carbon_provider is not None:
        try:
            settings.carbon_provider = CarbonProviderType(req.carbon_provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid carbon provider: {req.carbon_provider}")

    return {"success": True, "settings": get_settings()}


@router.post("/simulation/reset")
def reset_simulation():
    """Reset simulated topology (leader to Mumbai) and reset cooldown/history."""
    db_service.reset_simulation()
    memory_service.clear_history()
    return {
        "success": True,
        "message": "Simulation topology reset to default (Mumbai leader) and history cleared.",
        "topology": db_service.get_topology(),
    }
