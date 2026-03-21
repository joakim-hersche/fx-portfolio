# Workstream A — Product Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Abstract the data layer behind a provider interface, expand European stock coverage, add ticker toggle pills to the comparison chart, and add in-app portfolio alerts — all without server-side changes.

**Architecture:** Two parallel tracks. Track 1 introduces a `DataProvider` protocol in `src/providers.py`, refactors `data_fetch.py` into a routing layer, and adds SMIM coverage. Track 2 adds ticker toggle pills to the comparison chart in `overview.py` and a new alert system (`src/alerts.py` + `src/ui/alerts.py`) that evaluates cheap portfolio metrics on Overview tab load.

**Tech Stack:** Python 3.12, NiceGUI, yfinance, Plotly, cachetools, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-product-quality-workstream-a-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/providers.py` | Create | DataProvider protocol + YFinanceProvider |
| `src/data_fetch.py` | Modify | Thin routing layer delegating to provider |
| `src/portfolio.py` | Unchanged | Keeps `yf.download` until second provider exists |
| `src/stocks.py` | Modify | Add SMIM scraping function |
| `src/alerts.py` | Create | Alert rule engine (concentration, correlation) |
| `src/ui/alerts.py` | Create | Alert banner UI component |
| `src/ui/overview.py` | Modify | Ticker toggle pills + alert banner integration |
| `src/ui/sidebar.py` | Modify | Add SMIM to _MARKETS + async ticker validation |
| `tests/test_providers.py` | Create | Provider protocol + YFinanceProvider tests |
| `tests/test_alerts.py` | Create | Alert rule engine tests |
| `tests/test_stocks.py` | Create | SMIM scraping tests |

---

## Track 1: Data Layer Abstraction + European Coverage

### Task 1: DataProvider Protocol

**Files:**
- Create: `src/providers.py`
- Create: `tests/test_providers.py`

- [ ] **Step 1: Write the protocol and YFinanceProvider skeleton test**

```python
# tests/test_providers.py
"""Tests for DataProvider protocol and YFinanceProvider."""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.providers import DataProvider, YFinanceProvider


def test_yfinance_provider_satisfies_protocol():
    """YFinanceProvider must implement all DataProvider methods."""
    provider = YFinanceProvider()
    assert isinstance(provider, DataProvider)


@patch("src.providers.yf.download")
def test_get_current_prices_returns_dict(mock_download):
    close_data = pd.DataFrame({"Close": [150.0, 151.0]})
    mock_download.return_value = close_data
    provider = YFinanceProvider()
    result = provider.get_current_prices(["AAPL"])
    assert isinstance(result, dict)
    assert "AAPL" in result


@patch("src.providers.yf.Ticker")
def test_get_company_name_returns_string(mock_ticker):
    mock_ticker.return_value.info = {"shortName": "Apple Inc."}
    provider = YFinanceProvider()
    assert provider.get_company_name("AAPL") == "Apple Inc."


@patch("src.providers.yf.Ticker")
def test_get_company_name_fallback_to_ticker(mock_ticker):
    mock_ticker.return_value.info = {}
    provider = YFinanceProvider()
    assert provider.get_company_name("AAPL") == "AAPL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_providers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.providers'`

- [ ] **Step 3: Create `src/providers.py` with protocol and YFinanceProvider**

