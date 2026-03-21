"""Health score engine, findings generator, portfolio fit simulation, region mapping."""
from __future__ import annotations


GICS_SECTORS: set[str] = {
    "Energy", "Materials", "Industrials", "Consumer Discretionary",
    "Consumer Staples", "Healthcare", "Financials", "Information Technology",
    "Communication Services", "Utilities", "Real Estate",
}

REGIONS: set[str] = {
    "North America", "Europe", "UK", "Asia-Pacific", "Emerging Markets",
}

STABILITY_VOL_CAP = 0.25

_SUFFIX_TO_REGION: dict[str, str] = {
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


# ── Component scores ────────────────────────────────────────────────────────

def compute_concentration_score(weights: dict[str, float]) -> tuple[float, float]:
    """Return (score out of 30, HHI)."""
    if not weights:
        return 0.0, 1.0
    hhi = sum(w ** 2 for w in weights.values())
    score = (1 - hhi) * 30
    return score, hhi


def compute_diversification_score(sectors: set[str], regions: set[str]) -> float:
    """Return score out of 35."""
    return (len(sectors) / 11 * 17.5) + (len(regions) / 5 * 17.5)


def compute_correlation_score(weighted_avg_corr: float | None) -> float:
    """Return score out of 20. None means single/no holding → full marks."""
    if weighted_avg_corr is None:
        return 20.0
    clamped = max(0.0, min(1.0, weighted_avg_corr))
    return (1 - clamped) * 20


def compute_stability_score(annualized_vol: float) -> float:
    """Return score out of 15."""
    return max(0.0, 15 * (1 - annualized_vol / STABILITY_VOL_CAP))


# ── Composite ────────────────────────────────────────────────────────────────

def compute_health_score(
    weights: dict[str, float],
    sectors: set[str],
    regions: set[str],
    weighted_avg_corr: float | None,
    annualized_vol: float,
) -> dict:
    concentration, hhi = compute_concentration_score(weights)
    diversification = compute_diversification_score(sectors, regions)
    correlation = compute_correlation_score(weighted_avg_corr)
    stability = compute_stability_score(annualized_vol)

    components = [
        {"name": "Diversification", "score": diversification, "max_score": 35,
         "details": f"{len(sectors)} sectors, {len(regions)} regions"},
        {"name": "Concentration", "score": concentration, "max_score": 30,
         "details": f"HHI {hhi:.3f}"},
        {"name": "Correlation", "score": correlation, "max_score": 20,
         "details": f"Avg corr {weighted_avg_corr}" if weighted_avg_corr is not None else "Single holding"},
        {"name": "Stability", "score": stability, "max_score": 15,
         "details": f"Vol {annualized_vol:.1%}"},
    ]

    return {
        "total": sum(c["score"] for c in components),
        "components": components,
    }


# ── Findings generator ──────────────────────────────────────────────────────

def generate_findings(
    weights: dict[str, float],
    sectors: set[str],
    regions: set[str],
    sector_weights: dict[str, float],
    weighted_avg_corr: float | None,
    annualized_vol: float,
    top_holdings: list[tuple[str, float]],
) -> list[dict]:
    """Generate plain-language diagnostic cards. Never uses advisory language."""
    findings: list[dict] = []

    # Single holding > 25% (report only the largest)
    if top_holdings and top_holdings[0][1] > 25:
        ticker, w_pct = top_holdings[0]
        findings.append({
            "severity": "red",
            "headline": "High concentration risk",
            "body": f"{ticker} represents {w_pct:.1f}% of the portfolio.",
        })

    # Top 3 > 65%
    top3_weight = sum(w for _, w in top_holdings[:3])
    if top3_weight > 65:
        severity = "red" if top3_weight > 80 else "amber"
        findings.append({
            "severity": severity,
            "headline": "High concentration risk",
            "body": f"Top 3 holdings account for {top3_weight:.1f}% of the portfolio.",
        })

    # Any sector > 50%
    for sector, sw in sector_weights.items():
        if sw > 50:
            findings.append({
                "severity": "amber",
                "headline": "Sector imbalance",
                "body": f"{sector} makes up {sw:.1f}% of the portfolio.",
            })

    # More than 3 GICS sectors missing
    missing = GICS_SECTORS - sectors
    if len(missing) > 3:
        findings.append({
            "severity": "amber",
            "headline": "Limited sector coverage",
            "body": f"{len(missing)} of 11 GICS sectors are not represented.",
        })

    # Weighted avg correlation > 0.6
    if weighted_avg_corr is not None and weighted_avg_corr > 0.6:
        findings.append({
            "severity": "amber",
            "headline": "High internal correlation",
            "body": f"Weighted average pairwise correlation is {weighted_avg_corr:.2f}.",
        })

    # 3+ regions → green
    if len(regions) >= 3:
        findings.append({
            "severity": "green",
            "headline": "Good geographic spread",
            "body": f"Portfolio spans {len(regions)} regions.",
        })

    # Vol < 16%
    if annualized_vol < 0.16:
        findings.append({
            "severity": "green",
            "headline": "Below-market volatility",
            "body": f"Annualized volatility is {annualized_vol:.1%}.",
        })

    # Cap at 5: prioritize red, then amber, then green
    findings.sort(key=lambda f: {"red": 0, "amber": 1, "green": 2}.get(f["severity"], 3))
    return findings[:5]


# ── Portfolio fit simulation ─────────────────────────────────────────────────

def simulate_addition(
    current_portfolio: dict,
    new_ticker_sector: str,
    new_ticker_region: str,
    new_ticker_corr_with_portfolio: float,
    addition_weight: float,
) -> dict:
    """Simulate adding a hypothetical stock and return score impact."""
    cp = current_portfolio
    current = compute_health_score(
        cp["weights"], cp["sectors"], cp["regions"],
        cp["weighted_avg_corr"], cp["annualized_vol"],
    )

    if addition_weight == 0.0:
        return {
            "current_score": current["total"],
            "projected_score": current["total"],
            "delta": 0.0,
            "impacts": [],
        }

    # Scale down existing weights, add new ticker
    scale = 1 - addition_weight
    new_weights = {t: w * scale for t, w in cp["weights"].items()}
    new_weights["__new__"] = addition_weight

    new_sectors = cp["sectors"] | {new_ticker_sector}
    new_regions = cp["regions"] | {new_ticker_region}

    # Blend correlation
    old_corr = cp["weighted_avg_corr"]
    if old_corr is not None:
        new_corr = old_corr * scale + new_ticker_corr_with_portfolio * addition_weight
    else:
        new_corr = new_ticker_corr_with_portfolio

    # Approximate new vol: reduce by diversification benefit (0.5 dampening keeps reduction conservative)
    new_vol = cp["annualized_vol"] * (1 - addition_weight * (1 - new_ticker_corr_with_portfolio) * 0.5)

    projected = compute_health_score(
        new_weights, new_sectors, new_regions, new_corr, new_vol,
    )

    # Build impact descriptions
    impacts: list[str] = []
    if new_ticker_sector not in cp["sectors"]:
        impacts.append(f"Adds {new_ticker_sector} exposure")
    if new_ticker_region not in cp["regions"]:
        impacts.append(f"Adds {new_ticker_region} exposure")
    if new_ticker_corr_with_portfolio < 0.4:
        impacts.append("Low correlation with existing holdings")

    return {
        "current_score": current["total"],
        "projected_score": projected["total"],
        "delta": projected["total"] - current["total"],
        "impacts": impacts,
    }


# ── Region mapping ───────────────────────────────────────────────────────────

def ticker_to_region(ticker: str) -> str:
    """Map ticker suffix to region. Default: North America."""
    for suffix, region in _SUFFIX_TO_REGION.items():
        if ticker.endswith(suffix):
            return region
    return "North America"
