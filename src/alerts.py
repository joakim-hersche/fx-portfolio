"""Portfolio alert rule engine.

Evaluates portfolio metrics against configurable thresholds.
Only includes rules that are cheap to compute (no heavy data fetching).
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Alert:
    severity: str  # "info", "warning", "critical"
    title: str
    message: str
    rule_id: str


def check_concentration(weights: dict[str, float], threshold: float = 0.30) -> list[Alert]:
    """Flag positions above threshold % of portfolio."""
    alerts = []
    for ticker, weight in weights.items():
        if weight > threshold:
            pct = round(weight * 100, 1)
            alerts.append(Alert(
                severity="critical" if weight > 0.40 else "warning",
                title="Concentration risk",
                message=f"{ticker} is {pct}% of your portfolio (threshold: {round(threshold * 100)}%)",
                rule_id=f"concentration_{ticker}",
            ))
    return alerts


def check_correlation(price_data: dict[str, pd.DataFrame], threshold: float = 0.85) -> list[Alert]:
    """Flag ticker pairs with correlation above threshold. Only evaluates warm cache data."""
    tickers = [t for t, df in price_data.items()
               if not df.empty and "Close" in df.columns and len(df) >= 30]
    if len(tickers) < 2:
        return []
    returns = {}
    for t in tickers:
        close = price_data[t]["Close"].dropna()
        returns[t] = close.pct_change().dropna()
    returns_df = pd.DataFrame(returns).dropna()
    if len(returns_df) < 30:
        return []
    corr_matrix = returns_df.corr()
    alerts = []
    seen = set()
    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if i >= j:
                continue
            pair_key = tuple(sorted([t1, t2]))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            corr_val = corr_matrix.loc[t1, t2]
            if abs(corr_val) > threshold:
                alerts.append(Alert(
                    severity="warning",
                    title="High correlation",
                    message=f"{t1} and {t2} have {round(corr_val * 100)}% correlation (threshold: {round(threshold * 100)}%)",
                    rule_id=f"correlation_{pair_key[0]}_{pair_key[1]}",
                ))
    return alerts


def evaluate_all(weights: dict[str, float], price_data: dict[str, pd.DataFrame] | None = None, settings: dict | None = None) -> list[Alert]:
    """Run all alert rules and return combined results."""
    s = settings or {}
    alerts = []
    alerts.extend(check_concentration(weights, s.get("concentration_threshold", 0.30)))
    if price_data:
        alerts.extend(check_correlation(price_data, s.get("correlation_threshold", 0.85)))
    return alerts
