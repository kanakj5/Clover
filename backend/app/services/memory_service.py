"""Persistent Memory Layer for Follow-the-Green Leaders decisions.

Supports SQLite persistent storage (local simulation) and YugabyteDB PostgreSQL interface.
Provides warning heuristics based on actual recorded historical performance outcomes.
"""
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from ..models.entities import OptimizationDecision
from ..core.config import settings


class MemoryService:
    """Manages persistent decision history, outcome tracking, and historical heuristics."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.sqlite_db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize memory schema if not exists and migrate new columns."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_history (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    workload_id TEXT NOT NULL,
                    workload_name TEXT NOT NULL,
                    current_region_id TEXT NOT NULL,
                    current_region_name TEXT NOT NULL,
                    target_region_id TEXT NOT NULL,
                    target_region_name TEXT NOT NULL,
                    current_carbon_intensity REAL NOT NULL,
                    target_carbon_intensity REAL NOT NULL,
                    current_emissions_g_per_hr REAL NOT NULL,
                    target_emissions_g_per_hr REAL NOT NULL,
                    carbon_reduction_g_per_hr REAL NOT NULL,
                    carbon_reduction_pct REAL NOT NULL,
                    current_p99_latency_ms REAL NOT NULL,
                    target_p99_latency_ms REAL NOT NULL,
                    latency_delta_ms REAL NOT NULL,
                    latency_budget_ms REAL NOT NULL,
                    status TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    historical_warning TEXT,
                    is_simulated INTEGER NOT NULL,
                    is_dry_run INTEGER NOT NULL,
                    cost_delta_usd_per_hr REAL,
                    operator_action_at TEXT,
                    rejection_reason TEXT,
                    actual_latency_ms REAL,
                    performance_impact TEXT,
                    ai_model TEXT,
                    ai_confidence_score REAL,
                    ai_reasoning_steps TEXT,
                    peak_hour_analysis TEXT,
                    rollback_plan TEXT,
                    meko_context_summary TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_workload ON decision_history (workload_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_target ON decision_history (target_region_id);
            """)

            # Safe column migrations for existing databases
            new_cols = [
                ("ai_model", "TEXT"),
                ("ai_confidence_score", "REAL"),
                ("ai_reasoning_steps", "TEXT"),
                ("peak_hour_analysis", "TEXT"),
                ("rollback_plan", "TEXT"),
                ("meko_context_summary", "TEXT"),
            ]
            for col_name, col_type in new_cols:
                try:
                    conn.execute(f"ALTER TABLE decision_history ADD COLUMN {col_name} {col_type};")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            conn.commit()

    def store_decision(self, decision: OptimizationDecision) -> OptimizationDecision:
        """Store a newly generated decision recommendation."""
        reasoning_json = json.dumps(decision.ai_reasoning_steps) if decision.ai_reasoning_steps else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decision_history (
                    id, timestamp, workload_id, workload_name,
                    current_region_id, current_region_name,
                    target_region_id, target_region_name,
                    current_carbon_intensity, target_carbon_intensity,
                    current_emissions_g_per_hr, target_emissions_g_per_hr,
                    carbon_reduction_g_per_hr, carbon_reduction_pct,
                    current_p99_latency_ms, target_p99_latency_ms,
                    latency_delta_ms, latency_budget_ms,
                    status, explanation, historical_warning,
                    is_simulated, is_dry_run, cost_delta_usd_per_hr,
                    operator_action_at, rejection_reason,
                    actual_latency_ms, performance_impact,
                    ai_model, ai_confidence_score, ai_reasoning_steps,
                    peak_hour_analysis, rollback_plan, meko_context_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.id,
                decision.timestamp,
                decision.workload_id,
                decision.workload_name,
                decision.current_region_id,
                decision.current_region_name,
                decision.target_region_id,
                decision.target_region_name,
                decision.current_carbon_intensity,
                decision.target_carbon_intensity,
                decision.current_emissions_g_per_hr,
                decision.target_emissions_g_per_hr,
                decision.carbon_reduction_g_per_hr,
                decision.carbon_reduction_pct,
                decision.current_p99_latency_ms,
                decision.target_p99_latency_ms,
                decision.latency_delta_ms,
                decision.latency_budget_ms,
                decision.status,
                decision.explanation,
                decision.historical_warning,
                1 if decision.is_simulated else 0,
                1 if decision.is_dry_run else 0,
                decision.cost_delta_usd_per_hr,
                decision.operator_action_at,
                decision.rejection_reason,
                None,
                None,
                decision.ai_model,
                decision.ai_confidence_score,
                reasoning_json,
                decision.peak_hour_analysis,
                decision.rollback_plan,
                decision.meko_context_summary,
            ))
            conn.commit()
        return decision

    def record_outcome(
        self,
        decision_id: str,
        new_status: str,
        actual_latency_ms: Optional[float] = None,
        rejection_reason: Optional[str] = None,
    ) -> Optional[OptimizationDecision]:
        """Record operator approval, rejection, or measured post-migration latency."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # First fetch existing record
            cur = conn.execute("SELECT * FROM decision_history WHERE id = ?", (decision_id,))
            row = cur.fetchone()
            if not row:
                return None

            impact = None
            if actual_latency_ms is not None:
                budget = row["latency_budget_ms"]
                if actual_latency_ms > budget:
                    impact = "DEGRADED (Violated Budget)"
                elif actual_latency_ms > row["current_p99_latency_ms"]:
                    impact = "SLOWER_ACCEPTABLE"
                else:
                    impact = "IMPROVED"

            conn.execute("""
                UPDATE decision_history
                SET status = ?,
                    operator_action_at = ?,
                    actual_latency_ms = COALESCE(?, actual_latency_ms),
                    rejection_reason = COALESCE(?, rejection_reason),
                    performance_impact = COALESCE(?, performance_impact)
                WHERE id = ?
            """, (new_status, now_iso, actual_latency_ms, rejection_reason, impact, decision_id))
            conn.commit()

        return self.get_decision_by_id(decision_id)

    def get_decision_by_id(self, decision_id: str) -> Optional[OptimizationDecision]:
        """Fetch single decision by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM decision_history WHERE id = ?", (decision_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_decision(row)

    def get_history(
        self,
        limit: int = 50,
        workload_id: Optional[str] = None,
        region_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OptimizationDecision]:
        """Retrieve filtered decision history sorted descending by timestamp."""
        query = "SELECT * FROM decision_history WHERE 1=1"
        params: List[Any] = []

        if workload_id:
            query += " AND workload_id = ?"
            params.append(workload_id)
        if region_id:
            query += " AND (current_region_id = ? OR target_region_id = ?)"
            params.extend([region_id, region_id])
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [self._row_to_decision(r) for r in cur.fetchall()]

    def retrieve_similar_decisions(
        self,
        workload_id: str,
        target_region_id: str,
        limit: int = 5,
    ) -> List[OptimizationDecision]:
        """Retrieve past decisions matching this workload and target region."""
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT * FROM decision_history
                WHERE workload_id = ? AND target_region_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (workload_id, target_region_id, limit))
            return [self._row_to_decision(r) for r in cur.fetchall()]

    def summarize_historical_failures(
        self,
        workload_id: str,
        target_region_id: str,
    ) -> Optional[str]:
        """Scan historical decisions for recorded regressions or latency violations.

        Returns an explanatory warning string if and only if prior failures actually exist in memory.
        """
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT COUNT(*) as count, AVG(latency_delta_ms) as avg_delta
                FROM decision_history
                WHERE workload_id = ? AND target_region_id = ?
                  AND (status = 'REJECTED' OR status = 'BLOCKED BY LATENCY' OR performance_impact LIKE 'DEGRADED%')
            """, (workload_id, target_region_id))
            row = cur.fetchone()
            if row and row["count"] > 0:
                count = row["count"]
                return (
                    f"Warning: {count} previous historical placement attempt(s) for '{workload_id}' "
                    f"targeting '{target_region_id}' were rejected or degraded latency. "
                    f"The decision engine has adjusted its risk assessment accordingly."
                )
        return None

    def get_last_movement_timestamp(self) -> Optional[datetime]:
        """Get the timestamp of the last approved leader placement change for cooldown verification."""
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT operator_action_at, timestamp FROM decision_history
                WHERE status = 'APPROVED'
                ORDER BY COALESCE(operator_action_at, timestamp) DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                ts_str = row["operator_action_at"] or row["timestamp"]
                try:
                    return datetime.fromisoformat(ts_str)
                except Exception:
                    pass
        return None

    def clear_history(self):
        """Reset simulation history after confirmation."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM decision_history")
            conn.commit()

    @staticmethod
    def _row_to_decision(row: sqlite3.Row) -> OptimizationDecision:
        keys = row.keys()
        
        reasoning_steps = None
        if "ai_reasoning_steps" in keys and row["ai_reasoning_steps"]:
            try:
                reasoning_steps = json.loads(row["ai_reasoning_steps"])
            except Exception:
                reasoning_steps = [row["ai_reasoning_steps"]]

        return OptimizationDecision(
            id=row["id"],
            timestamp=row["timestamp"],
            workload_id=row["workload_id"],
            workload_name=row["workload_name"],
            current_region_id=row["current_region_id"],
            current_region_name=row["current_region_name"],
            target_region_id=row["target_region_id"],
            target_region_name=row["target_region_name"],
            current_carbon_intensity=row["current_carbon_intensity"],
            target_carbon_intensity=row["target_carbon_intensity"],
            current_emissions_g_per_hr=row["current_emissions_g_per_hr"],
            target_emissions_g_per_hr=row["target_emissions_g_per_hr"],
            carbon_reduction_g_per_hr=row["carbon_reduction_g_per_hr"],
            carbon_reduction_pct=row["carbon_reduction_pct"],
            current_p99_latency_ms=row["current_p99_latency_ms"],
            target_p99_latency_ms=row["target_p99_latency_ms"],
            latency_delta_ms=row["latency_delta_ms"],
            latency_budget_ms=row["latency_budget_ms"],
            status=row["status"],
            explanation=row["explanation"],
            historical_warning=row["historical_warning"],
            is_simulated=bool(row["is_simulated"]),
            is_dry_run=bool(row["is_dry_run"]),
            cost_delta_usd_per_hr=row["cost_delta_usd_per_hr"],
            operator_action_at=row["operator_action_at"],
            rejection_reason=row["rejection_reason"],
            ai_model=row["ai_model"] if "ai_model" in keys else "Gemini 1.5 Flash (Meko Grounded)",
            ai_confidence_score=row["ai_confidence_score"] if "ai_confidence_score" in keys and row["ai_confidence_score"] is not None else 0.95,
            ai_reasoning_steps=reasoning_steps,
            peak_hour_analysis=row["peak_hour_analysis"] if "peak_hour_analysis" in keys else None,
            rollback_plan=row["rollback_plan"] if "rollback_plan" in keys else None,
            meko_context_summary=row["meko_context_summary"] if "meko_context_summary" in keys else None,
        )
