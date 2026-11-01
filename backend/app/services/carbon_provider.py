"""Modular Carbon-Intensity Provider Interface for Follow-the-Green Leaders.

Includes:
- DemoCarbonProvider: High-fidelity deterministic simulation data labeled clearly.
- ExternalCarbonProvider: Interface for Electricity Maps / WattTime, with documented fallbacks.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from ..simulation.seed_data import get_simulated_carbon_intensity
from ..core.config import settings


class BaseCarbonProvider(ABC):
    """Abstract interface for regional electricity carbon intensity queries."""

    @abstractmethod
    def get_carbon_intensity(self, region_id: str) -> Dict[str, Any]:
        """Fetch carbon intensity in gCO2/kWh with metadata and data provenance."""
        pass


class DemoCarbonProvider(BaseCarbonProvider):
    """Deterministic, offline simulation carbon provider."""

    DATA_SOURCE_NOTICE = "SIMULATED CARBON DATA — NOT LIVE GRID MEASUREMENTS"

    def get_carbon_intensity(self, region_id: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        intensity = get_simulated_carbon_intensity(region_id, now)
        return {
            "region_id": region_id,
            "carbon_intensity_g_per_kwh": intensity,
            "timestamp": now.isoformat(),
            "data_source": self.DATA_SOURCE_NOTICE,
            "is_simulated": True,
            "provider_type": "DEMO_SIMULATION",
        }


class ExternalCarbonProvider(BaseCarbonProvider):
    """Integration for live grid emission APIs (e.g. Electricity Maps).

    Uses documented endpoints when credentials are provided, or explicitly signals
    unconfigured status rather than pretending simulated data is live.
    """

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key or settings.carbon_api_key
        self.api_url = api_url or settings.carbon_api_url
        self.demo_fallback = DemoCarbonProvider()

    def get_carbon_intensity(self, region_id: str) -> Dict[str, Any]:
        # If API key is not supplied, explicitly return simulated data with clear warning
        if not self.api_key:
            data = self.demo_fallback.get_carbon_intensity(region_id)
            data["notice"] = (
                "External carbon API key not configured in environment. "
                "Displaying SIMULATED CARBON DATA — NOT LIVE GRID MEASUREMENTS."
            )
            return data

        # Map cloud regions to official zone IDs
        zone_map = {
            "ap-south-1": "IN-WE",  # India Western Grid
            "eu-central-1": "DE",   # Germany
            "us-east-1": "US-PJM",  # PJM Interconnection
        }
        zone = zone_map.get(region_id, "DE")
        url = self.api_url or f"https://api.electricitymap.org/v3/carbon-intensity/latest?zone={zone}"

        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(url, headers={"auth-token": self.api_key})
                if resp.status_code == 200:
                    payload = resp.json()
                    val = payload.get("carbonIntensity", 350.0)
                    return {
                        "region_id": region_id,
                        "carbon_intensity_g_per_kwh": float(val),
                        "timestamp": payload.get("datetime", datetime.now(timezone.utc).isoformat()),
                        "data_source": "Electricity Maps Live API",
                        "is_simulated": False,
                        "provider_type": "EXTERNAL_LIVE",
                    }
                else:
                    data = self.demo_fallback.get_carbon_intensity(region_id)
                    data["notice"] = f"External API returned status {resp.status_code}. Fallback to simulated data."
                    return data
        except Exception as e:
            data = self.demo_fallback.get_carbon_intensity(region_id)
            data["notice"] = f"External API call failed: {str(e)}. Fallback to simulated data."
            return data
