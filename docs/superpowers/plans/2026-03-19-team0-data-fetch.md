# Team 0: Data Fetch Changes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `sector`, `targetMeanPrice`, and `dividendRate` to the `fetch_fundamentals()` return dict so Teams 1, 3, and 4 can consume them without modifying `data_fetch.py`.

**Architecture:** Single function modification in `data_fetch.py`. The `.info` dict from yfinance already contains all three fields — `dividendRate` is even fetched (line 59) but only used to derive `Div Yield (%)`. We just need to include the raw values in the return dict.

**Tech Stack:** yfinance, cachetools

**Spec:** `docs/superpowers/specs/2026-03-19-feature-expansion-design.md` — Section 10 (Agent Architecture, "Shared Data Conflict")

---

## File Map

- **Modify:** `src/data_fetch.py:51-100` — `fetch_fundamentals()` return dict
- **Test:** `tests/test_data_fetch.py` — new file

---

### Task 1: Add new fields to `fetch_fundamentals()`

**Files:**
- Modify: `src/data_fetch.py:51-100`

- [ ] **Step 1: Read the current `fetch_fundamentals()` function**

Read `src/data_fetch.py` lines 51-100 to understand the current return dict structure.

- [ ] **Step 2: Add `sector`, `targetMeanPrice`, and `dividendRate` to the return dict**

In `fetch_fundamentals()`, after the existing field extraction, add:

```python
sector = info.get("sector", None)
target_price = info.get("targetMeanPrice", None)
```

Note: `div_rate` is already extracted at line 59 as `info.get("dividendRate")`. It's used to compute yield but never returned.

Add to the return dict (around line 95-100):
```python
"Sector": sector if sector else "Unknown",
"Target Price": target_price,
"Dividend Rate": div_rate,  # raw annual dividend per share (native currency)
```

For London-listed stocks (ticker ends with `.L`), apply GBX/100 conversion to `Target Price` — same pattern as `1-Year Low` and `1-Year High`.

- [ ] **Step 3: Verify no existing consumers break**

The return dict is consumed by:
- `src/ui/risk.py` — reads `P/E Ratio`, `Div Yield (%)`, `1-Year Low`, `1-Year High`, `Current Price`, `1-Year Position`
- `src/excel_export.py` — reads same fields for Fundamentals sheet
- `src/ui/overview.py` — reads `Current Price`

Adding new keys to the dict is purely additive. No existing consumers will break.

- [ ] **Step 4: Run the app to verify nothing crashes**

Run: `python main.py`
Expected: App starts normally. Risk & Analytics tab loads without errors. Positions tab loads without errors.

- [ ] **Step 5: Commit**

```bash
git add src/data_fetch.py
git commit -m "feat: add sector, target price, and dividend rate to fundamentals"
```

---

### Task 2: Write tests for the new fields

**Files:**
- Create: `tests/test_data_fetch.py`

- [ ] **Step 1: Create test file with mock**

```python
"""Tests for data_fetch.fetch_fundamentals()."""
from unittest.mock import patch, MagicMock
from src.data_fetch import fetch_fundamentals


def _mock_info(overrides=None):
    """Return a realistic yfinance .info dict."""
    base = {
        "trailingPE": 28.5,
        "dividendRate": 0.96,
        "dividendYield": 0.005,
        "fiftyTwoWeekLow": 142.0,
        "fiftyTwoWeekHigh": 198.5,
        "currentPrice": 176.0,
        "sector": "Technology",
        "targetMeanPrice": 195.0,
    }
    if overrides:
        base.update(overrides)
    return base


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_returns_sector(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    result = fetch_fundamentals("AAPL")
    assert result["Sector"] == "Technology"


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_returns_target_price(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    result = fetch_fundamentals("AAPL")
    assert result["Target Price"] == 195.0


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_returns_dividend_rate(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    result = fetch_fundamentals("AAPL")
    assert result["Dividend Rate"] == 0.96


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_missing_sector_defaults_to_unknown(mock_ticker):
    mock_ticker.return_value.info = _mock_info({"sector": None})
    result = fetch_fundamentals("SPY")
    assert result["Sector"] == "Unknown"


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_missing_target_price_returns_none(mock_ticker):
    mock_ticker.return_value.info = _mock_info({"targetMeanPrice": None})
    result = fetch_fundamentals("BTC-USD")
    assert result["Target Price"] is None


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_gbx_target_price_divided_by_100(mock_ticker):
    mock_ticker.return_value.info = _mock_info({"targetMeanPrice": 15000.0})
    result = fetch_fundamentals("SHEL.L")
    assert result["Target Price"] == 150.0  # 15000 / 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_fetch.py -v`
Expected: FAIL — new keys not yet in return dict (if step 1 of Task 1 hasn't been done yet) or PASS (if Task 1 is already complete)

- [ ] **Step 3: Ensure tests pass after Task 1 implementation**

Run: `pytest tests/test_data_fetch.py -v`
Expected: All 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_data_fetch.py
git commit -m "test: add tests for new fundamentals fields"
```