```python
# src/providers.py
"""Data provider abstraction layer.

DataProvider defines the interface for all stock data sources.
YFinanceProvider wraps the existing yfinance logic as the default.

Planned migration: EOD Historical Data (~200 EUR/year) when subscribers
arrive. Add an EODProvider class implementing DataProvider, set
DATA_PROVIDER=eod in environment.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@runtime_checkable
class DataProvider(Protocol):
    """Interface for stock data providers."""

    def get_current_prices(self, tickers: list[str]) -> dict[str, float]: ...
    def get_price_history_short(self, ticker: str) -> pd.DataFrame: ...
    def get_price_history_long(self, ticker: str) -> pd.DataFrame: ...
    def get_price_history_range(self, ticker: str, period: str) -> pd.DataFrame: ...
    def get_simulation_history(self, ticker: str) -> pd.DataFrame: ...
    def get_analytics_history(self, ticker: str) -> pd.DataFrame: ...
    def get_fundamentals(self, ticker: str) -> dict: ...
    def get_news(self, ticker: str) -> list[dict]: ...
    def get_sector_peers(self, sector: str, candidates: list[str], target: str, max_peers: int) -> list[dict]: ...
    def get_sector_medians(self, sector: str, candidates: list[str], max_samples: int) -> dict: ...
    def get_company_name(self, ticker: str) -> str: ...


class YFinanceProvider:
    """Default provider wrapping yfinance."""

    def _safe_history(self, ticker: str, period: str) -> pd.DataFrame:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if not hist.empty:
                hist.index = hist.index.tz_localize(None)
            return hist
        except Exception as e:
            logger.warning("YFinanceProvider history(%s, %s) failed: %s", ticker, period, e)
            return pd.DataFrame()

    def get_current_prices(self, tickers: list[str]) -> dict[str, float]:
        if not tickers:
            return {}
        data = yf.download(tickers, period="5d", group_by="ticker", progress=False, threads=True)
        result = {}
        for t in tickers:
            try:
                if len(tickers) == 1:
                    close = data["Close"].dropna()
                else:
                    close = data[t]["Close"].dropna()
                if not close.empty:
                    result[t] = float(close.iloc[-1])
            except (KeyError, TypeError):
                continue
        return result

    def get_price_history_short(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "6mo")

    def get_price_history_long(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "max")

    def get_price_history_range(self, ticker: str, period: str) -> pd.DataFrame:
        return self._safe_history(ticker, period)

    def get_simulation_history(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "5y")

    def get_analytics_history(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "1y")

    def get_fundamentals(self, ticker: str) -> dict:
        try:
            info = yf.Ticker(ticker).info
            current = info.get("currentPrice") or info.get("regularMarketPrice")
            low_1y = info.get("fiftyTwoWeekLow")
            high_1y = info.get("fiftyTwoWeekHigh")
            pe = info.get("trailingPE")
            div_rate = info.get("dividendRate")
            sector = info.get("sector", None)
            target_price = info.get("targetMeanPrice", None)
            trading_ccy = info.get("currency")
            financial_ccy = info.get("financialCurrency")
            if financial_ccy == "GBp":
                financial_ccy = "GBX"

            div_pct = None
            div = info.get("dividendYield")
            if div is not None:
                candidate = div * 100
                div_pct = candidate if candidate <= 20.0 else div

            position = None
            if current and low_1y and high_1y and high_1y > low_1y:
                position = round((current - low_1y) / (high_1y - low_1y) * 100, 1)

            return {
                "P/E Ratio": round(pe, 1) if pe else None,
                "Div Yield (%)": round(div_pct, 2) if div_pct else None,
                "1-Year Low": round(low_1y, 2) if low_1y else None,
                "1-Year High": round(high_1y, 2) if high_1y else None,
                "1-Year Position": position,
                "Current Price": round(current, 2) if current else None,
                "Sector": sector if sector else "Unknown",
                "Target Price": round(target_price, 2) if target_price else None,
                "Dividend Rate": round(div_rate, 4) if div_rate else None,
                "Financial Currency": financial_ccy,
            }
        except Exception:
            return {}

    def get_news(self, ticker: str) -> list[dict]:
        try:
            news = yf.Ticker(ticker).news
            if not news:
                return []
            results = []
            for item in news:
                content = item.get("content", item)
                provider = content.get("provider", {})
                canonical = content.get("canonicalUrl", {})
                pub_time = 0
                pub_date = content.get("pubDate", "")
                if pub_date:
                    from datetime import datetime
                    try:
                        pub_time = int(datetime.fromisoformat(
                            pub_date.replace("Z", "+00:00")
                        ).timestamp())
                    except (ValueError, TypeError):
                        pub_time = item.get("providerPublishTime", 0)
                else:
                    pub_time = item.get("providerPublishTime", 0)
                results.append({
                    "title": content.get("title", item.get("title", "")),
                    "publisher": provider.get("displayName", item.get("publisher", "")),
                    "link": canonical.get("url", item.get("link", "")),
                    "providerPublishTime": pub_time,
                })
            return results
        except Exception:
            return []

    def get_sector_peers(self, sector: str, candidates: list[str], target: str, max_peers: int = 4) -> list[dict]:
        import statistics
        peers = []
        for ticker in candidates:
            if len(peers) >= max_peers:
                break
            if ticker == target:
                continue
            try:
                info = yf.Ticker(ticker).info
                if info.get("sector", "") != sector:
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

    def get_sector_medians(self, sector: str, candidates: list[str], max_samples: int = 10) -> dict:
        import statistics
        pe_values, dy_values = [], []
        sampled = 0
        for ticker in candidates:
            if sampled >= max_samples:
                break
            try:
                info = yf.Ticker(ticker).info
                if info.get("sector") != sector:
                    continue
                sampled += 1
                pe = info.get("trailingPE")
                if pe and pe > 0:
                    pe_values.append(pe)
                dy = info.get("dividendYield")
                if dy and dy > 0:
                    dy_values.append(dy * 100)
            except Exception:
                continue
        return {
            "median_pe": round(statistics.median(pe_values), 1) if pe_values else None,
            "median_div_yield": round(statistics.median(dy_values), 2) if dy_values else None,
        }

    def get_company_name(self, ticker: str) -> str:
        try:
            info = yf.Ticker(ticker).info
            return info.get("shortName") or info.get("longName") or ticker
        except Exception:
            return ticker
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_providers.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/providers.py tests/test_providers.py
git commit -m "feat: add DataProvider protocol and YFinanceProvider"
```

