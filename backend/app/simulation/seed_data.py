"""Deterministic simulation dataset and time-dependent carbon curves for Follow-the-Green Leaders."""
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ..models.entities import Region, WorkloadConfig


DEFAULT_REGIONS = [
    Region(
        id="ap-south-1",
        name="Mumbai",
        location="Asia Pacific (Mumbai)",
        carbon_intensity_g_per_kwh=600.0,
        electricity_price_usd_per_kwh=0.082,  # $82 / MWh
        base_write_latency_ms=25.0,
        is_healthy=True,
        is_leader=True,  # Initially leader in Mumbai
        replica_count=1,
        current_tps=1200.0,
        energy_mix="Coal Baseload + Solar (Midday)",
        data_source_label="SIMULATED DATA — NOT LIVE GRID MEASUREMENTS",
    ),
    Region(
        id="eu-central-1",
        name="Frankfurt",
        location="Europe Central (Frankfurt)",
        carbon_intensity_g_per_kwh=200.0,
        electricity_price_usd_per_kwh=0.145,  # $145 / MWh
        base_write_latency_ms=55.0,
        is_healthy=True,
        is_leader=False,
        replica_count=1,
        current_tps=0.0,
        energy_mix="Wind + Hydro + Nuclear (Clean Grid)",
        data_source_label="SIMULATED DATA — NOT LIVE GRID MEASUREMENTS",
    ),
    Region(
        id="us-east-1",
        name="Virginia",
        location="US East (N. Virginia)",
        carbon_intensity_g_per_kwh=400.0,
        electricity_price_usd_per_kwh=0.068,  # $68 / MWh
        base_write_latency_ms=35.0,
        is_healthy=True,
        is_leader=False,
        replica_count=1,
        current_tps=0.0,
        energy_mix="Natural Gas + Nuclear + Solar",
        data_source_label="SIMULATED DATA — NOT LIVE GRID MEASUREMENTS",
    ),
]

WORKLOAD_PROFILES: Dict[str, WorkloadConfig] = {
    "CHECKOUT": WorkloadConfig(
        id="CHECKOUT",
        name="E-Commerce Checkout & Payment Service",
        description="High-value transactional path with strict p99 write latency SLA (< 40ms). Prioritizes user experience over carbon savings.",
        tps=1200.0,
        assumed_kwh_per_tx=0.000008,
        max_p99_latency_ms=40.0,
        priority="PERFORMANCE_FIRST",
    ),
    "BACKGROUND_ANALYTICS": WorkloadConfig(
        id="BACKGROUND_ANALYTICS",
        name="Telemetry Aggregator & Financial Audit Batch",
        description="Asynchronous batch workload with high latency tolerance (budget 80ms). Ideal candidate to chase lowest-carbon electricity windows.",
        tps=450.0,
        assumed_kwh_per_tx=0.000015,
        max_p99_latency_ms=80.0,
        priority="CARBON_FLEXIBLE",
    ),
}


def get_simulated_carbon_intensity(region_id: str, timestamp: datetime) -> float:
    """Calculate deterministic diurnal variation for regional carbon intensity.

    Simulates solar peaks around 12:00 local time, evening peaks, and wind generation.
    Returns value in gCO2/kWh.
    """
    utc_hour = timestamp.hour + (timestamp.minute / 60.0)

    if region_id == "ap-south-1":  # Mumbai (UTC + 5:30)
        local_hour = (utc_hour + 5.5) % 24.0
        # Base 600, solar midday dip to ~460 at 12:00, evening peak to ~680 at 20:00
        diurnal_solar = 100.0 * math.sin((local_hour - 6) * math.pi / 12) if 6 <= local_hour <= 18 else 0.0
        evening_peak = 80.0 * math.exp(-((local_hour - 20) ** 2) / 8)
        base = 600.0 - (diurnal_solar * 1.4) + evening_peak
        return round(max(380.0, min(750.0, base)), 1)

    elif region_id == "eu-central-1":  # Frankfurt (UTC + 1 / UTC + 2)
        local_hour = (utc_hour + 2.0) % 24.0
        # Base 200, strong wind variation, solar dip
        diurnal = 40.0 * math.sin(local_hour * math.pi / 12)
        base = 200.0 + diurnal
        return round(max(110.0, min(310.0, base)), 1)

    elif region_id == "us-east-1":  # Virginia (UTC - 4)
        local_hour = (utc_hour - 4.0) % 24.0
        # Base 400, gas dispatch evening peak
        diurnal = 60.0 * math.sin((local_hour - 8) * math.pi / 12)
        base = 400.0 + (diurnal * 0.8)
        return round(max(290.0, min(510.0, base)), 1)

    return 350.0


def generate_time_series_data(time_window: str = "1h", points_count: int = 24) -> List[Dict[str, Any]]:
    """Generate deterministic simulated historical metrics for charts.

    Supports '15m', '1h', '24h'.
    """
    now = datetime.now(timezone.utc)
    if time_window == "15m":
        delta = timedelta(minutes=15)
        step = delta / points_count
    elif time_window == "1h":
        delta = timedelta(hours=1)
        step = delta / points_count
    else:  # 24h
        delta = timedelta(hours=24)
        step = delta / points_count

    start_time = now - delta
    records = []

    for i in range(points_count + 1):
        pt_time = start_time + (step * i)
        mumbai_ci = get_simulated_carbon_intensity("ap-south-1", pt_time)
        frankfurt_ci = get_simulated_carbon_intensity("eu-central-1", pt_time)
        virginia_ci = get_simulated_carbon_intensity("us-east-1", pt_time)

        # Baseline vs Optimized emissions (Checkout = 1200 TPS * 0.000008 kWh = 0.0096 kWh/s = 34.56 kWh/h)
        hourly_energy_kwh = 34.56
        # If leader stays in Mumbai:
        baseline_emissions_g = hourly_energy_kwh * mumbai_ci
        # If leader placed optimally (e.g. Frankfurt or Virginia according to budget):
        optimized_emissions_g = hourly_energy_kwh * min(mumbai_ci, virginia_ci)

        records.append({
            "timestamp": pt_time.isoformat(),
            "time_label": pt_time.strftime("%H:%M"),
            "mumbai_ci": mumbai_ci,
            "frankfurt_ci": frankfurt_ci,
            "virginia_ci": virginia_ci,
            "baseline_emissions_g": round(baseline_emissions_g, 1),
            "optimized_emissions_g": round(optimized_emissions_g, 1),
            "mumbai_p99_latency_ms": 25.0 + math.sin(i * 0.4) * 2.5,
            "frankfurt_p99_latency_ms": 55.0 + math.sin(i * 0.4 + 1) * 3.0,
            "virginia_p99_latency_ms": 35.0 + math.sin(i * 0.4 + 2) * 2.0,
            "data_source": "SIMULATED DATA — NOT LIVE GRID MEASUREMENTS",
        })

    return records
