# Portfolio Health & Stock Research — Design Spec

## Summary

Two structural changes to the dashboard:

1. **Portfolio Health tab** — replaces Risk & Analytics. Adds narrative diagnostics, a composite health score, and sector gap analysis on top of the existing metrics (which move to a collapsible section).
2. **Stock Research tab** — new tab for evaluating any ticker. Shows fundamentals, peer comparison, news, and a "Portfolio Fit Preview" showing how adding the stock would change the health score.

News integration via yfinance `.news` in both tabs. Tab count stays at 8 (one replaced, one added).

## Motivation

The dashboard is strong at analyzing existing holdings but weak at two things:
- **Interpreting risk data** — the current Risk tab shows raw metrics (beta, Sharpe, volatility) without explaining what they mean for the user's specific portfolio.
- **Evaluating new stocks** — there's no way to research a stock you don't own or to see how adding it would affect portfolio diversification.

User personas from the March 2026 feature expansion confirmed both gaps. The secondary segment (students/early-career) particularly struggles with raw metrics.

## Regulatory Constraint

MiFID II classifies investment advice as a regulated activity. The dashboard must remain an information tool, not an advisory tool. This constraint is structural, not just a disclaimer.

### Bright Lines — What the Tool Never Does

- Never says "buy", "sell", "add", or "remove" a specific stock
- Never ranks stocks as "best" or "worst"
- Never suggests specific allocation percentages for stocks not already owned
- Never curates, filters, or sentiment-labels news
- Never predicts price targets (analyst targets are sourced data, not ours)
- Never uses language like "opportunity", "undervalued", "strong buy"

### What the Tool Does

- Shows factual data: prices, ratios, correlations, sector classifications
- Shows mathematical calculations: HHI, volatility, weighted correlation
- Shows factual portfolio impact: "adding X changes your correlation by Y"
- Shows peer data: "here are other stocks in the same sector"
- Shows gaps: "you have 0% exposure to these sectors"

---

## 1. Portfolio Health Tab

Replaces the current Risk & Analytics tab (`src/ui/risk.py`).

### Layout (top to bottom)

#### 1.1 Health Score

Circular badge showing composite score 0–100. Below it: one-line description and an expandable "How is this calculated?" link.

#### 1.2 Key Findings

Narrative diagnostic cards with colored left border:
- **Red** — high-severity findings (e.g., "High concentration risk")
- **Amber** — medium-severity (e.g., "Sector imbalance")
- **Green** — positive findings (e.g., "Good geographic spread")

Each card has a headline and a plain-language explanation with the user's actual numbers. Example: "Your top 3 holdings (AAPL, ASML, SPY) account for 71% of portfolio value. A 20% drop in these would reduce your portfolio by ~14%."

Language is neutral and factual — describes what *is*, never what should be done.

Findings are generated from the health score components. The engine produces findings when:
- Any single holding exceeds 25% of portfolio value (concentration)
- Top 3 holdings exceed 65% of portfolio value (concentration)
- Any sector exceeds 50% of portfolio value (sector imbalance)
- More than 3 GICS sectors have 0% exposure (sector gaps)
- Weighted average pairwise correlation exceeds 0.6 (high correlation)
- Portfolio spans 3+ geographic regions (positive — geographic spread)
- Portfolio volatility is below S&P 500 (positive — stability)

#### 1.3 Sector Exposure

Horizontal bar chart showing portfolio weight per sector. Below the chart: a "No exposure" row listing sectors with 0% allocation as small tags.

This replaces and expands the existing sector breakdown chart from the Risk tab.

#### 1.4 Detailed Metrics (collapsed by default)

The existing analytics table (volatility, beta, Sharpe, max drawdown, P/E, dividend yield, 52-week range) in a collapsible section. Same data as the current Risk tab, collapsed by default so narrative findings get attention first.

Correlation heatmap below the table, also collapsible.

#### 1.5 Rebalancing Calculator

Moves here from the Risk tab unchanged. Sector-grouped target weights + deposit amount → buy-only suggestions.

### Disclaimer Banner

Visible amber banner at the top of the tab:

