"""Unit tests for the Carbon Calculation Engine."""
import pytest
from app.services.carbon_calculator import CarbonCalculator


def test_workload_energy_calculation():
    """Verify energy (kWh) = TPS * duration * kWh_per_tx."""
    # 1000 TPS, 1 hour (3600s), 0.000008 kWh/tx
    # Total TX = 3,600,000 tx * 0.000008 = 28.8 kWh
    energy = CarbonCalculator.calculate_workload_energy_kwh(
        tps=1000.0, duration_seconds=3600.0, energy_kwh_per_tx=0.000008
    )
    assert pytest.approx(energy, rel=1e-4) == 28.8


def test_zero_transactions_and_zero_energy():
    """Zero TPS or zero energy yields zero emissions."""
    energy = CarbonCalculator.calculate_workload_energy_kwh(tps=0.0, duration_seconds=3600.0)
    assert energy == 0.0

    emissions = CarbonCalculator.calculate_emissions_gco2(energy_kwh=0.0, carbon_intensity_g_per_kwh=500.0)
    assert emissions == 0.0


def test_invalid_negative_inputs():
    """Negative inputs must raise ValueError."""
    with pytest.raises(ValueError, match="TPS cannot be negative"):
        CarbonCalculator.calculate_workload_energy_kwh(tps=-10.0)

    with pytest.raises(ValueError, match="Duration cannot be negative"):
        CarbonCalculator.calculate_workload_energy_kwh(tps=100.0, duration_seconds=-50.0)

    with pytest.raises(ValueError, match="Carbon intensity cannot be negative"):
        CarbonCalculator.calculate_emissions_gco2(energy_kwh=10.0, carbon_intensity_g_per_kwh=-100.0)


def test_compare_regions_reduction_percentage():
    """Verify reduction math: (source - target) / source * 100."""
    # Source: Mumbai (600 gCO2/kWh), Target: Frankfurt (200 gCO2/kWh)
    # Reduction: 400 gCO2 / 600 gCO2 = 66.67%
    estimate = CarbonCalculator.compare_regions(
        source_carbon_intensity=600.0,
        target_carbon_intensity=200.0,
        tps=1000.0,
        duration_seconds=3600.0,
        energy_kwh_per_tx=0.00001,
    )
    assert estimate.source_intensity_g_per_kwh == 600.0
    assert estimate.target_intensity_g_per_kwh == 200.0
    assert pytest.approx(estimate.reduction_percentage, 0.01) == 66.67
    assert estimate.reduction_g_per_hour > 0
    assert "heuristic" in estimate.assumptions_note.lower()


def test_compare_regions_zero_source_emissions():
    """Avoid division by zero if source intensity is zero."""
    estimate = CarbonCalculator.compare_regions(
        source_carbon_intensity=0.0,
        target_carbon_intensity=0.0,
        tps=500.0,
    )
    assert estimate.reduction_percentage == 0.0
    assert estimate.source_emissions_g_per_hour == 0.0


def test_baseline_and_candidate_emissions_methods():
    """Verify separate baseline and candidate emission calculations."""
    # 500 TPS for 3600 seconds = 1,800,000 tx
    # At 0.00001 kWh/tx = 18 kWh
    # Mumbai (600 g/kWh) -> 10,800 gCO2
    # Frankfurt (200 g/kWh) -> 3,600 gCO2
    baseline = CarbonCalculator.calculate_baseline_emissions(
        source_carbon_intensity=600.0,
        tps=500.0,
        duration_seconds=3600.0,
        energy_kwh_per_tx=0.00001,
    )
    candidate = CarbonCalculator.calculate_candidate_emissions(
        target_carbon_intensity=200.0,
        tps=500.0,
        duration_seconds=3600.0,
        energy_kwh_per_tx=0.00001,
    )
    assert pytest.approx(baseline, rel=1e-4) == 10800.0
    assert pytest.approx(candidate, rel=1e-4) == 3600.0

    diff = CarbonCalculator.calculate_absolute_emissions_difference(baseline, candidate)
    assert pytest.approx(diff, rel=1e-4) == 7200.0

    pct = CarbonCalculator.calculate_percentage_reduction(baseline, candidate)
    assert pytest.approx(pct, rel=1e-4) == 66.6667


def test_emissions_per_thousand_transactions():
    """Verify emissions per 1,000 transactions calculation."""
    # 1,000 tx * 0.000008 kWh/tx = 0.008 kWh
    # At 500 gCO2/kWh = 4.0 gCO2
    per_1k = CarbonCalculator.calculate_emissions_per_thousand_transactions(
        carbon_intensity_g_per_kwh=500.0,
        energy_kwh_per_tx=0.000008,
    )
    assert pytest.approx(per_1k, rel=1e-4) == 4.0

    # Test error handling on negative inputs
    with pytest.raises(ValueError, match="Energy per transaction cannot be negative"):
        CarbonCalculator.calculate_emissions_per_thousand_transactions(
            carbon_intensity_g_per_kwh=500.0,
            energy_kwh_per_tx=-0.001,
        )

    with pytest.raises(ValueError, match="Carbon intensity cannot be negative"):
        CarbonCalculator.calculate_emissions_per_thousand_transactions(
            carbon_intensity_g_per_kwh=-10.0,
        )

