"""Transparent, explainable Carbon Calculation Engine for Follow-the-Green Leaders."""
from typing import Dict, Any, Optional
from ..models.entities import CarbonEstimate


class CarbonCalculator:
    """Calculates estimated energy consumption and carbon emissions for database workloads."""

    DEFAULT_ASSUMED_KWH_PER_TX = 0.000008  # 8 mWh per distributed SQL operation
    ASSUMPTIONS_DOC = (
        "Model covers estimated database server compute and storage energy only; "
        "it assumes 8 mWh (0.000008 kWh) per transactional operation based on typical "
        "cloud instance power profiles under active load. WAN network transfer is excluded. "
        "Values are modeled heuristics, NOT certified hardware measurements."
    )

    @staticmethod
    def calculate_workload_energy_kwh(
        tps: float,
        duration_seconds: float = 3600.0,
        energy_kwh_per_tx: Optional[float] = None,
    ) -> float:
        """Calculate total workload energy in kWh.

        Energy (kWh) = Number of transactions * Energy per transaction (kWh)
        where Number of transactions = TPS * duration_seconds
        """
        if tps < 0:
            raise ValueError("TPS cannot be negative")
        if duration_seconds < 0:
            raise ValueError("Duration cannot be negative")

        kwh_per_tx = energy_kwh_per_tx if energy_kwh_per_tx is not None else CarbonCalculator.DEFAULT_ASSUMED_KWH_PER_TX
        if kwh_per_tx < 0:
            raise ValueError("Energy per transaction cannot be negative")

        total_tx = tps * duration_seconds
        return total_tx * kwh_per_tx

    @staticmethod
    def calculate_emissions_gco2(
        energy_kwh: float,
        carbon_intensity_g_per_kwh: float,
    ) -> float:
        """Calculate total emissions in grams of CO2.

        Emissions (gCO2) = Electricity consumption (kWh) * Carbon intensity (gCO2/kWh)
        """
        if energy_kwh < 0:
            raise ValueError("Energy cannot be negative")
        if carbon_intensity_g_per_kwh < 0:
            raise ValueError("Carbon intensity cannot be negative")

        return energy_kwh * carbon_intensity_g_per_kwh

    @classmethod
    def compare_regions(
        cls,
        source_carbon_intensity: float,
        target_carbon_intensity: float,
        tps: float,
        duration_seconds: float = 3600.0,
        energy_kwh_per_tx: Optional[float] = None,
    ) -> CarbonEstimate:
        """Compare emissions between current and candidate regions over a time window (default 1 hour)."""
        tx_count = max(0.0, tps * duration_seconds)
        energy_kwh = cls.calculate_workload_energy_kwh(tps, duration_seconds, energy_kwh_per_tx)

        source_emissions = cls.calculate_baseline_emissions(source_carbon_intensity, tps, duration_seconds, energy_kwh_per_tx)
        target_emissions = cls.calculate_candidate_emissions(target_carbon_intensity, tps, duration_seconds, energy_kwh_per_tx)

        reduction_g = cls.calculate_absolute_emissions_difference(source_emissions, target_emissions)
        reduction_pct = cls.calculate_percentage_reduction(source_emissions, target_emissions)

        used_kwh_per_tx = (
            energy_kwh_per_tx if energy_kwh_per_tx is not None else cls.DEFAULT_ASSUMED_KWH_PER_TX
        )
        emissions_per_1k = cls.calculate_emissions_per_thousand_transactions(
            carbon_intensity_g_per_kwh=target_carbon_intensity,
            energy_kwh_per_tx=used_kwh_per_tx,
        )

        return CarbonEstimate(
            tx_count_per_hour=tx_count,
            total_energy_kwh_per_hour=energy_kwh,
            source_intensity_g_per_kwh=source_carbon_intensity,
            target_intensity_g_per_kwh=target_carbon_intensity,
            source_emissions_g_per_hour=source_emissions,
            target_emissions_g_per_hour=target_emissions,
            reduction_g_per_hour=reduction_g,
            reduction_percentage=round(reduction_pct, 2),
            assumed_kwh_per_tx=used_kwh_per_tx,
            assumptions_note=cls.ASSUMPTIONS_DOC,
        )

    @classmethod
    def calculate_baseline_emissions(
        cls,
        source_carbon_intensity: float,
        tps: float,
        duration_seconds: float = 3600.0,
        energy_kwh_per_tx: Optional[float] = None,
    ) -> float:
        """Calculate estimated baseline emissions for the current region over duration_seconds."""
        energy_kwh = cls.calculate_workload_energy_kwh(tps, duration_seconds, energy_kwh_per_tx)
        return cls.calculate_emissions_gco2(energy_kwh, source_carbon_intensity)

    @classmethod
    def calculate_candidate_emissions(
        cls,
        target_carbon_intensity: float,
        tps: float,
        duration_seconds: float = 3600.0,
        energy_kwh_per_tx: Optional[float] = None,
    ) -> float:
        """Calculate estimated candidate emissions for a target region over duration_seconds."""
        energy_kwh = cls.calculate_workload_energy_kwh(tps, duration_seconds, energy_kwh_per_tx)
        return cls.calculate_emissions_gco2(energy_kwh, target_carbon_intensity)

    @staticmethod
    def calculate_absolute_emissions_difference(
        baseline_emissions: float,
        candidate_emissions: float,
    ) -> float:
        """Calculate absolute emissions difference (baseline - candidate) in gCO2."""
        return baseline_emissions - candidate_emissions

    @staticmethod
    def calculate_percentage_reduction(
        baseline_emissions: float,
        candidate_emissions: float,
    ) -> float:
        """Calculate percentage emissions reduction relative to baseline."""
        if baseline_emissions <= 0:
            return 0.0
        diff = baseline_emissions - candidate_emissions
        return (diff / baseline_emissions) * 100.0

    @classmethod
    def calculate_emissions_per_thousand_transactions(
        cls,
        carbon_intensity_g_per_kwh: float,
        energy_kwh_per_tx: Optional[float] = None,
    ) -> float:
        """Calculate estimated emissions per 1,000 transactions in gCO2.

        1,000 transactions * (energy_kwh_per_tx) * carbon_intensity_g_per_kwh
        """
        kwh_per_tx = energy_kwh_per_tx if energy_kwh_per_tx is not None else cls.DEFAULT_ASSUMED_KWH_PER_TX
        if kwh_per_tx < 0:
            raise ValueError("Energy per transaction cannot be negative")
        if carbon_intensity_g_per_kwh < 0:
            raise ValueError("Carbon intensity cannot be negative")

        thousand_tx_energy = 1000.0 * kwh_per_tx
        return cls.calculate_emissions_gco2(thousand_tx_energy, carbon_intensity_g_per_kwh)