---

### Task 2: Wire Provider into data_fetch.py

**Files:**
- Modify: `src/data_fetch.py`

**Note:** `portfolio.py` is NOT modified in this task. It still calls `yf.download` directly for batch prices because `build_portfolio_df` needs the raw MultiIndex DataFrame (current + prev-day close). The full refactor of `portfolio.py` happens when a second provider is implemented and the return shape can be properly abstracted. For now, the provider is wired into `data_fetch.py` so that new code (alerts, validation, future features) can use it.

- [ ] **Step 1: Run existing tests to confirm green baseline**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 2: Add provider initialization to data_fetch.py**

At the top of `src/data_fetch.py`, after the existing imports, add:

```python
import os
from src.providers import YFinanceProvider

_provider = YFinanceProvider()

def get_provider():
    """Return the active data provider instance.

    Currently always returns YFinanceProvider. When a paid provider
    (e.g., EOD Historical Data) is added, this will read
    DATA_PROVIDER env var to select the implementation.
    """
    return _provider
```

This keeps all existing cached functions intact. The provider is available for new call sites and gradual migration.

- [ ] **Step 3: Run all tests to verify nothing broke**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASS (no existing code paths changed)

- [ ] **Step 4: Commit**

```bash
git add src/data_fetch.py
git commit -m "refactor: wire DataProvider into data_fetch routing layer"
```

---

### Task 3: Add SMIM Coverage to stocks.py

**Files:**
- Modify: `src/stocks.py`
- Modify: `src/data_fetch.py:300-326` (add SMIM to load_stock_options)
- Create: `tests/test_stocks.py`

- [ ] **Step 1: Write test for SMIM scraping**

```python
# tests/test_stocks.py
"""Tests for stock list scraping functions."""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.stocks import get_smim_stocks


@patch("src.stocks.requests.get")
def test_get_smim_stocks_returns_dict(mock_get):
    """SMIM scraper should return a dict of ticker -> display name."""
    # Simulate a Wikipedia table with SMIM tickers
    html = '''
    <table class="wikitable">
    <tr><th>Ticker</th><th>Company</th></tr>
    <tr><td>BAER.SW</td><td>Julius Baer</td></tr>
    <tr><td>SREN.SW</td><td>Swiss Re</td></tr>
    </table>
    '''
    mock_response = MagicMock()
    mock_response.text = html
    mock_get.return_value = mock_response

    result = get_smim_stocks()
    assert isinstance(result, dict)
    assert len(result) >= 1
    # Verify tickers have .SW suffix
    for ticker in result:
        assert ticker.endswith(".SW"), f"SMIM ticker {ticker} missing .SW suffix"


@patch("src.stocks.requests.get")
def test_get_smim_stocks_fallback_on_failure(mock_get):
    """If Wikipedia scrape fails, return static fallback list."""
    mock_get.side_effect = Exception("network error")
    result = get_smim_stocks()
    assert isinstance(result, dict)
    assert len(result) > 0  # fallback should have entries
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_stocks.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_smim_stocks'`

