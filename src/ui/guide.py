"""Guide tab – plain-language explanations of every dashboard feature."""

from nicegui import ui

from src.theme import TEXT_PRIMARY, TEXT_SECONDARY


def build_guide_tab():
    """Plain-language explanations of every dashboard feature."""
    with ui.column().classes("w-full gap-6 p-4").style(f"color:{TEXT_PRIMARY}"):

        ui.label("Getting Started").classes("text-xl font-bold")
        ui.markdown(
            "Pick a stock market from the sidebar, search for a company, "
            "enter how many shares you bought and when. The app looks up prices "
            "automatically. You can add the same stock multiple times if you "
            "bought at different dates."
        ).classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        ui.html('<hr class="content-divider">')
        ui.label("The Numbers at the Top (KPI Cards)").classes("text-xl font-bold")
        ui.markdown("""| Metric | What it means |
|--------|--------------|
| **Total Portfolio Value** | What all your shares are worth right now, converted to your chosen currency. |
| **Today's Change** | How much the total value moved since the market closed yesterday. Green = up, red = down. |
| **Total Return** | The difference between what your portfolio is worth today (including any dividends received) and what you originally paid. The percentage below it is that same number as a fraction of your total investment. |
| **Positions** | How many different stocks you own. If you bought the same stock twice, that counts as one position but two purchases. |""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        ui.html('<hr class="content-divider">')
        ui.label("Charts").classes("text-xl font-bold")
        ui.markdown("""- **Portfolio Allocation** — a bar chart showing what percentage of your money is in each stock. \
If one bar is much longer than the rest, your portfolio is concentrated — a big move in that stock affects everything.
- **Portfolio Comparison** — every stock is set to 100 at the start so you can compare growth fairly. \
A stock at 130 has grown 30%; a stock at 85 has fallen 15%. Use the time range buttons to zoom in or out.
- **Price History** — the actual price chart for each stock. The orange dashed line is what you paid; \
the grey dashed line marks the date you bought it. If the price line is above the orange line, you are in profit on that position.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        ui.html('<hr class="content-divider">')
        ui.label("Risk & Analytics").classes("text-xl font-bold")
        ui.markdown("""These are standard measures used by professional investors. You do not need to understand all of them, but here is what the key ones mean:

- **Volatility** — how much the price swings day to day, expressed as a yearly percentage. Higher = more unpredictable. \
A stock with 25% volatility typically swings about 25% up or down in a year.
- **Worst Drop (Max Drawdown)** — the biggest peak-to-trough fall in the past year. If it says -35%, \
the stock lost 35% from its highest point before recovering.
- **Return/Risk Score (Sharpe Ratio)** — how much return you earn per unit of risk. Above 1 is good, \
above 2 is excellent, below 0 means the stock lost money.
- **Market Sensitivity (Beta)** — how much the stock moves relative to the overall market (S&P 500). \
Beta of 1.0 means it moves in lockstep. Above 1.0 means it swings more; below 1.0 means it is calmer.
- **Correlation** — whether two stocks tend to go up and down together (close to 1.0) or move independently \
(close to 0). Owning stocks with low correlation reduces overall portfolio risk.
- **P/E Ratio** — how many years of current earnings you are paying for. A P/E of 20 means you pay 20x \
this year's profit. Lower can mean cheaper; higher can mean the market expects fast growth.
- **Dividend Yield** — the annual dividend payment as a percentage of the stock price. A 3% yield means you \
receive roughly 3% of your investment back as cash each year.""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        ui.html('<hr class="content-divider">')
        ui.label("Monte Carlo Simulation (the Fan Charts)").classes("text-xl font-bold")
        ui.markdown("""Imagine replaying the stock market 1,000 times. Each replay uses the stock's real historical \
behaviour — how much it typically moves each day — but shuffles the order of good and bad days randomly. \
The result is a fan of possible futures:

- The **dark band** is where 50% of the replays ended up — the most likely zone.
- The **light band** covers 80% of replays — a wider range of plausible outcomes.
- The **dashed line** is the median — exactly half of the replays were above, half below.

If the fan is wide, there is a lot of uncertainty. If it is narrow, the stock has been relatively stable historically.

**Portfolio Outlook** adds two extra metrics:
- **VaR (Value at Risk) 95%** — in the worst 5% of replays, the portfolio lost at least this much. \
Think of it as a "bad month" scenario.
- **CVaR (Expected Shortfall) 95%** — the average loss in those worst 5% of replays. Always worse than VaR; \
this is what tail risk actually costs on average.

**Position Outlook** does the same thing for a single stock. The probability figure tells you: out of 1,000 replays, \
how many ended above your buy price?""").classes("text-sm").style(f"color:{TEXT_SECONDARY}")

        ui.html('<hr class="content-divider">')
        ui.label("Model Diagnostics — When to Be Sceptical").classes("text-xl font-bold")
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
