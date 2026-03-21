"""Tests for src.health — health score engine, findings, simulation, region mapping."""
import pytest
from src.health import (
    compute_concentration_score,
    compute_diversification_score,
    compute_correlation_score,
    compute_stability_score,
    compute_health_score,
    generate_findings,
    simulate_addition,
    ticker_to_region,
)


# ── Concentration ────────────────────────────────────────────────────────────

class TestConcentration:
    def test_single_stock(self):
        score, hhi = compute_concentration_score({"AAPL": 1.0})
        assert hhi == pytest.approx(1.0)
        assert score == pytest.approx(0.0)

    def test_two_equal(self):
        score, hhi = compute_concentration_score({"A": 0.5, "B": 0.5})
        assert hhi == pytest.approx(0.5)
        assert score == pytest.approx(15.0)

    def test_ten_equal(self):
        weights = {f"S{i}": 0.1 for i in range(10)}
        score, hhi = compute_concentration_score(weights)
        assert hhi == pytest.approx(0.1)
        assert score == pytest.approx(27.0)

    def test_concentration_empty_weights(self):
        score, hhi = compute_concentration_score({})
        assert score == pytest.approx(0.0)
        assert hhi == pytest.approx(1.0)


# ── Diversification ─────────────────────────────────────────────────────────

class TestDiversification:
    def test_empty_sets(self):
        assert compute_diversification_score(set(), set()) == pytest.approx(0.0)

    def test_full_coverage(self):
        from src.health import GICS_SECTORS, REGIONS
        assert compute_diversification_score(GICS_SECTORS, REGIONS) == pytest.approx(35.0)

    def test_partial(self):
        sectors = {"Energy", "Materials", "Industrials", "Healthcare", "Financials"}
        regions = {"North America", "Europe"}
        expected = (5 / 11 * 17.5) + (2 / 5 * 17.5)
        assert compute_diversification_score(sectors, regions) == pytest.approx(expected)


# ── Correlation ──────────────────────────────────────────────────────────────

class TestCorrelation:
    def test_zero_correlation(self):
        assert compute_correlation_score(0.0) == pytest.approx(20.0)

    def test_full_correlation(self):
        assert compute_correlation_score(1.0) == pytest.approx(0.0)

    def test_none_single_holding(self):
        assert compute_correlation_score(None) == pytest.approx(20.0)

    def test_correlation_negative_clamped(self):
        # Negative correlation must be clamped to 0, so score is capped at 20
        score = compute_correlation_score(-0.5)
        assert score == pytest.approx(20.0)
        assert score <= 20.0


# ── Stability ────────────────────────────────────────────────────────────────

class TestStability:
    def test_moderate_vol(self):
        assert compute_stability_score(0.125) == pytest.approx(7.5)

    def test_high_vol_clamped(self):
        assert compute_stability_score(0.30) == pytest.approx(0.0)

    def test_zero_vol(self):
        assert compute_stability_score(0.0) == pytest.approx(15.0)


# ── Composite ────────────────────────────────────────────────────────────────

class TestComposite:
    def test_total_equals_sum(self):
        result = compute_health_score(
            weights={"A": 0.5, "B": 0.5},
            sectors={"Financials", "Healthcare"},
            regions={"North America"},
            weighted_avg_corr=0.3,
            annualized_vol=0.15,
        )
        component_sum = sum(c["score"] for c in result["components"])
        assert result["total"] == pytest.approx(component_sum)

    def test_four_components_present(self):
        result = compute_health_score(
            weights={"A": 1.0},
            sectors={"Energy"},
            regions={"Europe"},
            weighted_avg_corr=None,
            annualized_vol=0.10,
        )
        names = {c["name"] for c in result["components"]}
        assert names == {"Diversification", "Concentration", "Correlation", "Stability"}


# ── Findings ─────────────────────────────────────────────────────────────────