- [ ] **Step 3: Implement `get_smim_stocks` in stocks.py**

Add after `get_smi_stocks()`:

```python
# Static fallback for SMIM — updated quarterly from SIX Group
_SMIM_FALLBACK = {
    "BAER.SW": "Julius Baer (BAER.SW)",
    "SREN.SW": "Swiss Re (SREN.SW)",
    "SCMN.SW": "Swisscom (SCMN.SW)",
    "GEBN.SW": "Geberit (GEBN.SW)",
    "SGSN.SW": "SGS (SGSN.SW)",
    "TEMN.SW": "Temenos (TEMN.SW)",
    "PGHN.SW": "Partners Group (PGHN.SW)",
    "BARN.SW": "Barry Callebaut (BARN.SW)",
    "STMN.SW": "Straumann (STMN.SW)",
    "VACN.SW": "VAT Group (VACN.SW)",
    "SOON.SW": "Sonova (SOON.SW)",
    "SANN.SW": "Sandoz (SANN.SW)",
    "BEAN.SW": "Belimo (BEAN.SW)",
    "SIGN.SW": "SIG Group (SIGN.SW)",
    "KNIN.SW": "Kuehne+Nagel (KNIN.SW)",
    "DKSH.SW": "DKSH (DKSH.SW)",
    "BUBN.SW": "Bucher Industries (BUCHER.SW)",
    "SFZN.SW": "Siegfried (SFZN.SW)",
    "LISP.SW": "Chocoladefabriken Lindt (LISP.SW)",
    "BANB.SW": "Bachem (BANB.SW)",
}


def get_smim_stocks():
    """Fetch SMIM (Swiss Mid-Cap) constituents from Wikipedia.

    Falls back to a static list if the scrape fails.
    SMIM tickers already include the .SW suffix on Wikipedia.
    """
    result = fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/Swiss_Market_Index_Mid",
        ticker_col="Ticker",
        name_col="Company",
        suffix="",  # Wikipedia SMIM table includes .SW suffix
    )
    if result:
        return result
    return dict(_SMIM_FALLBACK)
```

- [ ] **Step 4: Add SMIM to `load_stock_options` in data_fetch.py**

In `src/data_fetch.py`, add the import:

```python
from src.stocks import get_smim_stocks
```

And add to the `sources` list in `load_stock_options()`:

```python
        ("Switzerland — SMIM", get_smim_stocks),
```

Place it after `("Switzerland — SMI", get_smi_stocks)`.

- [ ] **Step 5: Add SMIM to sidebar `_MARKETS` list**

In `src/ui/sidebar.py` line 29-33, add `"Switzerland — SMIM"` after `"Switzerland — SMI"`:

```python
_MARKETS = [
    "US — S&P 500", "UK — FTSE 100", "Germany — DAX", "France — CAC 40",
    "Switzerland — SMI", "Switzerland — SMIM", "Netherlands — AEX", "Spain — IBEX 35",
    "Sweden — OMX 30",
    "ETFs", "REITs", "Bonds", "Emerging Markets", "Crypto", "Commodities",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_stocks.py tests/test_data_fetch.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/stocks.py src/data_fetch.py src/ui/sidebar.py tests/test_stocks.py
git commit -m "feat: add SMIM (Swiss Mid-Cap) to stock search"
```

---

### Task 4: Async Ticker Validation in Sidebar

**Files:**
- Modify: `src/ui/sidebar.py`

- [ ] **Step 1: Add validation to the add-position submit handler**

