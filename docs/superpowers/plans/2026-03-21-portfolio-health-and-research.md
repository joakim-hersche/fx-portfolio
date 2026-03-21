# Portfolio Health & Stock Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Risk & Analytics tab with a narrative-driven Portfolio Health tab, and add a new Stock Research tab for evaluating any ticker with portfolio fit analysis.

**Architecture:** The health score engine and findings generator live in `src/health.py` (pure computation, no UI). The Portfolio Health UI (`src/ui/health.py`) replaces `src/ui/risk.py`, reusing existing data-fetch patterns and moving current metrics into collapsible sections. The Research tab (`src/ui/research.py`) is a new UI module with its own search, fundamentals display, and portfolio fit preview. News fetching is added to `src/data_fetch.py`.

**Tech Stack:** NiceGUI, yfinance, pandas, numpy (all existing)

**Spec:** `docs/superpowers/specs/2026-03-20-portfolio-health-and-research-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/health.py` | Create | Health score computation, findings generation, portfolio fit simulation. Pure functions, no UI. |
| `src/ui/health.py` | Create | Portfolio Health tab UI — score display, findings cards, sector exposure, disclaimer, collapsible metrics, rebalancing calculator. |
| `src/ui/research.py` | Create | Stock Research tab UI — search, company header, fundamentals, portfolio fit preview, price chart, peers, news. |
| `src/data_fetch.py` | Modify | Add `fetch_ticker_news()`, `fetch_sector_peers()`, `fetch_sector_medians()`. |
| `src/ui/risk.py` | Delete | Replaced by `src/ui/health.py`. |
| `main.py` | Modify | Tab bar: rename "Risk & Analytics" → "Portfolio Health", add "Research". Update imports and `_build_tab`. |
| `src/ui/guide.py` | Modify | Update documentation for new tabs. |
| `tests/test_health.py` | Create | Unit tests for health score, findings, portfolio fit simulation. |
| `tests/test_data_fetch.py` | Modify | Add tests for `fetch_ticker_news()`, `fetch_sector_peers()`. |

---

## Task 1: Health Score Engine — Core Computation

**Files:**
- Create: `src/health.py`
- Test: `tests/test_health.py`

This task builds the pure computation layer: health score from four components (diversification, concentration, correlation, stability), with no UI dependencies.

- [ ] **Step 1: Write failing tests for HHI and concentration score**

```python
# tests/test_health.py
"""Tests for src.health — health score engine."""
import pytest


def test_hhi_single_stock():
    """Single stock = HHI of 1.0, concentration score = 0."""
    from src.health import compute_concentration_score
    score, hhi = compute_concentration_score({"AAPL": 1.0})
    assert hhi == 1.0
    assert score == 0.0


def test_hhi_equal_weight_two():
    """Two equal stocks = HHI of 0.5."""
    from src.health import compute_concentration_score
    score, hhi = compute_concentration_score({"AAPL": 0.5, "MSFT": 0.5})
    assert hhi == pytest.approx(0.5)
    assert score == pytest.approx(15.0)  # (1 - 0.5) * 30


def test_hhi_equal_weight_ten():
    """Ten equal stocks = HHI of 0.1, near-perfect score."""
    from src.health import compute_concentration_score
    weights = {f"T{i}": 0.1 for i in range(10)}
    score, hhi = compute_concentration_score(weights)
    assert hhi == pytest.approx(0.1)
    assert score == pytest.approx(27.0)  # (1 - 0.1) * 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.health'`

- [ ] **Step 3: Implement concentration score**

```python
# src/health.py
"""Portfolio health score engine.

Pure computation — no UI, no yfinance, no caching.
All functions take pre-computed data (weights, sectors, correlations)
and return scores + metadata.
"""


# ── Constants ────────────────────────────────────────────────────────────────

GICS_SECTORS = [
    "Energy", "Materials", "Industrials", "Consumer Discretionary",
    "Consumer Staples", "Healthcare", "Financials",
    "Information Technology", "Communication Services", "Utilities",
    "Real Estate",
]

REGIONS = ["North America", "Europe", "UK", "Asia-Pacific", "Emerging Markets"]

# Component weights (must sum to 100)
W_DIVERSIFICATION = 35
W_CONCENTRATION = 30
W_CORRELATION = 20
W_STABILITY = 15

# Stability benchmark cap (25% annualized volatility)
STABILITY_VOL_CAP = 0.25


def compute_concentration_score(
    weights: dict[str, float],
) -> tuple[float, float]:
    """Compute concentration score from portfolio weights.

    Parameters
    ----------
    weights : dict
        Mapping of ticker -> portfolio weight as decimal (0.0–1.0, summing to ~1.0).

    Returns
    -------
    (score, hhi) : tuple[float, float]
        score: 0–30 points.
        hhi: Herfindahl-Hirschman Index (sum of squared weights).
    """
    if not weights:
        return 0.0, 1.0
    hhi = sum(w ** 2 for w in weights.values())
    score = (1 - hhi) * W_CONCENTRATION
    return round(score, 1), round(hhi, 4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Write failing tests for diversification score**

```python
# Append to tests/test_health.py

def test_diversification_no_sectors():
    """No sectors or regions = 0 score."""
    from src.health import compute_diversification_score
    score = compute_diversification_score(sectors=set(), regions=set())
    assert score == 0.0


def test_diversification_full_coverage():
    """All 11 sectors + all 5 regions = full 35 points."""
    from src.health import compute_diversification_score, GICS_SECTORS, REGIONS
    score = compute_diversification_score(
        sectors=set(GICS_SECTORS), regions=set(REGIONS),
    )
    assert score == pytest.approx(35.0)


def test_diversification_partial():
    """5 sectors, 2 regions."""
    from src.health import compute_diversification_score
    score = compute_diversification_score(
        sectors={"Energy", "Healthcare", "Financials", "IT", "Utilities"},
        regions={"North America", "Europe"},
    )
    # (5/11 * 17.5) + (2/5 * 17.5) = 7.954 + 7.0 = 14.954
    assert score == pytest.approx(14.95, abs=0.1)
```

- [ ] **Step 6: Implement diversification score**

```python
# Add to src/health.py

def compute_diversification_score(
    sectors: set[str],
    regions: set[str],
) -> float:
    """Compute diversification score from sector and geographic coverage.

    Returns score: 0–35 points.
    """
    sector_score = len(sectors) / len(GICS_SECTORS) * (W_DIVERSIFICATION / 2)
    region_score = len(regions) / len(REGIONS) * (W_DIVERSIFICATION / 2)
    return round(sector_score + region_score, 1)
```

- [ ] **Step 7: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 6 PASSED

- [ ] **Step 8: Write failing tests for correlation and stability scores**

```python
# Append to tests/test_health.py