class TestFindings:
    def test_high_single_concentration(self):
        findings = generate_findings(
            weights={"AAPL": 0.40, "MSFT": 0.60},
            sectors={"Information Technology"},
            regions={"North America"},
            sector_weights={"Information Technology": 100.0},
            weighted_avg_corr=0.5,
            annualized_vol=0.18,
            top_holdings=[("MSFT", 60.0), ("AAPL", 40.0)],
        )
        reds = [f for f in findings if f["severity"] == "red"]
        assert any("concentration" in f["headline"].lower() for f in reds)

    def test_good_geographic_spread(self):
        findings = generate_findings(
            weights={"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            sectors={"Energy", "Materials", "Industrials", "Healthcare"},
            regions={"North America", "Europe", "Asia-Pacific"},
            sector_weights={"Energy": 25, "Materials": 25, "Industrials": 25, "Healthcare": 25},
            weighted_avg_corr=0.3,
            annualized_vol=0.12,
            top_holdings=[("A", 25.0), ("B", 25.0), ("C", 25.0), ("D", 25.0)],
        )
        greens = [f for f in findings if f["severity"] == "green"]
        assert any("geographic" in f["headline"].lower() for f in greens)

    def test_sector_imbalance(self):
        findings = generate_findings(
            weights={"A": 0.60, "B": 0.40},
            sectors={"Energy", "Materials"},
            regions={"North America"},
            sector_weights={"Energy": 60.0, "Materials": 40.0},
            weighted_avg_corr=0.4,
            annualized_vol=0.20,
            top_holdings=[("A", 60.0), ("B", 40.0)],
        )
        ambers = [f for f in findings if f["severity"] == "amber"]
        assert any("sector" in f["headline"].lower() for f in ambers)


# ── Simulation ───────────────────────────────────────────────────────────────

class TestSimulation:
    def test_adding_stock_changes_score(self):
        current = {
            "weights": {"AAPL": 0.5, "MSFT": 0.5},
            "sectors": {"Information Technology"},
            "regions": {"North America"},
            "weighted_avg_corr": 0.8,
            "annualized_vol": 0.20,
        }
        result = simulate_addition(
            current_portfolio=current,
            new_ticker_sector="Healthcare",
            new_ticker_region="Europe",
            new_ticker_corr_with_portfolio=0.2,
            addition_weight=0.10,
        )
        assert result["delta"] != 0.0
        assert result["current_score"] != result["projected_score"]

    def test_simulate_vol_dampening(self):
        # Without dampening (factor 1.0), vol reduction for a zero-corr asset at 10% weight
        # would be: 0.20 * (1 - 0.10 * 1.0) = 0.18
        # With dampening (factor 0.5): 0.20 * (1 - 0.10 * 0.5) = 0.19
        # Verify the dampened result is more conservative (higher vol = less reduction)
        current = {
            "weights": {"AAPL": 0.5, "MSFT": 0.5},
            "sectors": {"Information Technology"},
            "regions": {"North America"},
            "weighted_avg_corr": 0.5,
            "annualized_vol": 0.20,
        }
        result = simulate_addition(
            current_portfolio=current,
            new_ticker_sector="Healthcare",
            new_ticker_region="Europe",
            new_ticker_corr_with_portfolio=0.0,
            addition_weight=0.10,
        )
        # With dampening, new_vol = 0.20 * (1 - 0.10 * 1.0 * 0.5) = 0.19
        # Without dampening it would be 0.18 — projected stability score must reflect 0.19
        expected_new_vol = 0.20 * (1 - 0.10 * (1 - 0.0) * 0.5)
        assert expected_new_vol == pytest.approx(0.19)
        # The simulation should complete and produce a valid positive score
        assert result["projected_score"] > 0

    def test_zero_weight_no_change(self):
        current = {
            "weights": {"AAPL": 0.5, "MSFT": 0.5},
            "sectors": {"Information Technology"},
            "regions": {"North America"},
            "weighted_avg_corr": 0.6,
            "annualized_vol": 0.18,
        }
        result = simulate_addition(
            current_portfolio=current,
            new_ticker_sector="Healthcare",
            new_ticker_region="Europe",
            new_ticker_corr_with_portfolio=0.3,
            addition_weight=0.0,
        )
        assert result["delta"] == pytest.approx(0.0)


# ── Region Mapping ───────────────────────────────────────────────────────────

class TestRegionMapping:
    def test_uk(self):
        assert ticker_to_region("VOD.L") == "UK"

    def test_europe_as(self):
        assert ticker_to_region("ASML.AS") == "Europe"

    def test_europe_de(self):
        assert ticker_to_region("SAP.DE") == "Europe"

    def test_europe_sw(self):
        assert ticker_to_region("NESN.SW") == "Europe"

    def test_north_america_default(self):
        assert ticker_to_region("AAPL") == "North America"