In `src/ui/sidebar.py`, find the add-position submit handler. After the user submits a ticker, before adding it to the portfolio, add an async validation step.

Find the section where the ticker is being added to the portfolio (look for where `on_mutation` is called after adding a lot). Before that, add validation:

```python
async def _validate_ticker(ticker: str) -> bool:
    """Check if a ticker returns data from the provider."""
    from src.data_fetch import get_provider
    try:
        result = await run.io_bound(
            lambda: get_provider().get_price_history_short(ticker)
        )
        return not result.empty
    except Exception:
        return False
```

In the submit handler, if the ticker is NOT in `all_tickers` (freeform entry), call the validation:

```python
if ticker not in all_tickers:
    valid = await _validate_ticker(ticker)
    if not valid:
        ui.notify("Ticker not found — check the symbol and try again", type="warning")
        return
```

- [ ] **Step 2: Test manually** — start the app, type a garbage ticker in the sidebar search, submit. Verify warning notification appears.

- [ ] **Step 3: Commit**

```bash
git add src/ui/sidebar.py
git commit -m "feat: validate freeform ticker entry before adding to portfolio"
```

---

## Track 2: Comparison Chart Toggles + In-App Alerts

### Task 5: Ticker Toggle Pills on Comparison Chart

**Files:**
- Modify: `src/ui/overview.py:430-571`

- [ ] **Step 1: Add ticker pill row to `build_comparison`**

In `src/ui/overview.py`, inside the `build_comparison` function, after the controls row (line 453) and before `chart_container` (line 455), add the pill container:

```python
    # ── Ticker toggle pills ──
    ticker_visibility: dict[str, bool] = {t: True for t in portfolio}
    pill_container = ui.row().classes("w-full items-center gap-1 flex-wrap").style(
        "overflow-x:auto;padding:4px 0;margin:0;"
    )
```

- [ ] **Step 2: Build the pill rendering function**

Add inside `build_comparison`, after the `ticker_visibility` declaration:

```python
    def _render_pills():
        pill_container.clear()
        with pill_container:
            for ticker in portfolio:
                color = portfolio_color_map.get(ticker, "#3B82F6")
                active = ticker_visibility[ticker]
                opacity = "1" if active else "0.35"
                text_style = "text-decoration:line-through;" if not active else ""

                with ui.button(on_click=lambda t=ticker: _toggle_ticker(t)).props(
                    "flat dense no-caps"
                ).style(
                    f"opacity:{opacity};border:1px solid {color}40;border-radius:20px;"
                    f"padding:2px 10px;font-size:11px;color:#F1F5F9;"
                    f"background:{'rgba(0,0,0,0)' if not active else color + '15'};"
                    f"transition:all 0.2s ease;min-height:0;line-height:1.4;"
                ):
                    ui.html(
                        f'<span style="display:inline-flex;align-items:center;gap:4px;">'
                        f'<span style="width:6px;height:6px;border-radius:50%;background:{color};'
                        f'display:inline-block;"></span>'
                        f'<span style="{text_style}">{ticker}</span></span>'
                    )

            # Select All / None buttons (styled as text links)
            ui.html(
                f'<span style="font-size:10px;color:#64748B;margin-left:8px;">|</span>'
            )
            ui.button("All", on_click=lambda: _set_all(True)).props(
                "flat dense no-caps size=xs"
            ).style("font-size:10px;color:#94A3B8;min-height:0;padding:0 4px;")
            ui.html('<span style="font-size:10px;color:#64748B;">/</span>')
            ui.button("None", on_click=lambda: _set_all(False)).props(
                "flat dense no-caps size=xs"
            ).style("font-size:10px;color:#94A3B8;min-height:0;padding:0 4px;")
```

- [ ] **Step 3: Add toggle handlers**

```python
    async def _toggle_ticker(ticker: str):
        ticker_visibility[ticker] = not ticker_visibility[ticker]
        _render_pills()
        await _debounced_update()

    async def _set_all(visible: bool):
        for t in ticker_visibility:
            ticker_visibility[t] = visible
        _render_pills()
        await _debounced_update()
```