def test_correlation_score_zero_correlation():
    """Uncorrelated assets = full 20 points."""
    from src.health import compute_correlation_score
    score = compute_correlation_score(weighted_avg_corr=0.0)
    assert score == pytest.approx(20.0)


def test_correlation_score_perfect_correlation():
    """Perfectly correlated = 0 points."""
    from src.health import compute_correlation_score
    score = compute_correlation_score(weighted_avg_corr=1.0)
    assert score == pytest.approx(0.0)


def test_correlation_score_single_holding():
    """Single holding (no pairs) = full marks."""
    from src.health import compute_correlation_score
    score = compute_correlation_score(weighted_avg_corr=None)
    assert score == pytest.approx(20.0)


def test_stability_score_low_vol():
    """12.5% vol = half of benchmark cap = ~7.5 points."""
    from src.health import compute_stability_score
    score = compute_stability_score(annualized_vol=0.125)
    assert score == pytest.approx(7.5)


def test_stability_score_high_vol():
    """Vol at or above 25% cap = 0 points."""
    from src.health import compute_stability_score
    score = compute_stability_score(annualized_vol=0.30)
    assert score == 0.0


def test_stability_score_zero_vol():
    """Zero vol = full 15 points."""
    from src.health import compute_stability_score
    score = compute_stability_score(annualized_vol=0.0)
    assert score == pytest.approx(15.0)
```

- [ ] **Step 9: Implement correlation and stability scores**

```python
# Add to src/health.py

def compute_correlation_score(
    weighted_avg_corr: float | None,
) -> float:
    """Compute correlation score.

    Parameters
    ----------
    weighted_avg_corr : float or None
        Weight-adjusted average pairwise correlation. None if < 2 holdings.

    Returns score: 0–20 points.
    """
    if weighted_avg_corr is None:
        return float(W_CORRELATION)
    corr = max(0.0, min(1.0, weighted_avg_corr))
    return round((1 - corr) * W_CORRELATION, 1)


def compute_stability_score(annualized_vol: float) -> float:
    """Compute stability score from portfolio-level annualized volatility.

    Returns score: 0–15 points.
    """
    if annualized_vol <= 0:
        return float(W_STABILITY)
    return round(max(0.0, W_STABILITY * (1 - annualized_vol / STABILITY_VOL_CAP)), 1)
```

- [ ] **Step 10: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 12 PASSED

- [ ] **Step 11: Write failing test for composite health score**

```python
# Append to tests/test_health.py

def test_composite_health_score():
    """Composite score sums all four components."""
    from src.health import compute_health_score

    result = compute_health_score(
        weights={"AAPL": 0.5, "MSFT": 0.5},
        sectors={"Information Technology"},
        regions={"North America"},
        weighted_avg_corr=0.5,
        annualized_vol=0.15,
    )
    assert "total" in result
    assert "components" in result
    assert len(result["components"]) == 4

    # Verify total = sum of component scores
    component_sum = sum(c["score"] for c in result["components"])
    assert result["total"] == pytest.approx(component_sum)

    # Verify component names
    names = {c["name"] for c in result["components"]}
    assert names == {"Diversification", "Concentration", "Correlation", "Stability"}
```

- [ ] **Step 12: Implement composite health score**

```python
# Add to src/health.py

def compute_health_score(
    weights: dict[str, float],
    sectors: set[str],
    regions: set[str],
    weighted_avg_corr: float | None,
    annualized_vol: float,
) -> dict:
    """Compute composite portfolio health score.

    Returns dict with:
        total: float (0–100)
        components: list of dicts with name, score, max_score, details
    """
    conc_score, hhi = compute_concentration_score(weights)
    div_score = compute_diversification_score(sectors, regions)
    corr_score = compute_correlation_score(weighted_avg_corr)
    stab_score = compute_stability_score(annualized_vol)

    effective_positions = round(1 / hhi, 1) if hhi > 0 else len(weights)

    components = [
        {
            "name": "Diversification",
            "score": div_score,
            "max_score": W_DIVERSIFICATION,
            "details": {
                "sectors_held": len(sectors),
                "sectors_total": len(GICS_SECTORS),
                "regions_held": len(regions),
                "regions_total": len(REGIONS),
            },
        },
        {
            "name": "Concentration",
            "score": conc_score,
            "max_score": W_CONCENTRATION,
            "details": {
                "hhi": hhi,
                "effective_positions": effective_positions,
            },
        },
        {
            "name": "Correlation",
            "score": corr_score,
            "max_score": W_CORRELATION,
            "details": {
                "weighted_avg_corr": weighted_avg_corr,
            },
        },
        {
            "name": "Stability",
            "score": stab_score,
            "max_score": W_STABILITY,
            "details": {
                "annualized_vol": round(annualized_vol, 4),
                "benchmark_cap": STABILITY_VOL_CAP,
            },
        },
    ]

    total = round(sum(c["score"] for c in components), 1)

    return {"total": total, "components": components}
```

- [ ] **Step 13: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 13 PASSED

- [ ] **Step 14: Commit**

```bash
git add src/health.py tests/test_health.py
git commit -m "feat: health score engine with four components"
```

---

## Task 2: Findings Generator

**Files:**
- Modify: `src/health.py`
- Test: `tests/test_health.py`

Generates plain-language diagnostic findings based on portfolio data and health score thresholds.

- [ ] **Step 1: Write failing tests for findings**

```python
# Append to tests/test_health.py

def test_finding_high_single_concentration():
    """Flag when a single holding exceeds 25%."""
    from src.health import generate_findings
    findings = generate_findings(
        weights={"AAPL": 0.40, "MSFT": 0.30, "GOOG": 0.30},
        sectors={"IT"},
        regions={"North America"},
        sector_weights={"Information Technology": 100.0},
        weighted_avg_corr=0.3,
        annualized_vol=0.15,
        top_holdings=[("AAPL", 40.0), ("MSFT", 30.0), ("GOOG", 30.0)],
    )
    severities = [f["severity"] for f in findings]
    assert "red" in severities
    # At least one finding about concentration
    assert any("concentration" in f["headline"].lower() or "AAPL" in f["body"] for f in findings)


def test_finding_good_geographic_spread():
    """Green finding when 3+ regions covered."""
    from src.health import generate_findings
    findings = generate_findings(
        weights={"AAPL": 0.5, "HSBA.L": 0.25, "ASML.AS": 0.25},
        sectors={"IT", "Financials"},
        regions={"North America", "UK", "Europe"},
        sector_weights={"Information Technology": 50.0, "Financials": 50.0},
        weighted_avg_corr=0.3,
        annualized_vol=0.15,
        top_holdings=[("AAPL", 50.0), ("HSBA.L", 25.0), ("ASML.AS", 25.0)],
    )
    green_findings = [f for f in findings if f["severity"] == "green"]
    assert len(green_findings) >= 1
    assert any("geographic" in f["headline"].lower() for f in green_findings)


