"""Integration tests for the REST API endpoint logic and lifecycle workflows."""
import pytest
from app.api.endpoints import (
    get_health,
    get_regions,
    get_topology,
    get_workloads,
    get_kpi_summary,
    get_metrics_history,
    run_optimization,
    approve_recommendation,
    reject_recommendation,
    get_memory_history,
    get_settings,
    update_settings,
    reset_simulation,
    db_service,
    memory_service,
)
from app.schemas.dto import (
    OptimizationRunRequest,
    ApproveRequest,
    RejectRequest,
    SettingsUpdateRequest,
)
from app.core.config import settings


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure clean database and memory state before each test."""
    db_service.reset_simulation()
    memory_service.clear_history()
    settings.cooldown_seconds = 0  # Disable cooldown during unit testing


def test_health_endpoint():
    """Verify health endpoint structure, mode reporting, and data source disclosure."""
    res = get_health()
    assert res.status == "HEALTHY"
    assert res.operating_mode in ["SIMULATION", "LIVE"]
    assert "SIMULATED CARBON DATA" in res.carbon_data_label
    assert res.memory_status["provider"] == "MEKO_COMPATIBLE_LOCAL_FALLBACK"


def test_regions_endpoint():
    """Verify regions returned include Mumbai, Frankfurt, Virginia with correct fields."""
    regions = get_regions()
    assert len(regions) >= 3
    names = [r.name for r in regions]
    assert "Mumbai" in names
    assert "Frankfurt" in names
    assert "Virginia" in names
    mumbai = next(r for r in regions if r.name == "Mumbai")
    assert mumbai.is_leader is True


def test_topology_endpoint():
    """Verify topology exposes nodes, links, and simulated indicator."""
    topo = get_topology()
    assert "regions" in topo
    assert "connections" in topo
    assert topo["is_simulated"] is True
    assert len(topo["connections"]) >= 3


def test_workloads_endpoint():
    """Verify checkout and background analytics profiles exist."""
    workloads = get_workloads()
    ids = [w.id for w in workloads]
    assert "CHECKOUT" in ids
    assert "BACKGROUND_ANALYTICS" in ids


def test_kpi_summary():
    """Verify KPI aggregation calculations."""
    kpi = get_kpi_summary()
    assert kpi.current_leader_region == "Mumbai"
    assert kpi.hourly_emissions_gco2 > 0
    assert kpi.current_p99_latency_ms == 25.0
    assert kpi.is_simulated is True


def test_metrics_history():
    """Verify time-series history generator."""
    history = get_metrics_history(time_window="1h")
    assert len(history) > 0
    first = history[0]
    assert "mumbai_ci" in first
    assert "frankfurt_ci" in first
    assert "virginia_ci" in first
    assert "baseline_emissions_g" in first


def test_optimization_and_approval_workflow():
    """Full optimization lifecycle: run, verify recommendation, approve, verify topology change."""
    # Run optimization for background analytics (tolerant budget)
    req = OptimizationRunRequest(workload_id="BACKGROUND_ANALYTICS", max_latency_ms=80.0)
    decision = run_optimization(req)

    assert decision.status == "RECOMMENDED"
    target_id = decision.target_region_id
    assert target_id in ["eu-central-1", "us-east-1"]

    # Approve recommendation
    app_req = ApproveRequest(operator_confirmed=True)
    result = approve_recommendation(decision.id, app_req)
    assert result["success"] is True
    assert result["decision"].status == "APPROVED"

    # Verify that the simulated leader moved to the target region!
    current_regions = get_regions()
    new_leader = next(r for r in current_regions if r.id == target_id)
    assert new_leader.is_leader is True


def test_optimization_and_rejection_workflow():
    """Full optimization lifecycle: run, reject with explanation, verify memory recorded."""
    req = OptimizationRunRequest(workload_id="CHECKOUT")
    decision = run_optimization(req)

    rej_req = RejectRequest(reason="Performance SLA too risky during evening peak.")
    res = reject_recommendation(decision.id, rej_req)
    assert res["success"] is True
    assert res["decision"].status == "REJECTED"
    assert res["decision"].rejection_reason == "Performance SLA too risky during evening peak."

    # Verify rejection persists in history
    history = get_memory_history(status="REJECTED")
    assert len(history) >= 1
    assert history[0].id == decision.id


def test_settings_update_and_validation():
    """Verify non-secret settings modification."""
    update_req = SettingsUpdateRequest(cooldown_seconds=180, cost_aware_enabled=True)
    res = update_settings(update_req)
    assert res["success"] is True
    assert res["settings"]["cooldown_seconds"] == 180
    assert res["settings"]["cost_aware_enabled"] is True


def test_simulation_reset():
    """Verify simulation reset restores leader to Mumbai."""
    # First move leader
    req = OptimizationRunRequest(workload_id="CHECKOUT")
    d = run_optimization(req)
    approve_recommendation(d.id, ApproveRequest(operator_confirmed=True))

    # Reset
    reset_res = reset_simulation()
    assert reset_res["success"] is True

    # Confirm Mumbai is leader again
    regions = get_regions()
    mumbai = next(r for r in regions if r.id == "ap-south-1")
    assert mumbai.is_leader is True


def test_approve_nonexistent_recommendation_raises_404():
    """Approving an unknown recommendation ID raises 404 HTTPException."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        approve_recommendation("non-existent-uuid", ApproveRequest(operator_confirmed=True))
    assert exc_info.value.status_code == 404


def test_reject_nonexistent_recommendation_raises_404():
    """Rejecting an unknown recommendation ID raises 404 HTTPException."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        reject_recommendation("non-existent-uuid", RejectRequest(reason="Testing not found"))
    assert exc_info.value.status_code == 404


def test_invalid_settings_raise_400():
    """Passing invalid mode or workload raises 400 HTTPException."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        update_settings(SettingsUpdateRequest(operating_mode="INVALID_MODE"))
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        update_settings(SettingsUpdateRequest(active_workload="INVALID_WORKLOAD"))
    assert exc_info.value.status_code == 400