> **For informational purposes only.** This tool provides data and calculations to support your own research. It does not constitute financial advice, investment recommendations, or solicitation to buy or sell securities. Past performance does not predict future results. Always consult a qualified financial advisor before making investment decisions.

---

## 2. Health Score Methodology

Composite score from 0–100, computed from four equally-transparent components.

### Components

| Component | Weight | Metric | Formula |
|---|---|---|---|
| Diversification | 35% | Sector + geographic breadth | (sectors_held / 11 × 17.5) + (regions_held / 5 × 17.5) |
| Concentration | 30% | Capital distribution evenness | (1 − HHI) × 30, where HHI = Σ(weight²) |
| Correlation | 20% | Independence of holdings | (1 − weighted_avg_pairwise_corr) × 20 |
| Stability | 15% | Portfolio volatility vs benchmark | max(0, 15 × (1 − annualized_vol / 0.25)) |

### Component Details

**Diversification (35%)**
- Sector count: number of distinct GICS sectors held out of 11 (Energy, Materials, Industrials, Consumer Discretionary, Consumer Staples, Healthcare, Financials, IT, Communication Services, Utilities, Real Estate)
- Geographic count: number of distinct regions out of 5 (North America, Europe, UK, Asia-Pacific, Emerging Markets). Determined by ticker suffix (.L → UK, .DE/.PA/.AS → Europe, etc.) and yfinance country field. Best-effort mapping — tickers that can't be mapped default to North America.
- Score = (sectors / 11 × 17.5) + (regions / 5 × 17.5)

**Concentration (30%)**
- Herfindahl-Hirschman Index: sum of squared portfolio weights
- HHI = 1.0 means single stock, HHI = 1/N means perfectly equal weight
- Score = (1 − HHI) × 30
- Effective number of positions = 1/HHI (shown in explanation)

**Correlation (20%)**
- Weighted average pairwise Pearson correlation of daily log-returns, 1-year lookback
- Weights = product of the two positions' portfolio weights, normalized
- Score = (1 − avg_corr) × 20
- Requires at least 2 holdings with 60+ trading days of history; otherwise scores full marks (no data to penalize)

**Stability (15%)**
- Annualized portfolio volatility from daily returns (σ × √252)
- Benchmark cap set at 25% annualized (roughly the historical max for a diversified equity portfolio)
- Score = max(0, 15 × (1 − vol / 0.25))
- A portfolio with 12.5% vol scores ~7.5/15; a portfolio with 25%+ vol scores 0

### Color Coding

- Green: component score ≥ 70% of its maximum
- Amber: 40–70%
- Red: < 40%

### Expandable Methodology

When the user clicks "How is this calculated?", each component expands to show:
- **What it measures** — one sentence, no jargon
- **How it's calculated** — formula with the user's actual numbers plugged in
- **Why it matters** — one sentence on practical impact

### Score Language

The score measures diversification characteristics, not investment quality. UI language avoids value judgments:
- "Concentrated portfolio" not "bad portfolio"
- "Well-spread investments" not "good investments"

---

## 3. Stock Research Tab

New tab accessible from the main tab bar.

### Layout (top to bottom)

#### 3.1 Search Bar

Text input with autocomplete from existing `stock_options` dict (Wikipedia-scraped ticker lists). Reuses the same search infrastructure as the sidebar.

Recent searches shown as clickable tags to the right of the search bar. Stored in plain `app.storage.user` (ticker symbols are not sensitive data — no encryption needed).

#### 3.2 Company Header

Two-column: left shows company name, ticker, sector, country, currency. Right shows current price and daily change.

#### 3.3 Two-Column Body

**Left column — Fundamentals:**
- P/E Ratio (with sector median comparison)
- Dividend Yield (with sector median comparison)
- Market Cap (with size classification: mega/large/mid/small)
- Beta (with plain-language interpretation)
- 52-Week Range (with current percentile position)
- Analyst Target Price (with % upside/downside)

All data from yfinance `.info`. Sector medians computed from the Wikipedia-scraped peer list for the same GICS sector.

**Right column — Portfolio Fit Preview:**
- Current health score → projected health score if this stock were added
- Bullet points listing the factual impacts:
  - Sector exposure change (e.g., "Adds Healthcare exposure, currently 0%")
  - Correlation with existing holdings
  - Portfolio volatility change
  - Currency diversification change (if applicable)