def test_finding_sector_imbalance():
    """Amber finding when one sector exceeds 50%."""
    from src.health import generate_findings
    findings = generate_findings(
        weights={"AAPL": 0.4, "MSFT": 0.3, "JNJ": 0.3},
        sectors={"Information Technology", "Healthcare"},
        regions={"North America"},
        sector_weights={"Information Technology": 70.0, "Healthcare": 30.0},
        weighted_avg_corr=0.5,
        annualized_vol=0.15,
        top_holdings=[("AAPL", 40.0), ("MSFT", 30.0), ("JNJ", 30.0)],
    )
    amber_or_red = [f for f in findings if f["severity"] in ("amber", "red")]
    assert any("sector" in f["headline"].lower() for f in amber_or_red)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py::test_finding_high_single_concentration tests/test_health.py::test_finding_good_geographic_spread tests/test_health.py::test_finding_sector_imbalance -v`
Expected: FAIL — `ImportError: cannot import name 'generate_findings'`

- [ ] **Step 3: Implement findings generator**

```python
# Add to src/health.py

def generate_findings(
    weights: dict[str, float],
    sectors: set[str],
    regions: set[str],
    sector_weights: dict[str, float],
    weighted_avg_corr: float | None,
    annualized_vol: float,
    top_holdings: list[tuple[str, float]],
) -> list[dict]:
    """Generate plain-language diagnostic findings.

    Parameters
    ----------
    weights : dict
        ticker -> weight as decimal (0–1).
    sectors, regions : set
        Distinct sectors/regions in portfolio.
    sector_weights : dict
        sector_name -> total portfolio weight %.
    weighted_avg_corr : float or None
        Average pairwise correlation.
    annualized_vol : float
        Portfolio-level annualized vol (decimal).
    top_holdings : list[(ticker, weight_%)]
        Holdings sorted by weight descending, weight as percentage.

    Returns list of dicts: {severity, headline, body}
    """
    findings: list[dict] = []

    # Concentration: single holding > 25%
    for ticker, pct in top_holdings:
        if pct > 25:
            findings.append({
                "severity": "red",
                "headline": "High concentration risk",
                "body": (
                    f"{ticker} accounts for {pct:.0f}% of your portfolio. "
                    f"A 20% drop in {ticker} alone would reduce your portfolio by ~{pct * 0.2:.0f}%."
                ),
            })
            break  # Only report once (top holding)

    # Concentration: top 3 > 65%
    if len(top_holdings) >= 3:
        top3_pct = sum(pct for _, pct in top_holdings[:3])
        if top3_pct > 65:
            top3_names = ", ".join(t for t, _ in top_holdings[:3])
            findings.append({
                "severity": "red" if top3_pct > 80 else "amber",
                "headline": "High concentration risk",
                "body": (
                    f"Your top 3 holdings ({top3_names}) account for {top3_pct:.0f}% "
                    f"of portfolio value. A 20% drop in these would reduce your "
                    f"portfolio by ~{top3_pct * 0.2:.0f}%."
                ),
            })

    # Sector imbalance: any sector > 50%
    for sector, pct in sector_weights.items():
        if pct > 50:
            findings.append({
                "severity": "amber",
                "headline": "Sector imbalance",
                "body": (
                    f"{pct:.0f}% of your portfolio is in {sector}. "
                    f"Your returns are heavily tied to this sector's performance."
                ),
            })
            break

    # Sector gaps: > 3 GICS sectors with 0%
    missing_sectors = set(GICS_SECTORS) - sectors
    if len(missing_sectors) > 3:
        examples = ", ".join(sorted(missing_sectors)[:4])
        findings.append({
            "severity": "amber",
            "headline": "Limited sector coverage",
            "body": (
                f"No exposure to {len(missing_sectors)} of 11 major sectors "
                f"({examples}). Broader sector coverage reduces single-industry risk."
            ),
        })

    # Correlation: weighted avg > 0.6
    if weighted_avg_corr is not None and weighted_avg_corr > 0.6:
        findings.append({
            "severity": "amber",
            "headline": "High internal correlation",
            "body": (
                f"Average pairwise correlation is {weighted_avg_corr:.2f}. "
                f"Your holdings tend to move together — when one drops, most "
                f"others likely will too."
            ),
        })

    # Geographic spread: 3+ regions (positive)
    if len(regions) >= 3:
        region_list = ", ".join(sorted(regions))
        findings.append({
            "severity": "green",
            "headline": "Good geographic spread",
            "body": (
                f"Holdings span {len(regions)} regions ({region_list}). "
                f"Multi-market exposure reduces single-country risk."
            ),
        })

    # Stability: vol below S&P 500 historical avg (~16%)
    if annualized_vol < 0.16:
        findings.append({
            "severity": "green",
            "headline": "Below-market volatility",
            "body": (
                f"Portfolio volatility is {annualized_vol * 100:.1f}%, below the "
                f"S&P 500 historical average of ~16%. Lower volatility means "
                f"smaller day-to-day swings."
            ),
        })

    return findings
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 16 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/health.py tests/test_health.py
git commit -m "feat: findings generator for portfolio diagnostics"
```

---

## Task 3: Portfolio Fit Simulation

**Files:**
- Modify: `src/health.py`
- Test: `tests/test_health.py`

Simulates adding a hypothetical stock to the portfolio and computes the health score delta.

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_health.py

def test_simulate_addition_changes_score():
    """Adding a stock to a concentrated portfolio should change the score."""
    from src.health import simulate_addition

    current = {
        "weights": {"AAPL": 0.7, "MSFT": 0.3},
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
        addition_weight=0.05,
    )
    assert "current_score" in result
    assert "projected_score" in result
    assert "delta" in result
    assert "impacts" in result
    # Adding healthcare to an all-tech portfolio should help
    assert result["delta"] > 0


def test_simulate_addition_zero_weight():
    """Adding at 0% weight should not change score."""
    from src.health import simulate_addition
    current = {
        "weights": {"AAPL": 0.5, "MSFT": 0.5},
        "sectors": {"Information Technology"},
        "regions": {"North America"},
        "weighted_avg_corr": 0.5,
        "annualized_vol": 0.15,
    }
    result = simulate_addition(
        current_portfolio=current,
        new_ticker_sector="Healthcare",
        new_ticker_region="Europe",
        new_ticker_corr_with_portfolio=0.2,
        addition_weight=0.0,
    )
    assert result["delta"] == pytest.approx(0.0, abs=0.1)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py::test_simulate_addition_changes_score tests/test_health.py::test_simulate_addition_zero_weight -v`