- [ ] **Step 4: Filter traces in update_chart based on visibility**

Inside the existing `update_chart()` function, after the figure is built (after `fig = build_comparison_chart(...)` around line 536), add:

```python
        # Apply ticker visibility toggles — match by trace name, not index
        for trace in fig.data:
            for ticker, visible in ticker_visibility.items():
                if ticker in trace.name:
                    trace.visible = True if visible else "legendonly"
                    break
```

- [ ] **Step 5: Call `_render_pills()` after pill_container is created**

Add `_render_pills()` right after the pill_container definition to render the initial state.

- [ ] **Step 6: Test manually** — start the app with the sample portfolio, go to Overview, verify pills appear, click one to hide a trace, click "None" then "All".

- [ ] **Step 7: Commit**

```bash
git add src/ui/overview.py
git commit -m "feat: ticker toggle pills on comparison chart"
```

---

### Task 6: Alert Rule Engine

**Files:**
- Create: `src/alerts.py`
- Create: `tests/test_alerts.py`

- [ ] **Step 1: Write failing tests for alert rules**

```python
# tests/test_alerts.py
"""Tests for in-app alert rules."""
import pytest
import pandas as pd
from src.alerts import Alert, check_concentration, check_correlation


def test_concentration_triggers_when_above_threshold():
    weights = {"AAPL": 0.45, "MSFT": 0.30, "GOOGL": 0.25}
    alerts = check_concentration(weights, threshold=0.30)
    assert len(alerts) >= 1
    assert alerts[0].severity == "critical"
    assert "AAPL" in alerts[0].message


def test_concentration_no_alert_when_below_threshold():
    weights = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}
    alerts = check_concentration(weights, threshold=0.30)
    assert len(alerts) == 0


def test_correlation_triggers_when_above_threshold():
    # Create correlated price data
    dates = pd.date_range("2025-01-01", periods=252, freq="B")
    import numpy as np
    np.random.seed(42)
    base = np.cumsum(np.random.randn(252)) + 100
    price_data = {
        "AAPL": pd.DataFrame({"Close": base}, index=dates),
        "MSFT": pd.DataFrame({"Close": base * 1.1 + np.random.randn(252) * 0.5}, index=dates),
    }
    alerts = check_correlation(price_data, threshold=0.80)
    assert len(alerts) >= 1
    assert alerts[0].severity == "warning"


def test_correlation_no_alert_when_below_threshold():
    dates = pd.date_range("2025-01-01", periods=252, freq="B")
    import numpy as np
    np.random.seed(42)
    price_data = {
        "AAPL": pd.DataFrame({"Close": np.cumsum(np.random.randn(252)) + 100}, index=dates),
        "GLD": pd.DataFrame({"Close": np.cumsum(np.random.randn(252)) + 50}, index=dates),
    }
    alerts = check_correlation(price_data, threshold=0.95)
    assert len(alerts) == 0


def test_correlation_skips_with_insufficient_data():
    alerts = check_correlation({}, threshold=0.85)
    assert len(alerts) == 0


def test_alert_dataclass_fields():
    a = Alert(severity="warning", title="Test", message="msg", rule_id="test_rule")
    assert a.severity == "warning"
    assert a.rule_id == "test_rule"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_alerts.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/alerts.py`**

