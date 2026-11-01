"""Database Service managing cluster state, topology, and leader migrations."""
import copy
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from ..models.entities import Region
from ..simulation.seed_data import DEFAULT_REGIONS, get_simulated_carbon_intensity
from ..adapters.yugabytedb_adapter import YugabyteDBAdapter
from ..core.config import settings, OperatingMode


class DatabaseService:
    """Provides high-level database topology and leader control for both Live and Simulation modes."""

    def __init__(self, yugabyte_adapter: Optional[YugabyteDBAdapter] = None):
        self.yugabyte_adapter = yugabyte_adapter or YugabyteDBAdapter()
        # Simulated regions in-memory state
        self._simulated_regions: List[Region] = [copy.deepcopy(r) for r in DEFAULT_REGIONS]

    def get_operating_mode(self) -> OperatingMode:
        return settings.operating_mode

    def get_connection_status(self) -> Dict[str, Any]:
        """Check live database connectivity or return simulation status."""
        if settings.operating_mode == OperatingMode.LIVE:
            return self.yugabyte_adapter.check_connection()
        return {
            "is_connected": False,
            "mode": "SIMULATION_MODE",
            "host": settings.yugabytedb_host,
            "port": settings.yugabytedb_port,
            "database": settings.yugabytedb_database,
            "status_label": "SIMULATION MODE ACTIVE",
            "guidance": "Running in offline simulation mode without requiring live external infrastructure.",
        }

    def get_topology(self) -> List[Region]:
        """Fetch current database topology with updated carbon intensities."""
        now = datetime.now(timezone.utc)
        for r in self._simulated_regions:
            r.carbon_intensity_g_per_kwh = get_simulated_carbon_intensity(r.id, now)
            r.last_updated = now.isoformat()
        return [copy.deepcopy(r) for r in self._simulated_regions]

    def get_current_leader_region(self) -> Region:
        """Find the region where database leaders are currently placed."""
        for r in self._simulated_regions:
            if r.is_leader:
                return r
        # Fallback to first region if none marked
        self._simulated_regions[0].is_leader = True
        return self._simulated_regions[0]

    def update_leader_placement(
        self,
        target_region_id: str,
        is_dry_run: bool = False,
        operator_confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Move the database leader to the target region."""
        if is_dry_run:
            return {
                "success": True,
                "is_dry_run": True,
                "message": f"Dry-run execution: placement to {target_region_id} validated but no change made.",
            }

        if settings.operating_mode == OperatingMode.LIVE:
            # Live database migration with validation
            return self.yugabyte_adapter.execute_placement_change(
                target_region=target_region_id,
                operator_confirmed=operator_confirmed,
            )

        # Simulation mode leader migration
        found = False
        old_leader = None
        for r in self._simulated_regions:
            if r.is_leader:
                old_leader = r.name
                r.is_leader = False
            if r.id == target_region_id:
                r.is_leader = True
                found = True

        if not found:
            return {"success": False, "error": f"Region {target_region_id} not found in topology."}

        return {
            "success": True,
            "is_simulated": True,
            "old_leader": old_leader,
            "new_leader_id": target_region_id,
            "message": f"Simulated leader placement successfully moved from {old_leader} to {target_region_id}.",
        }

    def reset_simulation(self):
        """Reset simulated cluster topology to default initial state (Mumbai leader)."""
        self._simulated_regions = [copy.deepcopy(r) for r in DEFAULT_REGIONS]