Expected: FAIL

- [ ] **Step 3: Implement simulate_addition**

```python
# Add to src/health.py

def simulate_addition(
    current_portfolio: dict,
    new_ticker_sector: str | None,
    new_ticker_region: str | None,
    new_ticker_corr_with_portfolio: float | None,
    addition_weight: float,
) -> dict:
    """Simulate adding a stock and compute health score change.

    Parameters
    ----------
    current_portfolio : dict
        Keys: weights, sectors, regions, weighted_avg_corr, annualized_vol
    new_ticker_sector : str or None
        GICS sector of the new stock.
    new_ticker_region : str or None
        Geographic region.
    new_ticker_corr_with_portfolio : float or None
        Correlation of the new stock with the existing portfolio.
    addition_weight : float
        Weight (0–1) to assign to the new stock (existing weights scaled down).

    Returns dict with: current_score, projected_score, delta, impacts
    """
    weights = current_portfolio["weights"]
    sectors = current_portfolio["sectors"]
    regions = current_portfolio["regions"]
    avg_corr = current_portfolio["weighted_avg_corr"]
    vol = current_portfolio["annualized_vol"]

    # Current score
    current = compute_health_score(weights, sectors, regions, avg_corr, vol)
    current_score = current["total"]

    if addition_weight <= 0:
        return {
            "current_score": current_score,
            "projected_score": current_score,
            "delta": 0.0,
            "impacts": [],
        }

    # Scale down existing weights
    scale = 1.0 - addition_weight
    new_weights = {t: w * scale for t, w in weights.items()}
    new_weights["__new__"] = addition_weight

    # Update sectors and regions
    new_sectors = set(sectors)
    if new_ticker_sector:
        new_sectors.add(new_ticker_sector)

    new_regions = set(regions)
    if new_ticker_region:
        new_regions.add(new_ticker_region)

    # Approximate new correlation: blend existing with new stock's correlation
    if avg_corr is not None and new_ticker_corr_with_portfolio is not None:
        # Weighted blend: existing portfolio correlation stays, new pair adds
        new_corr = avg_corr * (1 - addition_weight) + new_ticker_corr_with_portfolio * addition_weight
    else:
        new_corr = avg_corr

    # Approximate new volatility (simplified: lower if new stock is less correlated)
    if new_ticker_corr_with_portfolio is not None:
        # Adding a less-correlated asset reduces portfolio vol
        new_vol = vol * (1 - addition_weight * (1 - new_ticker_corr_with_portfolio) * 0.5)
    else:
        new_vol = vol

    projected = compute_health_score(new_weights, new_sectors, new_regions, new_corr, new_vol)
    projected_score = projected["total"]

    # Build impact descriptions
    impacts = []
    if new_ticker_sector and new_ticker_sector not in sectors:
        impacts.append(f"Adds {new_ticker_sector} exposure (currently 0%)")
    if new_ticker_corr_with_portfolio is not None and new_ticker_corr_with_portfolio < 0.4:
        impacts.append(f"Low correlation ({new_ticker_corr_with_portfolio:.2f}) with existing holdings")
    if new_vol < vol:
        vol_reduction = (vol - new_vol) / vol * 100
        impacts.append(f"Reduces portfolio volatility by ~{vol_reduction:.0f}%")
    if new_ticker_region and new_ticker_region not in regions:
        impacts.append(f"Adds {new_ticker_region} geographic diversification")

    return {
        "current_score": current_score,
        "projected_score": projected_score,
        "delta": round(projected_score - current_score, 1),
        "impacts": impacts,
    }
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 18 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/health.py tests/test_health.py
git commit -m "feat: portfolio fit simulation for stock research"
```

---

## Task 4: Region Mapping Helper

**Files:**
- Modify: `src/health.py`
- Test: `tests/test_health.py`

Maps ticker to geographic region using suffix heuristic + yfinance country field.

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_health.py

def test_region_from_suffix_uk():
    from src.health import ticker_to_region
    assert ticker_to_region("HSBA.L") == "UK"


def test_region_from_suffix_europe():
    from src.health import ticker_to_region
    assert ticker_to_region("ASML.AS") == "Europe"
    assert ticker_to_region("SAP.DE") == "Europe"


def test_region_default_north_america():
    from src.health import ticker_to_region
    assert ticker_to_region("AAPL") == "North America"


def test_region_from_suffix_switzerland():
    """Swiss stocks map to Europe."""
    from src.health import ticker_to_region
    assert ticker_to_region("NESN.SW") == "Europe"
```

- [ ] **Step 2: Implement region mapping**

```python
# Add to src/health.py

_SUFFIX_REGION = {
    ".L": "UK",
    ".DE": "Europe",
    ".PA": "Europe",
    ".AS": "Europe",
    ".MC": "Europe",
    ".SW": "Europe",
    ".ST": "Europe",
    ".HK": "Asia-Pacific",
    ".T": "Asia-Pacific",
    ".AX": "Asia-Pacific",
    ".SI": "Asia-Pacific",
    ".KS": "Asia-Pacific",
}


def ticker_to_region(ticker: str) -> str:
    """Map ticker to geographic region using suffix heuristic.

    Best-effort — defaults to North America for unmapped tickers.
    """
    for suffix, region in _SUFFIX_REGION.items():
        if ticker.endswith(suffix):
            return region
    return "North America"
```

- [ ] **Step 3: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_health.py -v`
Expected: 22 PASSED

- [ ] **Step 4: Commit**

```bash
git add src/health.py tests/test_health.py
git commit -m "feat: ticker-to-region mapping for diversification score"
```

---

## Task 5: Data Fetch — News and Sector Peers

**Files:**
- Modify: `src/data_fetch.py`
- Test: `tests/test_data_fetch.py`

Add `fetch_ticker_news()` and `fetch_sector_peers()` functions.

- [ ] **Step 1: Write failing tests for news fetching**

```python
# Append to tests/test_data_fetch.py

@patch("src.data_fetch.yf.Ticker")
def test_fetch_ticker_news_returns_list(mock_ticker):
    """fetch_ticker_news should return a list of dicts."""
    from src.cache import short_cache
    short_cache.clear()

    mock_instance = MagicMock()
    mock_instance.news = [
        {
            "title": "Apple announces new product",
            "publisher": "Reuters",
            "link": "https://example.com/1",
            "providerPublishTime": 1700000000,
        }
    ]
    mock_ticker.return_value = mock_instance

    from src.data_fetch import fetch_ticker_news
    result = fetch_ticker_news("AAPL")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "Apple announces new product"


@patch("src.data_fetch.yf.Ticker")
def test_fetch_ticker_news_handles_failure(mock_ticker):
    """Should return empty list on error."""
    from src.cache import short_cache
    short_cache.clear()

    mock_ticker.side_effect = Exception("API error")

    from src.data_fetch import fetch_ticker_news
    result = fetch_ticker_news("INVALID")
    assert result == []
```