```python
# src/alerts.py
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


def check_concentration(
    weights: dict[str, float],
    threshold: float = 0.30,
) -> list[Alert]:
    """Flag positions above threshold % of portfolio.

    Args:
        weights: {ticker: decimal weight} e.g. {"AAPL": 0.45}
        threshold: decimal threshold (0.30 = 30%)
    """
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


def check_correlation(
    price_data: dict[str, pd.DataFrame],
    threshold: float = 0.85,
) -> list[Alert]:
    """Flag ticker pairs with correlation above threshold.

    Only evaluates if price data is already available (warm cache).
    Args:
        price_data: {ticker: DataFrame with 'Close' column}
        threshold: correlation threshold (0.85 = 85%)
    """
    tickers = [t for t, df in price_data.items()
               if not df.empty and "Close" in df.columns and len(df) >= 30]
    if len(tickers) < 2:
        return []

    # Build return matrix
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


def evaluate_all(
    weights: dict[str, float],
    price_data: dict[str, pd.DataFrame] | None = None,
    settings: dict | None = None,
) -> list[Alert]:
    """Run all alert rules and return combined results.

    Args:
        weights: {ticker: decimal weight}
        price_data: {ticker: 1y DataFrame} or None if cache is cold
        settings: {"concentration_threshold": 0.30, "correlation_threshold": 0.85}
    """
    s = settings or {}
    alerts = []
    alerts.extend(check_concentration(weights, s.get("concentration_threshold", 0.30)))
    if price_data:
        alerts.extend(check_correlation(price_data, s.get("correlation_threshold", 0.85)))
    return alerts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/test_alerts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/alerts.py tests/test_alerts.py
git commit -m "feat: alert rule engine (concentration + correlation)"
```

---

### Task 7: Alert UI Component

**Files:**
- Create: `src/ui/alerts.py`
- Modify: `src/ui/overview.py` (integrate alert banner at top)

- [ ] **Step 1: Create `src/ui/alerts.py`**

```python
# src/ui/alerts.py
"""Alert banner UI component for the Overview tab."""

from __future__ import annotations

from nicegui import ui

from src.alerts import Alert, evaluate_all
from src.theme import ACCENT, TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM, BG_CARD, BORDER
from src.ui.shared import load_portfolio, save_portfolio
from src.cache import long_cache_analytics

_SEVERITY_COLORS = {
    "critical": "#EF4444",
    "warning": "#F59E0B",
    "info": "#3B82F6",
}


def _get_alert_state(portfolio_data: dict) -> dict:
    """Read alert state from portfolio dict."""
    return portfolio_data.get("_alerts", {})


def _save_alert_state(portfolio_data: dict, alert_state: dict) -> None:
    """Write alert state into portfolio dict and persist."""
    portfolio_data["_alerts"] = alert_state
    save_portfolio(portfolio_data)


def render_alert_banner(
    portfolio: dict,
    weights: dict[str, float],
    portfolio_data: dict,
) -> None:
    """Render alert banner at the top of Overview tab.

    Args:
        portfolio: {ticker: [lots]} for computing alerts
        weights: {ticker: decimal weight} for concentration check
        portfolio_data: raw portfolio dict (for reading/writing _alerts state)
    """
    # Read alert settings and snapshots
    alert_state = _get_alert_state(portfolio_data)
    settings = alert_state.get("settings", {})
    dismissed = set(alert_state.get("dismissed", []))

    # Check which price data is warm in cache (don't trigger fetches).
    # We probe long_cache_analytics directly using cachetools' default hashkey.
    # COUPLING NOTE: this assumes fetch_analytics_history uses @cached(long_cache_analytics)
    # with the default key function (hashkey). If that decorator changes to use
    # lenient_key or a custom key, this probe will silently miss cached data.
    warm_price_data = {}
    for ticker in portfolio:
        from cachetools.keys import hashkey
        key = hashkey(ticker)
        if key in long_cache_analytics:
            warm_price_data[ticker] = long_cache_analytics[key]

    # Evaluate alerts
    alerts = evaluate_all(weights, warm_price_data or None, settings)

    # Filter out dismissed alerts
    active_alerts = [a for a in alerts if a.rule_id not in dismissed]

    # Save current snapshot
    alert_state["snapshots"] = {
        "weights": {t: round(w, 4) for t, w in weights.items()},
    }
    _save_alert_state(portfolio_data, alert_state)

    if not active_alerts:
        return

    # Render banner
    with ui.column().classes("w-full").style(
        f"background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;"
        f"padding:12px 16px;margin-bottom:12px;"
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.html(
                f'<span style="font-size:12px;font-weight:600;color:{TEXT_PRIMARY};">'
                f'Portfolio Alerts</span>'
            )
            # Gear icon for settings
            settings_visible = {"show": False}
            settings_container = ui.column().classes("w-full")

            def _toggle_settings():
                settings_visible["show"] = not settings_visible["show"]
                settings_container.set_visibility(settings_visible["show"])

            ui.button(icon="settings", on_click=_toggle_settings).props(
                "flat dense round size=xs"
            ).style(f"color:{TEXT_DIM};")

        # Alert items
        for alert in active_alerts:
            color = _SEVERITY_COLORS.get(alert.severity, "#94A3B8")
            with ui.row().classes("w-full items-center gap-2").style("margin-top:6px;"):
                ui.html(
                    f'<span style="width:6px;height:6px;border-radius:50%;background:{color};'
                    f'display:inline-block;flex-shrink:0;"></span>'
                )
                ui.html(
                    f'<span style="font-size:11px;color:{TEXT_MUTED};flex:1;">'
                    f'{alert.message}</span>'
                )
                # Dismiss button
                def _dismiss(rule_id=alert.rule_id):
                    dismissed.add(rule_id)
                    alert_state["dismissed"] = list(dismissed)
                    _save_alert_state(portfolio_data, alert_state)
                    ui.notify("Alert dismissed", type="info")

                ui.button(icon="close", on_click=_dismiss).props(
                    "flat dense round size=xs"
                ).style(f"color:{TEXT_DIM};opacity:0.5;")

        # Settings panel (hidden by default)
        with settings_container:
            settings_container.set_visibility(False)
            ui.separator().style("margin:8px 0;")
            ui.html(f'<span style="font-size:10px;color:{TEXT_DIM};font-weight:600;">Alert Thresholds</span>')
            with ui.row().classes("gap-4 items-center").style("margin-top:4px;"):
                conc = ui.number(
                    "Concentration %", value=settings.get("concentration_threshold", 0.30) * 100,
                    min=10, max=80, step=5,
                ).props("dense outlined").style("width:140px;font-size:11px;")
                corr = ui.number(
                    "Correlation %", value=settings.get("correlation_threshold", 0.85) * 100,
                    min=50, max=99, step=5,
                ).props("dense outlined").style("width:140px;font-size:11px;")

                def _save_settings():
                    settings["concentration_threshold"] = conc.value / 100
                    settings["correlation_threshold"] = corr.value / 100
                    alert_state["settings"] = settings
                    _save_alert_state(portfolio_data, alert_state)
                    ui.notify("Thresholds saved", type="positive")

                ui.button("Save", on_click=_save_settings).props(
                    "dense flat no-caps size=sm"
                ).style(f"color:{ACCENT};font-size:11px;")
```

