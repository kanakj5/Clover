"""Unit and integration tests for Meko Context Tool and Gemini AI Service."""
import pytest
from datetime import datetime, timezone
from app.services.meko_context_tool import MekoContextTool
from app.services.gemini_ai_service import GeminiAIService
from app.services.optimization_engine import OptimizationEngine
from app.services.database_service import DatabaseService
from app.services.memory_service import MemoryService
from app.simulation.seed_data import WORKLOAD_PROFILES
from app.api.endpoints import get_meko_regional_peaks, get_meko_context_dossier


@pytest.fixture
def meko_gemini_env(tmp_path):
    db_file = str(tmp_path / "test_meko_memory.db")
    memory_svc = MemoryService(db_path=db_file)
    db_svc = DatabaseService()
    db_svc.reset_simulation()
    context_tool = MekoContextTool(memory_svc)
    ai_service = GeminiAIService()
    engine = OptimizationEngine(
        database_service=db_svc,
        memory_service=memory_svc,
        meko_context_tool=context_tool,
        gemini_ai_service=ai_service,
    )
    return engine, db_svc, memory_svc, context_tool, ai_service


def test_meko_peak_schedules(meko_gemini_env):
    """Verify Meko tracks regional peak hours, UTC offsets, and grid windows."""
    _, _, _, context_tool, _ = meko_gemini_env
    peaks = context_tool.get_peak_schedules()
    assert len(peaks) == 3
    names = [p.name for p in peaks]
    assert "Mumbai" in names
    assert "Frankfurt" in names
    assert "Virginia" in names

    mumbai = next(p for p in peaks if p.name == "Mumbai")
    assert "IST" in mumbai.timezone_label
    assert mumbai.traffic_surge_factor >= 1.0


def test_meko_context_dossier_assembly(meko_gemini_env):
    """Verify Meko compiles full multi-region dossier with telemetry and markdown prompt."""
    _, db_svc, _, context_tool, _ = meko_gemini_env
    workload = WORKLOAD_PROFILES["CHECKOUT"]
    topology = db_svc.get_topology()
    current_leader = db_svc.get_current_leader_region()

    dossier = context_tool.assemble_context_for_gemini(
        workload=workload,
        topology=topology,
        current_leader=current_leader,
        latency_budget_ms=40.0,
        min_carbon_pct=10.0,
        cooldown_remaining_sec=0,
    )

    assert dossier.workload_id == "CHECKOUT"
    assert len(dossier.regional_telemetry) == 3
    assert len(dossier.candidate_options) == 2
    assert "MEKO CONTEXT DOSSIER" in dossier.context_prompt_for_ai
    assert "Workload Specifications" in dossier.context_prompt_for_ai


def test_gemini_decision_reasoning_and_rollback(meko_gemini_env):
    """Verify Gemini AI outputs structured confidence, analytical steps, and rollback plans."""
    _, db_svc, _, context_tool, ai_service = meko_gemini_env
    workload = WORKLOAD_PROFILES["BACKGROUND_ANALYTICS"]
    topology = db_svc.get_topology()
    current_leader = db_svc.get_current_leader_region()

    dossier = context_tool.assemble_context_for_gemini(
        workload=workload,
        topology=topology,
        current_leader=current_leader,
        latency_budget_ms=80.0,
        min_carbon_pct=10.0,
        cooldown_remaining_sec=0,
    )

    decision = ai_service.evaluate_placement(dossier, cooldown_remaining_sec=0)
    assert decision.decision in ["RECOMMEND_MIGRATION", "MAINTAIN_PLACEMENT"]
    assert decision.confidence_score >= 0.8
    assert len(decision.reasoning_steps) >= 3
    assert "Gemini" in decision.ai_model
    assert "ALTER TABLESPACE" in decision.rollback_plan or "No action" in decision.rollback_plan


def test_optimization_engine_persists_ai_fields(meko_gemini_env):
    """Verify OptimizationEngine integrates Meko + Gemini and stores AI metadata in persistent memory."""
    engine, _, memory_svc, _, _ = meko_gemini_env
    decision = engine.run_optimization(workload_id="BACKGROUND_ANALYTICS", max_latency_ms=80.0)

    assert decision.ai_model is not None
    assert "Gemini" in decision.ai_model
    assert decision.ai_confidence_score is not None
    assert decision.ai_reasoning_steps is not None
    assert len(decision.ai_reasoning_steps) > 0
    assert decision.peak_hour_analysis is not None
    assert decision.rollback_plan is not None

    # Verify reload from SQLite persistent memory
    reloaded = memory_svc.get_decision_by_id(decision.id)
    assert reloaded is not None
    assert reloaded.ai_model == decision.ai_model
    assert reloaded.ai_confidence_score == decision.ai_confidence_score
    assert reloaded.ai_reasoning_steps == decision.ai_reasoning_steps
    assert reloaded.rollback_plan == decision.rollback_plan


def test_api_meko_endpoints():
    """Verify /api/meko/peaks and /api/meko/context HTTP handlers."""
    peaks = get_meko_regional_peaks()
    assert len(peaks) == 3

    dossier = get_meko_context_dossier(workload_id="CHECKOUT")
    assert dossier.workload_id == "CHECKOUT"
    assert len(dossier.regional_telemetry) == 3