Note: Check top of `tests/test_data_fetch.py` for existing imports — the file already imports `patch` and `MagicMock`. Use the same pattern.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_data_fetch.py::test_fetch_ticker_news_returns_list tests/test_data_fetch.py::test_fetch_ticker_news_handles_failure -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement fetch_ticker_news**

Add to `src/data_fetch.py`, after the existing `fetch_price_history_range` function:

```python
@cached(short_cache)
def fetch_ticker_news(ticker: str) -> list[dict]:
    """Fetch recent news for a ticker via yfinance. Cached for 5 minutes.

    Returns list of dicts with keys: title, publisher, link, providerPublishTime.
    """
    try:
        news = yf.Ticker(ticker).news
        if not news:
            return []
        return [
            {
                "title": item.get("title", ""),
                "publisher": item.get("publisher", ""),
                "link": item.get("link", ""),
                "providerPublishTime": item.get("providerPublishTime", 0),
            }
            for item in news
        ]
    except Exception:
        return []
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_data_fetch.py -v`
Expected: All PASSED

- [ ] **Step 5: Write failing test for sector peers**

```python
# Append to tests/test_data_fetch.py

@patch("src.data_fetch.yf.Ticker")
def test_fetch_sector_peers_returns_peer_data(mock_ticker):
    """fetch_sector_peers should return fundamentals for sector peers."""
    from src.cache import long_cache_fundamentals
    long_cache_fundamentals.clear()

    mock_info = {
        "sector": "Technology",
        "shortName": "Apple Inc.",
        "marketCap": 3000000000000,
        "trailingPE": 28.5,
        "dividendYield": 0.005,
        "beta": 1.2,
        "currentPrice": 180.0,
    }
    mock_instance = MagicMock()
    mock_instance.info = mock_info
    mock_instance.history.return_value = pd.DataFrame(
        {"Close": [150.0, 180.0]},
        index=pd.date_range("2025-03-01", periods=2),
    )
    mock_ticker.return_value = mock_instance

    from src.data_fetch import fetch_sector_peers
    # This function takes a sector name and the Wikipedia stock list
    # For test, just verify it handles the happy path
    result = fetch_sector_peers("Technology", ["AAPL", "MSFT", "GOOG"], "AAPL", max_peers=3)
    assert isinstance(result, list)
```

- [ ] **Step 6: Implement fetch_sector_peers**

Add to `src/data_fetch.py`:

```python
@cached(long_cache_fundamentals, key=lenient_key)
def fetch_sector_peers(
    sector: str,
    candidate_tickers: list[str],
    target_ticker: str,
    max_peers: int = 4,
) -> list[dict]:
    """Find sector peers for a ticker from a candidate list.

    Returns list of dicts with: ticker, name, pe, div_yield, beta, return_1y.
    The target_ticker is excluded from results.
    """
    peers = []
    for ticker in candidate_tickers:
        if len(peers) >= max_peers:
            break
        if ticker == target_ticker:
            continue
        try:
            info = yf.Ticker(ticker).info
            ticker_sector = info.get("sector", "")
            if ticker_sector != sector:
                continue

            hist = yf.Ticker(ticker).history(period="1y")
            return_1y = None
            if not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if len(close) >= 2:
                    return_1y = round((close.iloc[-1] / close.iloc[0] - 1) * 100, 1)

            peers.append({
                "ticker": ticker,
                "name": info.get("shortName", ticker),
                "pe": info.get("trailingPE"),
                "div_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                "beta": info.get("beta"),
                "return_1y": return_1y,
            })
        except Exception:
            continue
    return peers
```

- [ ] **Step 7: Implement fetch_sector_medians**

The spec requires fundamentals shown "with sector median comparison" for P/E and Dividend Yield. Add to `src/data_fetch.py`:

```python
@cached(long_cache_fundamentals, key=lenient_key)
def fetch_sector_medians(
    sector: str,
    candidate_tickers: list[str],
    max_samples: int = 10,
) -> dict:
    """Compute median P/E and dividend yield for a sector.

    Samples up to max_samples tickers from the candidate list that match
    the given sector. Returns dict with keys: median_pe, median_div_yield.
    """
    pe_values = []
    dy_values = []
    sampled = 0

    for ticker in candidate_tickers:
        if sampled >= max_samples:
            break
        try:
            info = yf.Ticker(ticker).info
            if info.get("sector") != sector:
                continue
            sampled += 1
            pe = info.get("trailingPE")
            if pe is not None and pe > 0:
                pe_values.append(pe)
            dy = info.get("dividendYield")
            if dy is not None and dy > 0:
                dy_values.append(dy * 100)
        except Exception:
            continue

    import statistics
    return {
        "median_pe": round(statistics.median(pe_values), 1) if pe_values else None,
        "median_div_yield": round(statistics.median(dy_values), 2) if dy_values else None,
    }
```

- [ ] **Step 8: Run all tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 9: Commit**

```bash
git add src/data_fetch.py tests/test_data_fetch.py
git commit -m "feat: news fetching, sector peers, and sector medians"
```

---

## Task 6: Portfolio Health Tab UI

**Files:**
- Create: `src/ui/health.py`
- Delete: `src/ui/risk.py` (after verifying health.py works)
- Modify: `main.py`

This is the largest UI task. It reuses existing data fetching from `risk.py` and adds the health score display, findings cards, and disclaimer banner. Existing analytics table, correlation heatmap, sector breakdown, and rebalancing calculator are moved into collapsible sections.

- [ ] **Step 1: Create `src/ui/health.py` with the `build_health_tab` function signature and disclaimer banner**

The new file follows the same async pattern as `build_risk_tab` in `risk.py`. Start with the disclaimer banner and health score section, then progressively add the remaining sections.