- [ ] **Step 2: Integrate alert banner into Overview tab**

In `src/ui/overview.py`, find the `build_overview` function (the main entry point for the Overview tab). At the top of the tab content, before the KPI cards, add:

```python
    from src.ui.alerts import render_alert_banner

    # Compute weights for alert evaluation
    if not df.empty:
        alert_weights = {}
        for ticker in portfolio:
            ticker_value = df[df["Ticker"] == ticker]["Total Value"].sum()
            alert_weights[ticker] = ticker_value / df["Total Value"].sum()
        portfolio_data = load_portfolio()
        render_alert_banner(portfolio, alert_weights, portfolio_data)
```

Add the import at the top of the file:
```python
from src.ui.shared import load_portfolio
```

- [ ] **Step 3: Test manually** — load sample portfolio, add one large position (>30%), go to Overview, verify alert banner appears. Click dismiss, verify it goes away. Click gear, change thresholds.

- [ ] **Step 4: Commit**

```bash
git add src/ui/alerts.py src/ui/overview.py
git commit -m "feat: in-app alert banner on Overview tab"
```

---

### Task 8: Run Full Test Suite + Manual Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Manual smoke test**

Start the app:
```bash
cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python main.py
```

Verify:
1. Load sample portfolio — all tabs render without errors
2. Overview: alert banner shows if any position > 30%
3. Overview: comparison chart has ticker toggle pills, clicking toggles traces
4. Overview: "All" and "None" links work
5. Sidebar: search dropdown includes SMIM stocks (search for "BAER" or "Julius")
6. Sidebar: type a garbage ticker, submit — warning notification appears

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: smoke test fixes for workstream A"
```
