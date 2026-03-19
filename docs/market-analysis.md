# Market Analysis — Portfolio Dashboard

Last updated: 2026-03-19

> Pricing data based on publicly available information as of early 2025. Verify current pricing before making final decisions.

---

## 1. Target Customer Segments

| Segment | Size estimate | Pain point we solve | Willingness to pay |
|---|---|---|---|
| **Retail self-directed investors** | Largest pool. Outgrew spreadsheets, intimidated by Bloomberg/Refinitiv. | One-click multi-market portfolio view with real analytics, not just P&L tracking. | $5-15/mo — price-sensitive, need free tier to convert. |
| **Semi-pro traders / finance professionals** | Smaller but high-value. Personal portfolios alongside work. | Monte Carlo, model diagnostics, cross-market FX comparison — tools they know from work but don't have at home. | $15-30/mo — will pay for quant features if credible. |
| **Small RIAs / independent advisors** | ~15k registered IAs in the US alone, plus EU equivalents. | Lightweight client reporting without enterprise software costs. Excel export matters here. | $20-50/mo — business expense, ROI-driven. |
| **Finance students & academics** | Large volume, low revenue. | Hands-on portfolio analytics with real model diagnostics (QQ plots, Jarque-Bera). Teaching tool. | Free or <$5/mo. Institutional licenses possible. |

**Primary focus:** Segments 1 and 2 drive volume. Segment 3 drives ARPU. Segment 4 is marketing/brand.

---

## 2. Competitive Landscape

| Product | Pricing | Key features | Limitations |
|---|---|---|---|
| **Sharesight** | Free (1 portfolio/10 holdings), Starter $15/mo, Investor $24/mo, Expert $39/mo | Tax reporting (CGT, dividends), broker imports, multi-currency, performance tracking | No Monte Carlo or risk analytics. Tax-focused, not analysis-focused. Expensive for what you get. No self-hosting. |
| **Portfolio Performance** (open source) | Free | Desktop Java app. Full transaction tracking, multiple benchmarks, taxonomy/classifications, currency support | Desktop-only (no web/mobile). Steep learning curve. No forecasting or simulation. No cloud sync. Ugly UI. |
| **Stock Events** | Free + Premium ~$8/mo | Dividend tracking, calendar view, portfolio sync, clean mobile UI | Dividend-focused — minimal analytics. No risk metrics, no simulation. Mobile-first, weak on desktop. |
| **SimplePortfolio** | Free + Pro ~$5/mo | Clean UI, basic portfolio tracking, performance charts | Very basic — no analytics beyond simple returns. Limited market coverage. |
| **Ziggma** | Free + Premium ~$10/mo | Portfolio score, risk analysis, stock screener, dividend tracking | Risk analysis is shallow (no simulation). Screener is the main draw, not portfolio analytics. US-heavy. |
| **Delta** | Free + Pro $10/mo | Multi-asset (crypto, stocks, ETFs), broker connections, clean mobile UI | Tracking-focused, not analytics-focused. No simulation or diagnostics. Acquired by eToro — data privacy concerns. |
| **Kubera** | $15/mo (no free tier) | Net worth tracker, multi-asset (real estate, crypto, bank accounts), clean UI | Not a portfolio analytics tool — it's a wealth aggregator. No risk metrics, no forecasting. |

### Key takeaway

Most competitors are **portfolio trackers** (record transactions, show P&L). Almost none offer **portfolio analytics** (simulation, risk decomposition, model diagnostics). The gap is real.

The closest competitor in spirit is Portfolio Performance, but it's a Java desktop app with a dated UI and no forecasting. Sharesight is the most established SaaS but focuses on tax, not analytics.

---

## 3. Competitive Wedge

What this dashboard does that competitors don't:

| Feature | Us | Sharesight | Portfolio Perf. | Ziggma | Delta | Stock Events |
|---|---|---|---|---|---|---|
| Monte Carlo simulation | Yes | No | No | No | No | No |
| Model diagnostics (JB, LB, QQ) | Yes | No | No | No | No | No |
| Multi-market in one tool (8 indices) | Yes | Partial | Yes | US-heavy | Yes | Partial |
| FX-adjusted comparison charts | Yes | Basic | Yes | No | No | No |
| Full Excel export (analytics + MC) | Yes | CSV only | Yes | No | No | No |
| Self-hostable (Docker) | Yes | No | Yes (desktop) | No | No | No |
| No ads, no data selling | Yes | Yes | Yes | Unclear | No (eToro) | Unclear |
| PWA / installable | Yes | No | No | No | Native app | Native app |

