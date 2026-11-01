"""Unit tests for the Optimization Engine policy enforcement."""
import os
import pytest
from datetime import datetime, timezone
from app.services.optimization_engine import OptimizationEngine
from app.services.database_service import DatabaseService
from app.services.memory_service import MemoryService
from app.models.entities import Region, WorkloadConfig
from app.core.config import settings


@pytest.fixture
def test_env(tmp_path):
    """Isolated test environment with temporary SQLite memory DB."""
    db_file = str(tmp_path / "test_memory.db")
    memory_svc = MemoryService(db_path=db_file)
    db_svc = DatabaseService()
    db_svc.reset_simulation()
    engine = OptimizationEngine(database_service=db_svc, memory_service=memory_svc)
    return engine, db_svc, memory_svc


def test_cleaner_region_with_acceptable_latency(test_env):
    """Virginia has 35ms write latency and ~400 gCO2/kWh (vs Mumbai 600 gCO2/kWh).

    For Checkout (budget 40ms), Virginia is acceptable and should be recommended!
    """
    engine, db_svc, memory_svc = test_env
    decision = engine.run_optimization(workload_id="CHECKOUT", max_latency_ms=40.0)

    # Mumbai (600) -> Virginia (400) gives ~33% reduction and fits inside 40ms budget
    # Frankfurt (200) has 55ms latency which violates 40ms budget
    assert decision.status == "RECOMMENDED"
    assert decision.target_region_id == "us-east-1"
    assert decision.target_p99_latency_ms <= 40.0
    assert decision.carbon_reduction_pct > 0


def test_cleaner_region_with_unacceptable_latency(test_env):
    """Frankfurt is the cleanest (200 gCO2/kWh), but latency is 55ms.

    If latency budget is set strictly to 30ms, all candidates (Virginia 35ms, Frankfurt 55ms)
    must be REJECTED with BLOCKED BY LATENCY!
    """
    engine, db_svc, memory_svc = test_env
    decision = engine.run_optimization(workload_id="CHECKOUT", max_latency_ms=30.0)

    assert decision.status == "BLOCKED BY LATENCY"
    assert "latency" in decision.explanation.lower()
    assert decision.target_p99_latency_ms > 30.0


def test_unhealthy_target_region(test_env):
    """Unhealthy candidates must be rejected."""
    engine, db_svc, memory_svc = test_env
    # Mark Virginia and Frankfurt as unhealthy
    for r in db_svc._simulated_regions:
        if r.id != "ap-south-1":
            r.is_healthy = False

    decision = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS")
    assert decision.status in ["BLOCKED BY HEALTH", "NO ACTION NEEDED"]


def test_active_cooldown(test_env):
    """Cooldown prevents constant switching."""
    engine, db_svc, memory_svc = test_env
    # First recommendation and approval
    d1 = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS", max_latency_ms=80.0)
    assert d1.status == "RECOMMENDED"
    
    # Approve recommendation
    memory_svc.record_outcome(decision_id=d1.id, new_status="APPROVED", actual_latency_ms=55.0)

    # Immediately run another optimization cycle
    settings.cooldown_seconds = 300
    d2 = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS")
    assert d2.status == "BLOCKED BY COOLDOWN"
    assert "cooldown active" in d2.explanation.lower()


def test_insufficient_carbon_benefit(test_env):
    """Candidate with benefit below minimum threshold is not recommended."""
    engine, db_svc, memory_svc = test_env
    # Set threshold very high (e.g. 90% reduction required)
    decision = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS", min_carbon_pct=90.0)
    assert decision.status == "NO ACTION NEEDED"
    assert "falls below the configured threshold" in decision.explanation


def test_historical_warning_integration(test_env):
    """Historical degraded latency for a region generates a prominent warning in memory."""
    engine, db_svc, memory_svc = test_env
    # Generate initial decision and record outcome as degraded
    d = engine.run_optimization(workload_id="CHECKOUT")
    memory_svc.record_outcome(
        decision_id=d.id,
        new_status="REJECTED",
        rejection_reason="Caused excessive p99 spike in production trial.",
    )

    # Check that failure summary detects it
    warning = memory_svc.summarize_historical_failures("CHECKOUT", d.target_region_id)
    assert warning is not None
    assert "previous historical placement attempt" in warning


def test_no_eligible_alternatives_when_single_region(test_env):
    """When cluster topology has only one region, engine returns NO ACTION NEEDED."""
    engine, db_svc, memory_svc = test_env
    # Restrict topology to only the current leader
    current_leader = db_svc.get_current_leader_region()
    db_svc._simulated_regions = [current_leader]

    decision = engine.run_optimization(workload_id="CHECKOUT")
    assert decision.status == "NO ACTION NEEDED"
    assert "No alternative candidate regions available" in decision.explanation
    assert decision.target_region_id == current_leader.id


def test_anti_flapping_policy(test_env):
    """Verify anti-flapping pins leader during rapid evaluation cycles."""
    engine, db_svc, memory_svc = test_env
    settings.cooldown_seconds = 180

    # Execute first migration
    d1 = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS", max_latency_ms=80.0)
    assert d1.status == "RECOMMENDED"
    # Approve and move leader
    db_svc.update_leader_placement(d1.target_region_id)
    memory_svc.record_outcome(d1.id, new_status="APPROVED", actual_latency_ms=55.0)

    # Immediately request another optimization: anti-flapping should kick in
    d2 = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS")
    assert d2.status == "BLOCKED BY COOLDOWN"
    assert "cooldown active" in d2.explanation.lower()
    assert "avoid flapping" in d2.explanation.lower()