The projection assumes the stock is added at a default 5% portfolio weight (this is configurable via a small input field).

#### 3.4 Price Chart

Plotly line or candlestick chart. Same component as Positions tab price chart. Time range selector: 1m, 3m, 1y, 3y, 5y.

#### 3.5 Peer Comparison Table

Table showing 3–5 stocks in the same GICS sector with: P/E, dividend yield, beta, 1-year return. The researched stock is highlighted. Peers selected by market cap proximity from the Wikipedia-scraped stock lists, cross-referenced with yfinance `.info["sector"]` to filter to same-sector peers. Sector lookups cached in `long_cache_fundamentals` (24h TTL) to avoid excessive API calls when building peer lists.

No ranking, no "best/worst" labels. Pure data comparison.

#### 3.6 News

Recent headlines from yfinance `.news` for this ticker. Chronological order, no filtering. Each headline shows title, publisher, time ago, and a link to the source article.

### Disclaimer Banner

Same amber banner as Portfolio Health tab.

---

## 4. News Integration

### Data Source

yfinance `Ticker.news` property. Returns list of dicts with: title, publisher, link, providerPublishTime, thumbnail.

### Locations

1. **Portfolio Health tab** — aggregated news for all tickers in the portfolio. Each headline tagged with its ticker (color-coded to match portfolio color map). Reverse chronological. Max 20 headlines.
2. **Research tab** — news for the single ticker being researched. Max 10 headlines.

### Caching

5-minute TTL using the existing `short_cache`. News fetched per-ticker via `_fetch_ticker_news(ticker)` cached function.

### Display Rules

- Chronological order only — no relevance ranking, no sentiment analysis
- Headlines are external links — open in new tab
- Publisher and relative time shown
- No thumbnails (keeps UI clean, avoids layout issues with missing images)
- No editorial text added by the dashboard

---

## 5. Technical Approach

### Files Changed

| File | Change |
|---|---|
| `src/ui/risk.py` | Rewrite → becomes `src/ui/health.py`. Existing metrics move to collapsible section. New: score, findings, sector exposure. |
| `src/ui/research.py` | New file. Search, fundamentals, portfolio fit, peers, news. |
| `src/data_fetch.py` | New functions: `fetch_ticker_news()`, `fetch_sector_peers()`, `fetch_sector_medians()`. |
| `src/portfolio.py` | New: `compute_health_score()`, `generate_findings()`, `simulate_addition()`. |
| `main.py` | Tab bar: rename "Risk & Analytics" → "Portfolio Health". Add "Research" tab. Update lazy loading. |
| `src/ui/guide.py` | Update documentation for new tabs. |

### New Dependencies

None. All data comes from yfinance (already in stack).

### Caching

- Health score: `long_cache_analytics` (24-hour TTL, invalidated on portfolio change)
- Ticker news: `short_cache` (5-minute TTL)
- Sector peers/medians: `long_cache_fundamentals` (24-hour TTL)
- Portfolio fit simulation: not cached (computed on demand, fast enough with cached inputs)

### Data Requirements

Health score requires:
- Portfolio weights (existing)
- GICS sector per ticker (existing via yfinance `.info["sector"]`)
- Country/region per ticker (existing via suffix heuristic + yfinance)
- 1-year daily returns per ticker (existing)
- Pairwise correlation matrix (existing, computed in Risk tab)
- Portfolio-level volatility (existing)

Research tab requires:
- yfinance `.info` for searched ticker (existing pattern)
- yfinance `.news` for searched ticker (new, trivial)
- Sector peer list from Wikipedia-scraped stock lists (existing data, new lookup logic)
- Health score simulation with hypothetical addition (new, uses existing computation)

---

## 6. Scope Exclusions

- No sentiment analysis on news
- No price predictions or forecasts (Forecast tab already handles Monte Carlo)
- No stock screener / filter tool (future consideration)
- No watchlist feature (future consideration)
- No social features or community signals
- No integration with brokers or trading APIs
- No changes to existing tabs beyond Risk → Health rename
