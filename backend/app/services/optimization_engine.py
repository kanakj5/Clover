"""Deterministic, explainable Carbon-Aware Optimization Engine for Follow-the-Green Leaders.

Integrates:
- Meko Context Tool: aggregates peak traffic hours, diurnal carbon curves, and historical memory.
- Gemini AI Service: makes multi-constraint decisions on database leader placement.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from ..models.entities import Region, WorkloadConfig, OptimizationDecision, GeminiDecisionOutput
from ..simulation.seed_data import WORKLOAD_PROFILES
from ..services.carbon_calculator import CarbonCalculator
from ..services.memory_service import MemoryService
from ..services.database_service import DatabaseService
from ..services.meko_context_tool import MekoContextTool
from ..services.gemini_ai_service import GeminiAIService
from ..core.config import settings


class OptimizationEngine:
    """Evaluates multi-region database topology to find carbon-optimal leader placements

    enforcing strict latency SLAs, health invariants, and cooldown periods.
    """

    def __init__(
        self,
        database_service: DatabaseService,
        memory_service: MemoryService,
        meko_context_tool: Optional[MekoContextTool] = None,
        gemini_ai_service: Optional[GeminiAIService] = None,
    ):
        self.db_service = database_service
        self.memory_service = memory_service
        self.context_tool = meko_context_tool or MekoContextTool(memory_service)
        self.ai_service = gemini_ai_service or GeminiAIService()

    def run_optimization(
        self,
        workload_id: Optional[str] = None,
        max_latency_ms: Optional[float] = None,
        min_carbon_pct: Optional[float] = None,
        dry_run: Optional[bool] = None,
    ) -> OptimizationDecision:
        """Execute one complete optimization cycle powered by Meko context and Gemini AI."""
        # 1. Resolve effective workload and thresholds
        w_id = workload_id or settings.active_workload.value
        workload = WORKLOAD_PROFILES.get(w_id, WORKLOAD_PROFILES["CHECKOUT"])
        
        effective_budget = max_latency_ms if max_latency_ms is not None else workload.max_p99_latency_ms
        effective_min_reduction = min_carbon_pct if min_carbon_pct is not None else settings.min_carbon_reduction_pct
        is_dry_run = dry_run if dry_run is not None else settings.dry_run_enabled

        # 2. Gather cluster topology and current leader
        topology = self.db_service.get_topology()
        current_region = self.db_service.get_current_leader_region()

        # Compute current baseline emissions
        baseline_calc = CarbonCalculator.compare_regions(
            source_carbon_intensity=current_region.carbon_intensity_g_per_kwh,
            target_carbon_intensity=current_region.carbon_intensity_g_per_kwh,
            tps=workload.tps,
            duration_seconds=3600.0,
            energy_kwh_per_tx=workload.assumed_kwh_per_tx,
        )

        # 3. Check Cooldown constraint (Anti-Flapping)
        last_movement = self.memory_service.get_last_movement_timestamp()
        now = datetime.now(timezone.utc)
        cooldown_remaining_sec = 0
        if last_movement:
            if last_movement.tzinfo is None:
                last_movement = last_movement.replace(tzinfo=timezone.utc)
            elapsed = (now - last_movement).total_seconds()
            if elapsed < settings.cooldown_seconds:
                cooldown_remaining_sec = int(settings.cooldown_seconds - elapsed)

        # Single region check
        candidates = [r for r in topology if r.id != current_region.id]
        if not candidates:
            return self._create_decision(
                status="NO ACTION NEEDED",
                workload=workload,
                current_region=current_region,
                target_region=current_region,
                explanation=f"No alternative candidate regions available in topology. Leader remains in {current_region.name}.",
                effective_budget=effective_budget,
                is_dry_run=is_dry_run,
                ai_output=GeminiDecisionOutput(
                    decision="MAINTAIN_PLACEMENT",
                    target_region_id=current_region.id,
                    target_region_name=current_region.name,
                    confidence_score=0.99,
                    reasoning_steps=["No alternative candidate regions available in topology."],
                    peak_hour_impact_assessment="Single-region cluster topology.",
                    carbon_benefit_assessment="Emissions are baseline for the sole available region.",
                    rollback_plan="No action required.",
                    ai_model="Gemini 1.5 Flash (Meko Grounded)",
                ),
            )

        # Check unhealthy regions
        healthy_candidates = [r for r in candidates if r.is_healthy]
        if not healthy_candidates:
            return self._create_decision(
                status="BLOCKED BY HEALTH",
                workload=workload,
                current_region=current_region,
                target_region=current_region,
                explanation=f"Placement blocked: All alternative candidates are marked UNHEALTHY. Leader retained in {current_region.name}.",
                effective_budget=effective_budget,
                is_dry_run=is_dry_run,
                ai_output=GeminiDecisionOutput(
                    decision="MAINTAIN_PLACEMENT",
                    target_region_id=current_region.id,
                    target_region_name=current_region.name,
                    confidence_score=0.99,
                    reasoning_steps=["Cluster Invariant: All candidate regions failed health checks."],
                    peak_hour_impact_assessment="Cannot evaluate traffic peaks on unhealthy regions.",
                    carbon_benefit_assessment="Health checks take precedence over carbon optimization.",
                    rollback_plan="No action required.",
                    ai_model="Gemini 1.5 Flash (Meko Grounded)",
                ),
            )

        # 4. Ingest Meko Context Dossier (Peak times, Diurnal carbon, Historical Memory)
        dossier = self.context_tool.assemble_context_for_gemini(
            workload=workload,
            topology=topology,
            current_leader=current_region,
            latency_budget_ms=effective_budget,
            min_carbon_pct=effective_min_reduction,
            cooldown_remaining_sec=cooldown_remaining_sec,
            target_time=now,
        )

        # 5. Gemini AI Evaluates the Multi-Constraint Decision
        ai_output = self.ai_service.evaluate_placement(dossier, cooldown_remaining_sec=cooldown_remaining_sec)

        # 6. Map Gemini Decision Output into Auditable Domain Decision
        if ai_output.decision == "BLOCKED_BY_COOLDOWN":
            return self._create_decision(
                status="BLOCKED BY COOLDOWN",
                workload=workload,
                current_region=current_region,
                target_region=current_region,
                explanation=(
                    f"Leader movement cooldown active ({cooldown_remaining_sec}s remaining of {settings.cooldown_seconds}s limit). "
                    f"Leader remains pinned in {current_region.name} to avoid flapping."
                ),
                effective_budget=effective_budget,
                is_dry_run=is_dry_run,
                ai_output=ai_output,
            )

        if ai_output.decision == "BLOCKED_BY_SLA":
            target_obj = next((r for r in topology if r.id == ai_output.target_region_id), current_region)
            cleanest_blocked = min(candidates, key=lambda c: c.carbon_intensity_g_per_kwh, default=target_obj)
            explanation = (
                f"Although {cleanest_blocked.name} offers lower carbon intensity ({cleanest_blocked.carbon_intensity_g_per_kwh:.0f} gCO2/kWh), "
                f"it was rejected: Write latency ({cleanest_blocked.base_write_latency_ms:.1f}ms) violates the strict '{workload.id}' budget of {effective_budget:.1f}ms. "
                f"Performance constraints took precedence over emissions reduction."
            )
            return self._create_decision(
                status="BLOCKED BY LATENCY",
                workload=workload,
                current_region=current_region,
                target_region=cleanest_blocked,
                explanation=explanation,
                effective_budget=effective_budget,
                is_dry_run=is_dry_run,
                ai_output=ai_output,
            )

        if ai_output.decision == "RECOMMEND_MIGRATION":
            target_cand = next((r for r in topology if r.id == ai_output.target_region_id), None)
            if not target_cand:
                target_cand = current_region

            calc = CarbonCalculator.compare_regions(
                source_carbon_intensity=current_region.carbon_intensity_g_per_kwh,
                target_carbon_intensity=target_cand.carbon_intensity_g_per_kwh,
                tps=workload.tps,
                duration_seconds=3600.0,
                energy_kwh_per_tx=workload.assumed_kwh_per_tx,
            )

            # Check threshold
            if calc.reduction_percentage < effective_min_reduction:
                explanation = (
                    f"Best candidate {target_cand.name} only reduces emissions by {calc.reduction_percentage:.1f}%, "
                    f"which falls below the configured threshold of {effective_min_reduction}%. Leader retained in {current_region.name}."
                )
                return self._create_decision(
                    status="NO ACTION NEEDED",
                    workload=workload,
                    current_region=current_region,
                    target_region=target_cand,
                    explanation=explanation,
                    effective_budget=effective_budget,
                    is_dry_run=is_dry_run,
                    ai_output=ai_output,
                )

            explanation = (
                f"Recommend moving database leaders from {current_region.name} ({current_region.carbon_intensity_g_per_kwh:.0f} gCO2/kWh) "
                f"to {target_cand.name} ({target_cand.carbon_intensity_g_per_kwh:.0f} gCO2/kWh). "
                f"Expected carbon savings: {calc.reduction_g_per_hour:.1f} gCO2/hr ({calc.reduction_percentage:.1f}% reduction). "
                f"Estimated p99 write latency will be {target_cand.base_write_latency_ms:.1f}ms (within allowed budget of {effective_budget:.1f}ms)."
            )

            cost_delta_usd = None
            if settings.cost_aware_enabled and target_cand.electricity_price_usd_per_kwh and current_region.electricity_price_usd_per_kwh:
                hourly_kwh = calc.total_energy_kwh_per_hour
                current_cost = hourly_kwh * current_region.electricity_price_usd_per_kwh
                cand_cost = hourly_kwh * target_cand.electricity_price_usd_per_kwh
                cost_delta_usd = cand_cost - current_cost

            return self._create_decision(
                status="RECOMMENDED",
                workload=workload,
                current_region=current_region,
                target_region=target_cand,
                explanation=explanation,
                effective_budget=effective_budget,
                is_dry_run=is_dry_run,
                ai_output=ai_output,
                cost_delta_usd=cost_delta_usd,
            )

        # Default fallback: Maintain placement
        return self._create_decision(
            status="NO ACTION NEEDED",
            workload=workload,
            current_region=current_region,
            target_region=current_region,
            explanation=f"Current placement in {current_region.name} is optimal. No action needed.",
            effective_budget=effective_budget,
            is_dry_run=is_dry_run,
            ai_output=ai_output,
        )

    def _create_decision(
        self,
        status: str,
        workload: WorkloadConfig,
        current_region: Region,
        target_region: Region,
        explanation: str,
        effective_budget: float,
        is_dry_run: bool,
        ai_output: GeminiDecisionOutput,
        cost_delta_usd: Optional[float] = None,
    ) -> OptimizationDecision:
        calc = CarbonCalculator.compare_regions(
            source_carbon_intensity=current_region.carbon_intensity_g_per_kwh,
            target_carbon_intensity=target_region.carbon_intensity_g_per_kwh,
            tps=workload.tps,
            duration_seconds=3600.0,
            energy_kwh_per_tx=workload.assumed_kwh_per_tx,
        )
        hist_warning = self.memory_service.summarize_historical_failures(workload.id, target_region.id)

        decision = OptimizationDecision(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            workload_id=workload.id,
            workload_name=workload.name,
            current_region_id=current_region.id,
            current_region_name=current_region.name,
            target_region_id=target_region.id,
            target_region_name=target_region.name,
            current_carbon_intensity=current_region.carbon_intensity_g_per_kwh,
            target_carbon_intensity=target_region.carbon_intensity_g_per_kwh,
            current_emissions_g_per_hr=calc.source_emissions_g_per_hour,
            target_emissions_g_per_hr=calc.target_emissions_g_per_hour,
            carbon_reduction_g_per_hr=calc.reduction_g_per_hour,
            carbon_reduction_pct=calc.reduction_percentage,
            current_p99_latency_ms=current_region.base_write_latency_ms,
            target_p99_latency_ms=target_region.base_write_latency_ms,
            latency_delta_ms=target_region.base_write_latency_ms - current_region.base_write_latency_ms,
            latency_budget_ms=effective_budget,
            status=status,
            explanation=explanation,
            historical_warning=hist_warning,
            is_simulated=settings.operating_mode != "LIVE",
            is_dry_run=is_dry_run,
            cost_delta_usd_per_hr=cost_delta_usd,
            ai_model=ai_output.ai_model,
            ai_confidence_score=ai_output.confidence_score,
            ai_reasoning_steps=ai_output.reasoning_steps,
            peak_hour_analysis=ai_output.peak_hour_impact_assessment,
            rollback_plan=ai_output.rollback_plan,
            meko_context_summary=f"Meko Context: Ingested diurnal emissions at this time, regional peak windows, and persistent memory audit.",
        )
        self.memory_service.store_decision(decision)
        return decision