```python
# src/ui/health.py
"""Portfolio Health tab for the NiceGUI dashboard.

Replaces the Risk & Analytics tab with narrative diagnostics,
a composite health score, and sector gap analysis. Existing metrics
are preserved in collapsible sections.
"""

import numpy as np
import pandas as pd
from nicegui import run, ui

from src.charts import FALLBACK_COLORS, C_POSITIVE, C_NEGATIVE, C_AMBER
from src.stocks import (
    TICKER_COLORS, get_bonds, get_commodities, get_crypto,
    get_emerging_markets, get_etfs, get_reits,
)
from src.data_fetch import fetch_analytics_history, fetch_fundamentals
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, compute_analytics
from src.health import (
    compute_health_score, generate_findings, ticker_to_region,
    GICS_SECTORS,
)
from src.theme import (
    TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM, TEXT_FAINT, TEXT_SECONDARY,
    BG_PILL, BORDER, BORDER_INPUT, BORDER_SUBTLE, BG_TOPBAR,
    GREEN, RED, AMBER, ACCENT,
)


# Re-use the asset class sector mapping from the old risk module
_ASSET_CLASS_SECTORS: dict[str, str] = {}
for _label, _fn in [
    ("Commodities", get_commodities),
    ("Equity ETFs", get_etfs),
    ("Bonds", get_bonds),
    ("Real Estate", get_reits),
    ("Emerging Markets", get_emerging_markets),
    ("Crypto", get_crypto),
]:
    for _t in _fn():
        _ASSET_CLASS_SECTORS[_t] = _label


_DISCLAIMER_HTML = (
    f'<div style="background:rgba(217,119,6,0.06);border:1px solid rgba(217,119,6,0.15);'
    f'border-radius:6px;padding:10px 14px;margin-bottom:16px;">'
    f'<div style="color:{AMBER};font-size:11px;line-height:1.5;">'
    f'<strong>For informational purposes only.</strong> '
    f'This tool provides data and calculations to support your own research. '
    f'It does not constitute financial advice, investment recommendations, or '
    f'solicitation to buy or sell securities. Past performance does not predict '
    f'future results. Always consult a qualified financial advisor before making '
    f'investment decisions.'
    f'</div></div>'
)


def _section_header(title: str) -> None:
    ui.html(
        f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:{TEXT_MUTED};margin:18px 0 8px 0;">'
        f'{title}</div>'
    )


def _score_color(score: float, max_score: float) -> str:
    """Return color based on score percentage: green >= 70%, amber 40-70%, red < 40%."""
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.7:
        return GREEN
    if pct >= 0.4:
        return AMBER
    return RED
```