**The pitch in one sentence:** "The portfolio analytics tool that finance professionals would build for themselves — Monte Carlo simulation, real model diagnostics, multi-market FX support, and full data export. Self-hostable, no ads, no data selling."

---

## 4. Recommended Free / Paid Tier Split

### Free tier (convert and retain)

- Up to **5 positions**
- Overview tab (KPI cards, allocation chart, comparison chart)
- Positions tab (price history, basic table)
- 1-year price history lookback
- Single display currency
- Community support

### Paid tier — "Pro" (core revenue)

- **Unlimited positions**
- Risk & Analytics tab (heatmap, fundamentals, risk attribution)
- Forecast tab (Monte Carlo simulation, fan charts, horizon analysis)
- Diagnostics tab (QQ plots, Jarque-Bera, Ljung-Box, backtest fan, reliability)
- Full Excel export (analytics, MC results, fundamentals)
- Extended price history (5+ years)
- All display currencies
- Priority data refresh
- Email support

### Potential future tier — "Advisor" (segment 3)

- Multi-portfolio management
- Client-branded PDF reports
- API access
- White-label option
- Priority support / onboarding

### Rationale

The free tier must be useful enough to demonstrate value (overview + positions covers the "outgrew spreadsheets" crowd). The paid tier gates the quant features that are the actual differentiator — users who need Monte Carlo and diagnostics know what they are and will pay for them. Excel export behind the paywall is standard practice (Sharesight does the same with detailed reports).

---

## 5. Pricing Benchmarks

| Competitor | Free tier | Paid monthly | Paid yearly (per month) |
|---|---|---|---|
| Sharesight Starter | 10 holdings | $15/mo | ~$12.50/mo |
| Sharesight Expert | — | $39/mo | ~$31/mo |
| Ziggma Premium | Limited | ~$10/mo | ~$8/mo |
| Stock Events Premium | Basic | ~$8/mo | ~$6/mo |
| Delta Pro | Basic | ~$10/mo | ~$7/mo |
| Kubera | No free tier | $15/mo | $12.50/mo |
| SimplePortfolio Pro | Basic | ~$5/mo | ~$4/mo |
| Portfolio Performance | Full (free) | — | — |

### Recommended pricing

| Tier | Monthly | Yearly |
|---|---|---|
| **Free** | $0 | $0 |
| **Pro** | **$12/mo** | **$96/yr ($8/mo)** |
| Advisor (future) | $29/mo | $240/yr ($20/mo) |

**Why $12/mo:**
- Undercuts Sharesight Starter ($15) while offering more analytics.
- Above the "impulse buy" apps (Stock Events, SimplePortfolio) — justified by quant features they lack.
- The yearly discount to $8/mo competes directly with Ziggma/Delta while offering significantly more depth.
- Low enough that finance professionals won't expense-report it — they'll just pay, reducing friction.

**Alternative: usage-based addon.** If Monte Carlo simulations are computationally expensive at scale, consider keeping the base Pro at $8/mo and charging $4/mo as a "Simulation Pack" addon. This lets cost-conscious users get risk analytics without simulation, and heavy users pay for compute.

---

## 6. Go-to-Market Priorities

1. **Launch on Product Hunt / Hacker News** — self-hostable + Docker + no-data-selling angle resonates strongly with these audiences.
2. **Finance subreddits** (r/investing, r/portfolios, r/financialindependence) — the "outgrew spreadsheets" crowd lives here.
3. **Finance educator partnerships** — offer free academic licenses in exchange for curriculum integration.
4. **Content marketing** — "Why your portfolio tracker doesn't show you risk" style posts. The diagnostics features are inherently educational.
5. **Open-source the core** (optional, high-impact) — open-source the analytics engine, monetize the hosted SaaS. This is the Portfolio Performance playbook but with a modern web UI.
