"""Guide tab – plain-language explanations of every dashboard feature."""

from nicegui import ui

from src.theme import TEXT_PRIMARY, TEXT_SECONDARY


def build_guide_tab():
    """Plain-language explanations of every dashboard feature."""
    with ui.column().classes("w-full").style(f"gap:var(--grid-gap);color:{TEXT_PRIMARY}"):

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Getting Started").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown(
                "Pick a stock market from the sidebar, search for a company, "
                "enter how many shares you bought and when. The app looks up prices "
                "automatically. You can add the same stock multiple times if you "
                "bought at different dates."
            ).classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("The Numbers at the Top (KPI Cards)").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""| Metric | What it means |
|--------|--------------|
| **Total Portfolio Value** | What all your shares are worth right now, converted to your chosen currency. |
| **Today's Change** | How much the total value moved since the market closed yesterday. Green = up, red = down. |
| **Total Return** | The difference between what your portfolio is worth today (including any dividends received) and what you originally paid. The percentage below it is that same number as a fraction of your total investment. |
| **Positions** | How many different stocks you own. If you bought the same stock twice, that counts as one position but two purchases. |""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Charts").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""- **Portfolio Allocation** — a bar chart showing what percentage of your money is in each stock. \
If one bar is much longer than the rest, your portfolio is concentrated — a big move in that stock affects everything.
- **Portfolio Comparison** — every stock is set to 100 at the start so you can compare growth fairly. \
A stock at 130 has grown 30%; a stock at 85 has fallen 15%. Use the time range buttons to zoom in or out.
- **Price History** — the actual price chart for each stock. The orange dashed line is what you paid; \
the grey dashed line marks the date you bought it. If the price line is above the orange line, you are in profit on that position.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Portfolio Health").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""This tab replaces the old Risk & Analytics view with a more accessible, narrative-driven approach.

**Health Score (0–100)** — a composite score measuring how well-diversified your portfolio is. It is *not* a measure of \
investment quality — a score of 40 means "concentrated", not "bad." Click "How is this calculated?" to see the formula \
with your actual numbers. The score has four components:

- **Diversification (35%)** — how many different sectors and geographic regions you cover. More spread = higher score.
- **Concentration (30%)** — how evenly your money is distributed. One stock at 70% scores low; ten stocks at 10% each scores high. \
Uses the Herfindahl-Hirschman Index (HHI), the same formula economists use to measure market concentration.
- **Correlation (20%)** — whether your stocks move independently or all rise and fall together. \
Lower average correlation = better diversification benefit.
- **Stability (15%)** — how much your portfolio value swings day-to-day compared to the market. Lower volatility = higher score.

**Key Findings** — plain-language observations about your portfolio. Red cards flag high-risk patterns (e.g., heavy \
concentration in one stock), amber cards flag areas to watch (e.g., sector imbalance), and green cards highlight strengths \
(e.g., good geographic spread). These are factual observations, not recommendations.

**Sector Exposure** — which industries your money is spread across, with bars showing portfolio weight per sector. \
Sectors with 0% exposure are listed at the bottom.

**Detailed Metrics** — the full analytics table (volatility, Sharpe ratio, beta, P/E, etc.) and correlation heatmap \
from the old Risk tab. Collapsed by default so the narrative findings get attention first.

**Rebalancing Calculator** — set target weights and a deposit amount to see buy-only suggestions. \
This is a calculation tool, not a recommendation.

**Portfolio News** — recent headlines for all your holdings, pulled from Yahoo Finance. Shown in chronological order \
with no filtering or ranking. Click any headline to read the full article.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Stock Research").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""Search for any stock — including ones you do not own — to see its fundamentals, how it compares \
to sector peers, and how adding it would affect your portfolio's health score.

- **Fundamentals** — P/E ratio, dividend yield, market cap, beta, 52-week range, and analyst target price. \
Where available, sector median values are shown for context (e.g., "Above sector median of 28.1").
- **Portfolio Fit Preview** — shows your current health score and what it would become if you added this stock at 5% \
of your portfolio. Lists specific impacts: new sector exposure, correlation with your holdings, volatility change. \
This is a mathematical projection, not a recommendation to buy.
- **Peer Comparison** — a table of 3–5 stocks in the same sector, showing the same metrics side by side. \
No ranking or scoring — just data for your own comparison.
- **News** — recent headlines for the stock from Yahoo Finance, in chronological order.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Risk Metrics (in Detailed Metrics)").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""These are standard measures used by professional investors, now inside the collapsible \
"Detailed Metrics" section of the Portfolio Health tab:

- **Volatility** — how much the price swings day to day, expressed as a yearly percentage. Higher = more unpredictable.
- **Worst Drop (Max Drawdown)** — the biggest peak-to-trough fall in the past year.
- **Return/Risk Score (Sharpe Ratio)** — how much return you earn per unit of risk. Above 1 is good, above 2 is excellent.
- **Market Sensitivity (Beta)** — how much the stock moves relative to the overall market (S&P 500).
- **Correlation** — whether two stocks tend to go up and down together (close to 1.0) or move independently (close to 0).
- **P/E Ratio** — how many years of current earnings you are paying for.
- **Dividend Yield** — the annual dividend payment as a percentage of the stock price.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Monte Carlo Simulation (the Fan Charts)").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""Imagine replaying the stock market 1,000 times. Each replay uses the stock's real historical \
behaviour — how much it typically moves each day — but shuffles the order of good and bad days randomly. \
The result is a fan of possible futures:

- The **dark band** is where 50% of the replays ended up — the most likely zone.
- The **light band** covers 80% of replays — a wider range of plausible outcomes.
- The **dashed line** is the median — exactly half of the replays were above, half below.

If the fan is wide, there is a lot of uncertainty. If it is narrow, the stock has been relatively stable historically.

**Portfolio Outlook** adds two extra metrics:
- **VaR (Value at Risk) 95%** — in the worst 5% of replays, the portfolio lost at least this much. \
Think of it as a loss threshold that only 5% of simulated outcomes exceeded.
- **CVaR (Expected Shortfall) 95%** — the average loss in those worst 5% of replays. Always worse than VaR; \
this is what tail risk actually costs on average.

**Position Outlook** does the same thing for a single stock. The probability figure tells you: out of 1,000 replays, \
how many ended above your buy price?""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
            ui.label("Model Diagnostics — When to Be Sceptical").classes("text-lg font-bold").style(f"color:{TEXT_PRIMARY}")
            ui.markdown("""The simulation assumes that daily price changes follow a bell curve (normal distribution) and \
are independent from one day to the next. These assumptions are often wrong for real stocks:

- **Jarque-Bera: Fail** means the stock has fatter tails than a bell curve — extreme days (crashes or rallies) \
happen more often than the model expects. The fan chart will understate how bad a bad day can really be.
- **Ljung-Box: Fail** means today's return is correlated with recent days — there is momentum or mean-reversion \
that the model ignores.
- **QQ Plot** — if the dots follow the red line, the bell-curve assumption holds. Where the dots curve away from \
the line, the real distribution has heavier tails.

Most individual stocks will fail the normality test. That does not make the simulation useless — it means you should \
treat the edges of the fan as optimistic. Real tail risk is likely larger than shown.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")