Write the full `build_health_tab` async function. It should:
1. Render the disclaimer banner
2. Fetch data using the same `_fetch_risk_data` pattern from `risk.py`
3. Compute health score using `src.health.compute_health_score`
4. Render health score circle
5. Render findings cards
6. Render sector exposure (reuse `_render_sector_breakdown` logic from risk.py — copy the function into health.py since we're deleting risk.py)
7. Render collapsible detailed metrics (the existing flat table + correlation heatmap)
8. Render rebalancing calculator

This is a large function. The implementer should refer to `src/ui/risk.py` for the data fetching pattern and UI component patterns, and copy the following functions from risk.py into health.py:
- `_render_flat_table`
- `_render_correlation_heatmap` and `_corr_color`
- `_render_sector_breakdown` and `_build_sector_data` and `_SECTOR_COLORS`
- `_render_rebalancing_calculator`
- Helper functions: `_fmt`, `_color_class`, `_section_intro`

Then add the new sections (health score, findings, disclaimer) on top.

The complete `build_health_tab` function structure:

```python
async def build_health_tab(portfolio: dict, currency: str) -> None:
    """Render the Portfolio Health tab."""
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")
    tickers = list(portfolio.keys())

    if not tickers:
        ui.html(
            f'<p style="color:{TEXT_DIM};font-size:13px;padding:20px 0;">'
            f'Add positions to your portfolio to see portfolio health.</p>'
        )
        return

    # Disclaimer
    ui.html(_DISCLAIMER_HTML)

    # Fetch data (same pattern as old risk tab)
    result = await run.io_bound(lambda: _fetch_health_data(tickers, portfolio, currency))
    if result is None:
        ui.html(f'<div style="color:{TEXT_DIM};font-size:13px;padding:24px;">'
                'Could not load health data. Please try reloading the page.</div>')
        return
    price_data_1y, analytics_df, fund_rows, portfolio_df = result

    # Build color map
    portfolio_color_map = {
        t: TICKER_COLORS.get(t, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }

    # Compute health score inputs
    ticker_weights_decimal = (
        portfolio_df.groupby("Ticker")["Weight (%)"].sum() / 100
    ).to_dict()

    sectors = set()
    regions = set()
    for fr in fund_rows:
        sector = fr.get("Sector", "Unknown")
        if sector and sector != "Unknown":
            sectors.add(sector)
        regions.add(ticker_to_region(fr["Ticker"]))

    sector_weights = {}
    for fr in fund_rows:
        sector = fr.get("Sector", "Unknown")
        w = ticker_weights_decimal.get(fr["Ticker"], 0) * 100
        sector_weights[sector] = sector_weights.get(sector, 0) + w

    # Compute weighted avg correlation
    weighted_avg_corr = _compute_weighted_corr(price_data_1y, tickers, ticker_weights_decimal)

    # Compute portfolio volatility
    annualized_vol = _compute_portfolio_vol(price_data_1y, tickers, ticker_weights_decimal)

    # Top holdings
    top_holdings = sorted(
        [(t, w * 100) for t, w in ticker_weights_decimal.items()],
        key=lambda x: x[1], reverse=True,
    )

    # Health score
    score_result = compute_health_score(
        ticker_weights_decimal, sectors, regions,
        weighted_avg_corr, annualized_vol,
    )

    # Render health score circle
    _render_health_score(score_result)

    # Findings
    findings = generate_findings(
        ticker_weights_decimal, sectors, regions, sector_weights,
        weighted_avg_corr, annualized_vol, top_holdings,
    )
    _render_findings(findings)

    # Sector exposure
    with ui.element("div").classes("risk-sections w-full"):
        _render_sector_breakdown(fund_rows, portfolio_df, portfolio_color_map)

        # Collapsible detailed metrics
        with ui.expansion("Detailed Metrics").classes("w-full").style(
            f"background:transparent;border:1px solid {BORDER_SUBTLE};border-radius:8px;"
        ):
            _render_flat_table(
                portfolio_df, analytics_df, fund_rows, price_data_1y,
                currency_symbol, portfolio_color_map, base_currency=currency,
            )
            if len(tickers) >= 2:
                _render_correlation_heatmap(price_data_1y, tickers)

        # Rebalancing calculator
        _render_rebalancing_calculator(fund_rows, portfolio_df, currency_symbol)
```

The following helper functions need to be implemented:

```python
def _fetch_health_data(
    tickers: list[str], portfolio: dict, currency: str,
) -> tuple[dict, pd.DataFrame, list[dict], pd.DataFrame] | None:
    """Fetch all data needed for the health tab. Same pattern as _fetch_risk_data in risk.py.
    Returns (price_data_1y, analytics_df, fund_rows, portfolio_df)."""
    # Copy the _fetch_risk_data function body from risk.py lines 1183-1226

def _compute_weighted_corr(
    price_data_1y: dict[str, pd.DataFrame],
    tickers: list[str],
    weights: dict[str, float],
) -> float | None:
    """Compute weight-adjusted average pairwise Pearson correlation.
    Returns None if < 2 tickers have sufficient history.

    Algorithm:
    1. Compute daily returns for each ticker from price_data_1y
    2. Build pairwise correlation matrix: pd.DataFrame(returns).corr()
    3. For each pair (i,j) where i<j: pair_weight = weights[i] * weights[j]
    4. weighted_avg = sum(corr[i,j] * pair_weight) / sum(pair_weight)
    """

def _compute_portfolio_vol(
    price_data_1y: dict[str, pd.DataFrame],
    tickers: list[str],
    weights: dict[str, float],
) -> float:
    """Compute portfolio-level annualized volatility.
    Returns 0.0 if insufficient data.

    Algorithm:
    1. Build daily returns DataFrame from price_data_1y (aligned dates)
    2. Portfolio daily return = sum(weight_i * return_i) for each day
    3. Annualized vol = std(portfolio_daily_returns) * sqrt(252)
    """

def _render_health_score(score_result: dict) -> None:
    """Render the circular health score badge and expandable methodology.
    score_result is the output of compute_health_score().
    Uses score_result['total'] for the badge number.
    Uses score_result['components'] for the expandable breakdown."""

def _render_findings(findings: list[dict]) -> None:
    """Render finding cards with colored left borders.
    Each finding: {severity: 'red'|'amber'|'green', headline: str, body: str}.
    Red = border-left #DC2626, Amber = #D97706, Green = #16A34A.
    Follows the wireframe from the spec."""
```

- [ ] **Step 2: Test that the tab builds without errors by running the app**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -c "from src.ui.health import build_health_tab; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Update `main.py` to use the new health tab**

In `main.py`, make these changes:

1. Replace import: `from src.ui.risk import build_risk_tab` → `from src.ui.health import build_health_tab`
2. Update `_TAB_NAMES`: replace `"Risk & Analytics"` with `"Portfolio Health"`
3. In `_build_tab`, replace `elif name == "Risk & Analytics": await build_risk_tab(...)` with `elif name == "Portfolio Health": await build_health_tab(...)`

- [ ] **Step 4: Verify existing tests still pass**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASSED (no tests directly test risk.py UI rendering)

- [ ] **Step 5: Delete `src/ui/risk.py`**

```bash
git rm src/ui/risk.py
```

- [ ] **Step 6: Commit**

```bash
git add src/ui/health.py main.py
git commit -m "feat: portfolio health tab replaces risk & analytics"
```

---

## Task 7: Stock Research Tab UI

**Files:**
- Create: `src/ui/research.py`
- Modify: `main.py`

New tab with search, fundamentals, portfolio fit preview, price chart, peer comparison, and news.

- [ ] **Step 1: Create `src/ui/research.py`**

The Research tab follows the same async builder pattern as all other tabs. Key sections:

```python
# src/ui/research.py
"""Stock Research tab for the NiceGUI dashboard.

Search any ticker, view fundamentals with sector context,
see how adding it would affect portfolio health, compare
with sector peers, and read recent news.
"""

import time

import pandas as pd
from nicegui import app, run, ui

from src.charts import FALLBACK_COLORS
from src.data_fetch import (
    fetch_company_name, fetch_fundamentals, fetch_ticker_news,
    fetch_sector_peers, fetch_analytics_history, fetch_price_history_range,
)
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.health import (
    compute_health_score, simulate_addition, ticker_to_region,
)
from src.portfolio import build_portfolio_df, compute_analytics
from src.theme import (
    TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM, TEXT_FAINT,
    BG_PILL, BORDER, BORDER_INPUT, BORDER_SUBTLE,
    GREEN, RED, AMBER, ACCENT,
)


_DISCLAIMER_HTML = (
    f'<div style="background:rgba(217,119,6,0.06);border:1px solid rgba(217,119,6,0.15);'
    f'border-radius:6px;padding:10px 14px;margin-bottom:16px;">'
    f'<div style="color:{AMBER};font-size:11px;line-height:1.5;">'
    f'<strong>For informational purposes only.</strong> '
    f'This tool provides data and calculations to support your own research. '
    f'It does not constitute financial advice, investment recommendations, or '
    f'solicitation to buy or sell securities. Past performance does not predict '
    f'future results. Always consult a qualified financial advisor before making '
    f'investment decisions.'
    f'</div></div>'
)


async def build_research_tab(
    portfolio: dict,
    currency: str,
    stock_options: dict | None = None,
) -> None:
    """Render the Stock Research tab."""
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")

    # Disclaimer
    ui.html(_DISCLAIMER_HTML)

    # Results container (rebuilt on each search)
    results_container = ui.column().classes("w-full")

    # Search bar
    # Uses the same stock_options dict as the sidebar autocomplete
    options = stock_options or getattr(app.state, "stock_options", {}) or {}

    async def _on_search(ticker: str):
        """Fetch and render research data for the selected ticker."""
        if not ticker:
            return
        ticker = ticker.strip().upper()

        # Save to recent searches
        stored = app.storage.user.get("recent_searches", [])
        if ticker not in stored:
            stored = [ticker] + stored[:9]  # Keep last 10
            app.storage.user["recent_searches"] = stored

        results_container.clear()
        with results_container:
            spinner = ui.spinner('dots', size='xl').classes('self-center')

        try:
            # Fetch all data in parallel
            def _fetch():
                name = fetch_company_name(ticker)
                fund = fetch_fundamentals(ticker)
                news = fetch_ticker_news(ticker)
                hist = fetch_price_history_range(ticker, "1y")
                return name, fund, news, hist

            name, fund, news, hist = await run.io_bound(_fetch)

            results_container.clear()
            with results_container:
                # Company header
                _render_company_header(ticker, name, fund, currency_symbol, currency)

                with ui.row().classes("w-full").style("gap:16px;"):
                    # Left: Fundamentals
                    with ui.column().classes("flex-1"):
                        _render_fundamentals(fund, currency_symbol)

                    # Right: Portfolio Fit Preview
                    with ui.column().classes("flex-1"):
                        await _render_portfolio_fit(
                            ticker, fund, portfolio, currency,
                        )

                # Price chart
                _render_price_chart(ticker, hist)

                # Peer comparison
                await _render_peers(ticker, fund, options, currency_symbol)

                # News
                _render_news(news)

        except Exception as e:
            results_container.clear()
            with results_container:
                ui.html(
                    f'<div style="color:{TEXT_DIM};font-size:13px;padding:24px;">'
                    f'Could not load data for {ticker}. Error: {e}</div>'
                )
        finally:
            try:
                spinner.delete()
            except (ValueError, RuntimeError, NameError):
                pass

    with ui.row().classes("w-full items-center").style("gap:12px;margin-bottom:16px;"):
        search_input = ui.select(
            options=options,
            with_input=True,
            label="Search ticker or company name",
        ).classes("flex-1").props("dense outlined")
        search_input.on_value_change(lambda e: _on_search(e.value) if e.value else None)

        # Recent searches
        recent = app.storage.user.get("recent_searches", [])
        if recent:
            with ui.row().classes("items-center").style("gap:4px;"):
                ui.html(f'<span style="font-size:11px;color:{TEXT_DIM};">Recent:</span>')
                for t in recent[:5]:
                    ui.button(t, on_click=lambda t=t: _on_search(t)).props(
                        "flat dense no-caps size=sm"
                    ).style(
                        f"font-size:11px;color:{ACCENT};padding:2px 8px;"
                        f"border:1px solid rgba(59,130,246,0.2);border-radius:4px;"
                    )
```

The implementer should write the helper functions (`_render_company_header`, `_render_fundamentals`, `_render_portfolio_fit`, `_render_price_chart`, `_render_peers`, `_render_news`) following the patterns in the existing UI modules and the spec wireframes. Each function renders a section of the research results.

Key implementation notes:
- `_render_portfolio_fit` calls `simulate_addition()` from `src/health.py` with the current portfolio data
- `_render_price_chart` reuses the Plotly chart pattern from `src/ui/positions.py`
- `_render_peers` calls `fetch_sector_peers()` from `src/data_fetch.py`
- `_render_news` renders yfinance news chronologically with external links

- [ ] **Step 2: Add Research tab to `main.py`**

1. Add import: `from src.ui.research import build_research_tab`
2. Add `"Research"` to `_TAB_NAMES` list (after "Portfolio Health")
3. Add to `_build_tab`: `elif name == "Research": await build_research_tab(portfolio, currency, stock_options)`

- [ ] **Step 3: Verify the tab renders**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -c "from src.ui.research import build_research_tab; print('import OK')"`
Expected: `import OK`

- [ ] **Step 4: Run all tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/ui/research.py main.py
git commit -m "feat: stock research tab with fundamentals, fit preview, peers, news"
```

---

## Task 8: News in Portfolio Health Tab

**Files:**
- Modify: `src/ui/health.py`

Add aggregated portfolio news feed at the bottom of the health tab.

- [ ] **Step 1: Add news section to `build_health_tab`**

After the rebalancing calculator, add:

```python
# Portfolio news feed
_section_header("Portfolio News")
await _render_portfolio_news(tickers, portfolio_color_map)
```

Implement `_render_portfolio_news`:

```python
async def _render_portfolio_news(
    tickers: list[str],
    color_map: dict[str, str],
) -> None:
    """Render aggregated news for all portfolio tickers."""
    from src.data_fetch import fetch_ticker_news

    def _fetch_all_news():
        all_news = []
        for ticker in tickers:
            for item in fetch_ticker_news(ticker):
                item["ticker"] = ticker
                all_news.append(item)
        # Sort by publish time descending
        all_news.sort(key=lambda x: x.get("providerPublishTime", 0), reverse=True)
        return all_news[:20]

    news_items = await run.io_bound(_fetch_all_news)

    if not news_items:
        ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No recent news for your holdings.</p>')
        return

    with ui.column().classes("chart-card w-full"):
        for item in news_items:
            ticker = item.get("ticker", "")
            dot_color = color_map.get(ticker, TEXT_DIM)
            publish_time = item.get("providerPublishTime", 0)
            time_ago = _format_time_ago(publish_time)

            ui.html(
                f'<div style="display:flex;gap:8px;align-items:baseline;'
                f'padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
                f'<span style="font-size:11px;font-weight:600;color:{dot_color};'
                f'white-space:nowrap;">{ticker}</span>'
                f'<div style="flex:1;">'
                f'<a href="{item.get("link", "#")}" target="_blank" '
                f'style="color:{TEXT_PRIMARY};font-size:12px;text-decoration:none;">'
                f'{item.get("title", "")}</a>'
                f'<div style="font-size:10px;color:{TEXT_DIM};">'
                f'{item.get("publisher", "")} &middot; {time_ago}</div>'
                f'</div></div>'
            )
```

Also implement `_format_time_ago`:

```python
import time as _time

def _format_time_ago(unix_timestamp: int) -> str:
    """Convert unix timestamp to relative time string."""
    if not unix_timestamp:
        return ""
    diff = int(_time.time()) - unix_timestamp
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    days = diff // 86400
    return f"{days}d ago"
```

- [ ] **Step 2: Run all tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 3: Commit**

```bash
git add src/ui/health.py
git commit -m "feat: portfolio news feed in health tab"
```

---

## Task 9: Update Guide Tab

**Files:**
- Modify: `src/ui/guide.py`

Update the in-app documentation to describe the new tabs.

- [ ] **Step 1: Read current guide.py**

Read `src/ui/guide.py` to understand the existing documentation structure.

- [ ] **Step 2: Update guide content**

Replace the "Risk & Analytics" section with "Portfolio Health" documentation, and add a "Stock Research" section. Follow the existing formatting pattern.

Key points to document:
- **Portfolio Health**: Health score (what it measures, the four components), findings cards, sector exposure, collapsible detailed metrics, rebalancing calculator
- **Stock Research**: Search any ticker, fundamentals with sector context, portfolio fit preview, peer comparison, news feed
- Update any cross-references from "Risk & Analytics" to "Portfolio Health"

- [ ] **Step 3: Run all tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 4: Commit**

```bash
git add src/ui/guide.py
git commit -m "docs: update guide tab for health and research tabs"
```

---

## Task 10: Integration Testing and Polish

**Files:**
- All modified files

Final verification that everything works end-to-end.

- [ ] **Step 1: Run all tests**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 2: Start the app and verify visually**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && timeout 15 python main.py 2>&1 || true`

Check:
- Tab bar shows "Portfolio Health" instead of "Risk & Analytics"
- Tab bar shows "Research" as a new tab
- Portfolio Health tab loads with health score, findings, sector exposure
- Research tab has working search with autocomplete
- No console errors

- [ ] **Step 3: Verify tab count is 8**

Check `_TAB_NAMES` in `main.py` has exactly 8 entries: Overview, Positions, Portfolio Health, Income, Forecast, Research, Guide (with Diagnostics inside Forecast making it effectively 7 top-level + 1 sub).

The current `_TAB_NAMES` has 6 entries: Overview, Positions, Risk & Analytics, Income, Forecast, Guide. After changes: Overview, Positions, Portfolio Health, Income, Forecast, Research, Guide = 7 top-level tabs. (Diagnostics is a sub-panel within Forecast, not a separate tab.) The spec's "8 tabs" counts Diagnostics as a tab; the actual `_TAB_NAMES` list should have 7 entries.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: integration fixes for health and research tabs"
```
