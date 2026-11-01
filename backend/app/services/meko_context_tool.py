"""Meko Context Tool for Follow-the-Green Leaders.

Meko acts as the contextual memory and intelligence tool:
1. Ingests and tracks regional peak traffic hours and workload curves.
2. Ingests time-varying diurnal carbon emissions data for each region at that specific time.
3. Retrieves historical database migration precedents, outcomes, and operator rejections.
4. Assembles a rich, multi-dimensional Context Dossier fed directly into Gemini AI.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from ..models.entities import (
    Region,
    WorkloadConfig,
    RegionalPeakSchedule,
    RegionalTelemetryStatus,
    MekoContextDossier,
)
from ..simulation.seed_data import get_simulated_carbon_intensity
from ..services.memory_service import MemoryService


class MekoContextTool:
    """Context aggregation, peak-time tracking, and carbon intelligence layer."""

    REGIONAL_SCHEDULES = {
        "ap-south-1": {
            "name": "Mumbai",
            "timezone_label": "IST (UTC+5:30)",
            "utc_offset": 5.5,
            "peak_traffic_start": 9.5,
            "peak_traffic_end": 21.0,
            "surge_factor": 1.85,
            "clean_window_start": 11.0,
            "clean_window_end": 15.0,
            "dirty_peak_start": 18.0,
            "dirty_peak_end": 22.5,
            "clean_label": "11:00 - 15:00 IST (Solar Generation Dip)",
            "dirty_label": "18:00 - 22:30 IST (Evening Peak Coal Peakers)",
        },
        "eu-central-1": {
            "name": "Frankfurt",
            "timezone_label": "CET (UTC+1:00 / UTC+2:00)",
            "utc_offset": 2.0,
            "peak_traffic_start": 8.5,
            "peak_traffic_end": 18.0,
            "surge_factor": 1.60,
            "clean_window_start": 10.5,
            "clean_window_end": 15.5,
            "dirty_peak_start": 17.5,
            "dirty_peak_end": 21.0,
            "clean_label": "10:30 - 15:30 CET (Solar & Wind Influx - Cleanest Grid)",
            "dirty_label": "17:30 - 21:00 CET (Evening Grid Demand Peak)",
        },
        "us-east-1": {
            "name": "Virginia",
            "timezone_label": "EST (UTC-4:00)",
            "utc_offset": -4.0,
            "peak_traffic_start": 9.0,
            "peak_traffic_end": 18.0,
            "surge_factor": 1.70,
            "clean_window_start": 11.0,
            "clean_window_end": 16.0,
            "dirty_peak_start": 17.0,
            "dirty_peak_end": 21.0,
            "clean_label": "11:00 - 16:00 EST (Midday Nuclear + Solar baseload)",
            "dirty_label": "17:00 - 21:00 EST (Evening Gas Peaker Ramp)",
        },
    }

    def __init__(self, memory_service: MemoryService):
        self.memory_service = memory_service

    def get_peak_schedules(self, target_time: Optional[datetime] = None) -> List[RegionalPeakSchedule]:
        """Return the current peak status and schedules for all regions."""
        now = target_time or datetime.now(timezone.utc)
        results = []

        for region_id, sched in self.REGIONAL_SCHEDULES.items():
            local_dt = now + timedelta(hours=sched["utc_offset"])
            local_decimal = local_dt.hour + (local_dt.minute / 60.0)

            is_peak = sched["peak_traffic_start"] <= local_decimal <= sched["peak_traffic_end"]
            
            if sched["clean_window_start"] <= local_decimal <= sched["clean_window_end"]:
                grid_cond = "CLEAN_RENEWABLE_WINDOW"
            elif sched["dirty_peak_start"] <= local_decimal <= sched["dirty_peak_end"]:
                grid_cond = "DIRTY_FOSSIL_PEAK"
            else:
                grid_cond = "OFF_PEAK_BASELOAD"

            results.append(
                RegionalPeakSchedule(
                    region_id=region_id,
                    name=sched["name"],
                    timezone_label=sched["timezone_label"],
                    utc_offset_hours=sched["utc_offset"],
                    peak_traffic_window=f"{int(sched['peak_traffic_start']):02d}:30 - {int(sched['peak_traffic_end']):02d}:00",
                    is_peak_now=is_peak,
                    local_time_display=local_dt.strftime("%H:%M %p"),
                    traffic_surge_factor=sched["surge_factor"] if is_peak else 1.0,
                    carbon_surge_window=sched["dirty_label"] if grid_cond == "DIRTY_FOSSIL_PEAK" else sched["clean_label"],
                    grid_condition=grid_cond,
                )
            )

        return results

    def get_regional_telemetry(self, topology: List[Region], target_time: Optional[datetime] = None) -> List[RegionalTelemetryStatus]:
        """Synthesize live/simulated telemetry: local hour, peak phase, carbon now, carbon in 4h, trend."""
        now = target_time or datetime.now(timezone.utc)
        in_4h = now + timedelta(hours=4)
        telemetry = []

        for region in topology:
            sched = self.REGIONAL_SCHEDULES.get(region.id, {
                "name": region.name,
                "utc_offset": 0.0,
                "peak_traffic_start": 9.0,
                "peak_traffic_end": 18.0,
                "surge_factor": 1.5,
            })

            local_dt = now + timedelta(hours=sched["utc_offset"])
            local_dec = local_dt.hour + (local_dt.minute / 60.0)
            is_peak = sched["peak_traffic_start"] <= local_dec <= sched["peak_traffic_end"]

            ci_now = get_simulated_carbon_intensity(region.id, now)
            ci_4h = get_simulated_carbon_intensity(region.id, in_4h)

            diff = ci_4h - ci_now
            if diff < -15.0:
                trend = "FALLING_CLEANER"
            elif diff > 15.0:
                trend = "RISING_DIRTIER"
            else:
                trend = "STABLE"

            phase = "PEAK_TRAFFIC" if is_peak else "OFF_PEAK"

            telemetry.append(
                RegionalTelemetryStatus(
                    region_id=region.id,
                    name=region.name,
                    is_healthy=region.is_healthy,
                    is_leader=region.is_leader,
                    base_write_latency_ms=region.base_write_latency_ms,
                    carbon_intensity_now=ci_now,
                    carbon_intensity_in_4h=ci_4h,
                    carbon_trend=trend,
                    local_time=local_dt.strftime("%H:%M %p"),
                    is_peak_traffic=is_peak,
                    peak_phase=phase,
                    traffic_surge_factor=sched["surge_factor"] if is_peak else 1.0,
                )
            )

        return telemetry

    def assemble_context_for_gemini(
        self,
        workload: WorkloadConfig,
        topology: List[Region],
        current_leader: Region,
        latency_budget_ms: float,
        min_carbon_pct: float,
        cooldown_remaining_sec: int = 0,
        target_time: Optional[datetime] = None,
    ) -> MekoContextDossier:
        """Assemble complete context dossier: peak times, carbon emissions at this time, historical memory."""
        now = target_time or datetime.now(timezone.utc)
        telemetry = self.get_regional_telemetry(topology, now)

        historical_warnings = []
        for cand in topology:
            if cand.id != current_leader.id:
                warning = self.memory_service.summarize_historical_failures(workload.id, cand.id)
                if warning:
                    historical_warnings.append(warning)

        candidates = []
        for r_stat in telemetry:
            if r_stat.region_id == current_leader.id:
                continue

            cand_obj = next((r for r in topology if r.id == r_stat.region_id), None)
            if not cand_obj:
                continue

            baseline_ci = next((t.carbon_intensity_now for t in telemetry if t.region_id == current_leader.id), 500.0)
            reduction_pct = 0.0
            if baseline_ci > 0:
                reduction_pct = max(0.0, ((baseline_ci - r_stat.carbon_intensity_now) / baseline_ci) * 100.0)

            latency_delta = r_stat.base_write_latency_ms - current_leader.base_write_latency_ms
            violates_sla = r_stat.base_write_latency_ms > latency_budget_ms

            candidates.append({
                "region_id": r_stat.region_id,
                "region_name": r_stat.name,
                "is_healthy": r_stat.is_healthy,
                "carbon_intensity": r_stat.carbon_intensity_now,
                "carbon_intensity_in_4h": r_stat.carbon_intensity_in_4h,
                "carbon_trend": r_stat.carbon_trend,
                "carbon_reduction_pct": round(reduction_pct, 1),
                "base_write_latency_ms": r_stat.base_write_latency_ms,
                "latency_delta_ms": round(latency_delta, 1),
                "violates_sla": violates_sla,
                "local_time": r_stat.local_time,
                "is_peak_traffic": r_stat.is_peak_traffic,
            })

        prompt_text = self._build_gemini_prompt(
            workload=workload,
            current_leader=current_leader,
            telemetry=telemetry,
            candidates=candidates,
            historical_warnings=historical_warnings,
            latency_budget_ms=latency_budget_ms,
            min_carbon_pct=min_carbon_pct,
            cooldown_remaining_sec=cooldown_remaining_sec,
            now=now,
        )

        return MekoContextDossier(
            context_id=f"meko-{uuid.uuid4().hex[:12]}",
            generated_at=now.isoformat(),
            workload_id=workload.id,
            workload_name=workload.name,
            workload_priority=workload.priority,
            max_p99_latency_budget_ms=latency_budget_ms,
            current_tps=workload.tps,
            current_leader_id=current_leader.id,
            current_leader_name=current_leader.name,
            regional_telemetry=telemetry,
            historical_warnings=historical_warnings,
            candidate_options=candidates,
            context_prompt_for_ai=prompt_text,
        )

    def _build_gemini_prompt(
        self,
        workload: WorkloadConfig,
        current_leader: Region,
        telemetry: List[RegionalTelemetryStatus],
        candidates: List[Dict[str, Any]],
        historical_warnings: List[str],
        latency_budget_ms: float,
        min_carbon_pct: float,
        cooldown_remaining_sec: int,
        now: datetime,
    ) -> str:
        """Render markdown-formatted context dossier for Gemini AI."""
        lines = [
            f"# MEKO CONTEXT DOSSIER: MULTI-REGION DATABASE PLACEMENT",
            f"**Timestamp (UTC):** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"",
            f"## 1. Workload Specifications",
            f"- **Workload ID:** `{workload.id}` ({workload.name})",
            f"- **Priority Policy:** `{workload.priority}`",
            f"- **Max Allowed p99 Latency Budget:** **{latency_budget_ms:.1f} ms** (Strict SLA constraint)",
            f"- **Active Load Rate:** {workload.tps:,.0f} TPS",
            f"- **Energy Heuristic:** {workload.assumed_kwh_per_tx:.6f} kWh/tx",
            f"",
            f"## 2. Current Cluster Placement",
            f"- **Active Leader Region:** **{current_leader.name}** (`{current_leader.id}`)",
            f"- **Current Leader Latency:** {current_leader.base_write_latency_ms:.1f} ms",
            f"- **Cooldown Status:** {'ACTIVE (' + str(cooldown_remaining_sec) + 's remaining)' if cooldown_remaining_sec > 0 else 'EXPIRED (Leader migration permitted)'}",
            f"",
            f"## 3. Real-Time Regional Peak Times & Carbon Telemetry",
        ]

        for t in telemetry:
            is_lead = " [CURRENT LEADER]" if t.is_leader else ""
            lines.append(
                f"- **{t.name}** (`{t.region_id}`){is_lead}:\n"
                f"  • Local Clock: {t.local_time} | Status: {'🔴 PEAK TRAFFIC (' + str(t.traffic_surge_factor) + 'x load)' if t.is_peak_traffic else '🟢 OFF-PEAK BASELOAD'}\n"
                f"  • Carbon Intensity Now: **{t.carbon_intensity_now:.0f} gCO₂/kWh**\n"
                f"  • 4-Hour Trend: {t.carbon_trend} (Projected in 4h: {t.carbon_intensity_in_4h:.0f} gCO₂/kWh)\n"
                f"  • Write Latency: {t.base_write_latency_ms:.1f} ms"
            )

        lines.append("")
        lines.append("## 4. Evaluated Candidate Alternatives")
        for c in candidates:
            sla_status = "❌ VIOLATES SLA BUDGET" if c["violates_sla"] else "✅ WITHIN SLA BUDGET"
            lines.append(
                f"- **Target: {c['region_name']} (`{c['region_id']}`)**\n"
                f"  • Potential Carbon Reduction: **{c['carbon_reduction_pct']}%** (CI: {c['carbon_intensity']:.0f} gCO₂/kWh)\n"
                f"  • Latency: {c['base_write_latency_ms']:.1f} ms (Delta: {'+' if c['latency_delta_ms'] > 0 else ''}{c['latency_delta_ms']:.1f} ms) — {sla_status}\n"
                f"  • Local Time: {c['local_time']} ({'PEAK' if c['is_peak_traffic'] else 'OFF-PEAK'})"
            )

        if historical_warnings:
            lines.append("")
            lines.append("## 5. Meko Persistent Memory & Historical Precedents")
            for hw in historical_warnings:
                lines.append(f"- ⚠️ {hw}")
        else:
            lines.append("")
            lines.append("## 5. Meko Persistent Memory & Historical Precedents")
            lines.append("- No recorded latency violations or operator rejections for this workload/region pair.")

        lines.append("")
        lines.append("## 6. Optimization Decision Objectives for Gemini AI")
        lines.append(
            f"1. Performance First: Never violate the {latency_budget_ms:.1f} ms p99 write latency budget.\n"
            f"2. Peak Traffic Safety: Factor in whether the source or target region is in peak demand.\n"
            f"3. Carbon Maximization: Seek the maximum carbon reduction qualifying above the {min_carbon_pct}% threshold.\n"
            f"4. Stability: Respect anti-flapping cooldowns.\n"
            f"5. Provide actionable reasoning steps, confidence score, and operational rollback instructions."
        )

        return "\n".join(lines)
