"""Forecast & Diagnostics tabs for the NiceGUI dashboard.

Renders Monte Carlo portfolio/position outlooks and model diagnostics
using NiceGUI widgets and Plotly charts.
"""

import numpy as np
import pandas as pd
from nicegui import run, ui

from src.charts import (
    C_POSITIVE,
    C_NEGATIVE,
    C_AMBER,
    build_fan_chart,
    build_portfolio_histogram,
    build_qq_plot,
)
from src.data_fetch import (
    cached_run_monte_carlo_backtest,
    cached_run_monte_carlo_portfolio,
    cached_run_monte_carlo_ticker,
    fetch_company_name,
    fetch_simulation_history,
)
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.monte_carlo import compute_var_cvar, compute_model_diagnostics
from src.portfolio import build_portfolio_df
from src.theme import (
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_DIM,
    TEXT_FAINT,
    TEXT_SECONDARY,
    BG_CARD,
    BG_PILL,
    BORDER,
    BORDER_SUBTLE,
    BG_TOPBAR,
    GREEN,
    RED,
    AMBER,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_header(title: str) -> None:
    """Render a styled section header matching the dashboard aesthetic."""
    ui.html(
        f'<div style="font-size:10px; font-weight:700; letter-spacing:0.12em; '
        f'text-transform:uppercase; color:{TEXT_MUTED}; margin:18px 0 8px 0;">'
        f'{title}</div>'
    )


def _section_intro(text: str) -> None:
    """Render explanatory text below a section header."""
    ui.html(
        f'<p style="font-size:12px; color:{TEXT_DIM}; line-height:1.6; '
        f'margin:0 0 12px 0;">{text}</p>'
    )


def _caption(text: str) -> None:
    """Render small muted caption text."""
    ui.html(
        f'<p style="font-size:10px; color:{TEXT_FAINT}; line-height:1.5; '
        f'margin:8px 0 0 0;">{text}</p>'
    )


def _metric_card(label: str, value: str, sub: str = "") -> None:
    """Render a single metric card matching the theme."""
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    ui.html(
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _fmt(value, fmt_str: str, na: str = "\u2014") -> str:
    """Format a numeric value, returning a dash for None/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return na
    return fmt_str.format(value)


def _empty_state(msg: str) -> None:
    """Render an empty-state message."""
    ui.html(
        f'<p style="color:{TEXT_DIM}; font-size:13px; padding:20px 0;">{msg}</p>'
    )


# ── Data loading helpers ─────────────────────────────────────────────────────

def _load_simulation_data(tickers: list) -> dict:
    """Fetch 5-year simulation history for all tickers."""
    results = {}
    for t in tickers:
        hist = fetch_simulation_history(t)
        if not hist.empty:
            results[t] = hist
    return results


def _get_start_prices(tickers: list, price_data: dict, currency: str) -> dict:
    """Get current prices in base currency for all tickers with data."""
    start_prices: dict[str, float] = {}
    for t in tickers:
        hist = price_data.get(t)
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        close = hist["Close"].dropna()
        if close.empty:
            continue
        fx, _ = get_fx_rate(get_ticker_currency(t), currency)
        start_prices[t] = float(close.iloc[-1]) * fx
    return start_prices


# ── Portfolio Outlook ────────────────────────────────────────────────────────

def _render_portfolio_outlook(
    portfolio: dict,
    tickers: list,
    price_data: dict,
    currency: str,
    currency_symbol: str,
) -> None:
    """Render the Portfolio Outlook section with fan chart and risk metrics."""
    start_prices = _get_start_prices(tickers, price_data, currency)
    if not start_prices:
        _section_header("Portfolio Outlook")
        _empty_state(
            "Not enough price history to run the portfolio outlook. "
            "Each position needs at least 1 year of data."
        )
        return

    portfolio_mc = cached_run_monte_carlo_portfolio(
        portfolio=portfolio,
        price_data=price_data,
        start_prices_base=start_prices,
        horizon_days=504,
    )
    if not portfolio_mc:
        _section_header("Portfolio Outlook")
        _empty_state(
            "Not enough price history to run the portfolio outlook. "
            "Each position needs at least 1 year of data."
        )
        return

    # Header row with horizon toggle
    horizon_options = {"3 months": 63, "6 months": 126, "1 year": 252}
    with ui.row().classes("w-full items-center justify-between"):
        with ui.column().style("gap:2px;"):
            _section_header("Portfolio Outlook")
            ui.html(f'<div style="font-size:12px;color:{TEXT_DIM};">Monte Carlo simulation</div>')
        horizon_label = ui.toggle(
            list(horizon_options.keys()), value="1 year"
        ).props("dense size=sm no-caps")

    # Containers that update on horizon change
    with ui.column().classes("chart-card w-full").style("gap:8px; min-height:400px;") as chart_card:
        chart_container = ui.column().classes("w-full").style("gap:8px;")
    metrics_container = ui.column().classes("w-full").style("gap:8px;")
    with ui.column().classes("chart-card w-full").style("gap:8px; min-height:350px;") as hist_card:
        hist_container = ui.column().classes("w-full").style("gap:8px;")
    caption_container = ui.column().classes("w-full").style("gap:8px;")

    def _update_portfolio_outlook() -> None:
        day_idx = horizon_options[horizon_label.value]
        pct = portfolio_mc["percentiles"]
        paths = portfolio_mc["portfolio_paths"]
        paths_i = portfolio_mc["portfolio_paths_i"]
        start_val = portfolio_mc["start_value"]
        dates = list(portfolio_mc["dates"])[:day_idx + 1]

        sliced_pct = {
            k: list(pct[k].iloc[:day_idx + 1])
            for k in ("p10", "p25", "p50", "p75", "p90")
        }

        # Fan chart
        fig = build_fan_chart(
            dates=dates,
            percentiles=sliced_pct,
            hlines=[{
                "y": start_val,
                "text": f"Current  {currency_symbol}{start_val:,.0f}",
                "color": "#9CA3AF",
                "width": 1,
            }],
            currency_symbol=currency_symbol,
            y_title=f"Portfolio Value ({currency})",
            title="Portfolio Outlook",
        )

        chart_container.clear()
        with chart_container:
            ui.plotly(fig).classes("w-full")

        # Risk metrics
        end_vals = paths[:, day_idx]
        end_vals_i = paths_i[:, day_idx]
        vc = compute_var_cvar(end_vals, start_val)

        corr_p10 = float(sorted(end_vals)[int(len(end_vals) * 0.10)])
        indep_p10 = float(sorted(end_vals_i)[int(len(end_vals_i) * 0.10)])
        div_diff = indep_p10 - corr_p10
        # div_diff > 0 means correlation widens downside (bad)
        # div_diff < 0 means correlation narrows downside (good)
        div_is_benefit = div_diff < 0

        hl = horizon_label.value
        metrics_container.clear()
        with metrics_container:
            with ui.element("div").classes("metric-grid-4"):
                ui.html(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">Value at Risk 95% ({hl})</div>'
                    f'<div class="metric-value" style="color:#DC2626;">{currency_symbol}{abs(vc["var_abs"]):,.0f}</div>'
                    f'<div class="metric-sub">5% of simulations lost more than this — actual losses could be larger ({vc["var"] * 100:.1f}%)</div>'
                    f'</div>'
                )
                ui.html(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">Average tail loss ({hl})</div>'
                    f'<div class="metric-value" style="color:#DC2626;">{currency_symbol}{abs(vc["cvar_abs"]):,.0f}</div>'
                    f'<div class="metric-sub">Average loss in the worst 5% of scenarios ({vc["cvar"] * 100:.1f}%)</div>'
                    f'</div>'
                )
                p10_chg = (corr_p10 - start_val) / start_val * 100
                ui.html(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">10th percentile outcome</div>'
                    f'<div class="metric-value" style="color:#D97706;">{currency_symbol}{corr_p10:,.0f}</div>'
                    f'<div class="metric-sub">10% of simulations ended below this — not a worst case ({p10_chg:+.1f}%)</div>'
                    f'</div>'
                )
                if div_is_benefit:
                    div_color = GREEN
                    div_title = "Correlation effect"
                    div_sub = f"Correlation narrows downside in simulation"
                else:
                    div_color = RED
                    div_title = "Correlation effect"
                    div_sub = f"Correlation widens downside in simulation"
                ui.html(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">{div_title}</div>'
                    f'<div class="metric-value" style="color:{div_color};">'
                    f'{currency_symbol}{abs(div_diff):,.0f}</div>'
                    f'<div class="metric-sub" style="color:{div_color};">{div_sub}</div>'
                    f'</div>'
                )

        # Histogram
        p50_val = float(pct["p50"].iloc[day_idx])
        p90_val = float(pct["p90"].iloc[day_idx])
        fig_hist = build_portfolio_histogram(
            end_values=end_vals,
            start_value=start_val,
            p10=corr_p10,
            p50=p50_val,
            p90=p90_val,
            currency_symbol=currency_symbol,
            base_currency=currency,
            title="Distribution of Simulated Outcomes",
        )

        hist_container.clear()
        with hist_container:
            _section_header("Distribution of Simulated Outcomes")
            _section_intro(
                "Each bar represents the number of simulated portfolios that ended within that value range. "
                "A tall central peak means outcomes are tightly clustered; a wide spread means high uncertainty."
            )
            ui.plotly(fig_hist).classes("w-full")

        caption_container.clear()
        with caption_container:
            excluded = [t for t in tickers if t not in portfolio_mc["tickers_used"]]
            excluded_text = (
                f" Excluded (insufficient history): {', '.join(excluded)}."
                if excluded else ""
            )
            _caption(
                f"Based on {portfolio_mc['train_days']} trading days of calibration data. "
                f"Positions included: {', '.join(portfolio_mc['tickers_used'])}."
                f"{excluded_text} "
                f"This is a statistical model, not financial advice."
            )

    # Initial render and bind update
    _update_portfolio_outlook()
    horizon_label.on_value_change(lambda _: _update_portfolio_outlook())


# ── Position Outlook ─────────────────────────────────────────────────────────

def _render_position_outlook(
    portfolio: dict,
    tickers: list,
    price_data: dict,
    currency: str,
    currency_symbol: str,
) -> None:
    """Render the Position Outlook section with per-ticker fan chart."""
    # Header row with controls
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as _ex:
        _name_pairs = list(_ex.map(lambda t: (t, fetch_company_name(t)), tickers))
    ticker_names = {t: f"{t} \u2014 {name}" for t, name in _name_pairs}
    horizon_options = {"3 months": 63, "6 months": 126, "1 year": 252}
    lookback_options = {"1 year": 252, "2 years": 504, "5 years": None}

    with ui.row().classes("w-full items-center justify-between"):
        with ui.column().style("gap:2px;"):
            _section_header("Position Outlook")
            ui.html(f'<div style="font-size:12px;color:{TEXT_DIM};">Per-ticker Monte Carlo simulation</div>')
        with ui.row().classes("items-center").style("gap:10px;"):
            ticker_select = ui.select(
                options=ticker_names,
                value=tickers[0],
                label="Position",
            ).style("min-width:200px;")
            horizon_toggle = ui.toggle(
                list(horizon_options.keys()), value="6 months"
            ).props("dense size=sm no-caps")
            lookback_toggle = ui.toggle(
                list(lookback_options.keys()), value="2 years"
            ).props("dense size=sm no-caps")

    with ui.column().classes("chart-card w-full").style("gap:8px; min-height:400px;") as pos_chart_card:
        chart_container = ui.column().classes("w-full").style("gap:8px;")
    metrics_container = ui.column().classes("w-full").style("gap:8px;")
    info_container = ui.column().classes("w-full").style("gap:8px;")

    def _update_position_outlook() -> None:
        ticker = ticker_select.value
        horizon_days = horizon_options[horizon_toggle.value]
        lookback_days = lookback_options[lookback_toggle.value]

        hist = price_data.get(ticker, pd.DataFrame())
        fx, _ = get_fx_rate(get_ticker_currency(ticker), currency)

        current_price = None
        close = hist["Close"].dropna() if not hist.empty and "Close" in hist.columns else pd.Series(dtype=float)
        if not close.empty:
            current_price = float(close.iloc[-1]) * fx

        chart_container.clear()
        metrics_container.clear()
        info_container.clear()

        if current_price is None or current_price <= 0:
            with chart_container:
                _empty_state(f"Could not fetch a current price for {ticker}.")
            return

        result = cached_run_monte_carlo_ticker(
            ticker=ticker,
            hist=hist,
            current_price=current_price,
            horizon_days=horizon_days,
            lookback_days=lookback_days,
        )

        if not result:
            with chart_container:
                _empty_state(
                    f"{ticker} does not have enough price history for the selected calibration window. "
                    f"Try a shorter calibration window."
                )
            return

        # Build portfolio DF to get buy prices for hlines
        df = build_portfolio_df(portfolio, currency)
        lots = df[df["Ticker"] == ticker][["Purchase", "Buy Price", "Shares"]].copy() if not df.empty else pd.DataFrame()
        wavg = None
        if not lots.empty:
            wavg = float(
                (lots["Buy Price"] * lots["Shares"]).sum() / lots["Shares"].sum()
            )

        hlines = []
        if wavg is not None:
            hlines.append({
                "y": wavg,
                "text": f"Avg buy {currency_symbol}{wavg:,.2f}",
                "color": "#D97706",
                "width": 1.5,
            })
        if len(lots) > 1:
            for _, lot_row in lots.iterrows():
                hlines.append({
                    "y": lot_row["Buy Price"],
                    "text": f"Lot {int(lot_row['Purchase'])}  {currency_symbol}{lot_row['Buy Price']:,.2f}",
                    "color": "#9CA3AF",
                    "width": 1,
                    "position": "top right",
                })

        fig = build_fan_chart(
            dates=list(result["dates"]),
            percentiles=result["percentiles"],
            hlines=hlines,
            currency_symbol=currency_symbol,
            y_title=f"Price ({currency})",
            title=f"{ticker} Outlook",
        )

        with chart_container:
            ui.plotly(fig).classes("w-full")

        # Probability metrics
        end_paths = result["end_paths"]
        with metrics_container:
            with ui.element("div").classes("metric-grid-3"):
                if wavg is not None:
                    prob_above = float((end_paths >= wavg).mean() * 100)
                    _metric_card(
                        "Simulated prob. above avg buy",
                        f"{prob_above:.0f}%",
                        f"Model-based — vs {currency_symbol}{wavg:,.2f}",
                    )

                prob_above_current = float((end_paths >= current_price).mean() * 100)
                _metric_card(
                    "Simulated prob. above current",
                    f"{prob_above_current:.0f}%",
                    f"Model-based — vs {currency_symbol}{current_price:,.2f}",
                )

                _metric_card(
                    "Annualised volatility",
                    f"{result['sigma_annual']:.1f}%",
                )

        with info_container:
            flag = result["flag"]
            if flag.get("fat_tailed"):
                ui.html(
                    f'<div style="background:rgba(220,38,38,0.1); border:1px solid rgba(220,38,38,0.3); '
                    f'border-radius:6px; padding:10px 14px; margin:8px 0;">'
                    f'<span style="color:{RED}; font-weight:600;">{ticker} has fat-tailed returns</span>'
                    f'<span style="color:{TEXT_DIM}; font-size:12px;"> '
                    f'(excess kurtosis: {flag["kurtosis"]:.1f}). '
                    f'Extreme price moves occur more often than a normal distribution predicts. '
                    f'The confidence bands above will understate the real tail risk for this position.</span>'
                    f'</div>'
                )
            _caption(
                f"Based on {result['train_days']} trading days of {ticker} history "
                f"({lookback_toggle.value} window). Historical average annual return: "
                f"{result['mu_annual']:+.1f}%/yr, typical annual swing: {result['sigma_annual']:.1f}%/yr. "
                f"This is a statistical model, not financial advice."
            )

    _update_position_outlook()
    ticker_select.on_value_change(lambda _: _update_position_outlook())
    horizon_toggle.on_value_change(lambda _: _update_position_outlook())
    lookback_toggle.on_value_change(lambda _: _update_position_outlook())


# ── Backtest ─────────────────────────────────────────────────────────────────

def _render_backtest(
    portfolio: dict,
    tickers: list,
    price_data: dict,
    currency: str,
    currency_symbol: str,
) -> None:
    """Render the Monte Carlo Backtest section."""
    _section_header("Monte Carlo Backtest")
    _section_intro(
        "Tests the Monte Carlo model against your portfolio's actual history to check whether "
        "the simulated confidence bands were well-calibrated."
    )

    bt = cached_run_monte_carlo_backtest(portfolio, price_data)
    if not bt:
        _empty_state(
            "Not enough price history to run the backtest. "
            "Each position needs at least 2 years of trading data."
        )
        return

    # KPI row
    with ui.element("div").classes("metric-grid-3"):
        _metric_card("Hit Rate \u2014 80% band", f"{bt['hit_rate_80']}%")
        _metric_card("Hit Rate \u2014 50% band", f"{bt['hit_rate_50']}%")
        _metric_card("Training window", f"{bt['train_days']} days")

    # Fan chart legend + chart in a card
    with ui.column().classes("chart-card w-full"):
        _section_intro(
            "\u2022 <b>Dark band</b> \u2014 50% of simulated portfolios ended up in this range.<br>"
            "\u2022 <b>Light band</b> \u2014 80% of simulations fell here.<br>"
            "\u2022 <b>Dashed line</b> \u2014 the median simulation path.<br>"
            "\u2022 <b>Black line</b> \u2014 what your portfolio actually did."
        )

        fig = build_fan_chart(
            dates=list(bt["sim_dates"]),
            percentiles=bt["percentiles"],
            actual=bt["actual"],
            currency_symbol=currency_symbol,
            y_title=f"Portfolio Value ({currency})",
            title="Monte Carlo Backtest",
        )
        ui.plotly(fig).classes("w-full")

    # Per-ticker reliability table in a card
    with ui.column().classes("chart-card w-full"):
        _section_header("Model Reliability by Position")
        _section_intro(
            "Shows how well the model performed for each position individually over the past year. "
            "\u2022 <b>Hit Rate 80% CI</b> \u2014 should be close to 80% for a well-calibrated model.<br>"
            "\u2022 <b>Kurtosis</b> \u2014 excess kurtosis above 3 means unusually fat tails.<br>"
            "\u2022 <b>Fat-tailed</b> \u2014 fires when kurtosis exceeds 3; treat bands with extra scepticism."
        )

        def _reliability_label(hit_rate_80: float) -> str:
            if hit_rate_80 >= 80:
                return "Well-calibrated"
            if hit_rate_80 >= 65:
                return "Under-calibrated"
            return "Poorly-calibrated"

        def _reliability_color(label: str) -> str:
            if label == "Well-calibrated":
                return GREEN
            if label == "Under-calibrated":
                return AMBER
            return RED

        def _kurtosis_color(val) -> str:
            if not isinstance(val, (int, float)):
                return TEXT_SECONDARY
            if val <= 1:
                return GREEN
            if val <= 3:
                return AMBER
            return RED

        rows_html = ""
        for t in bt["tickers_used"]:
            hr = bt["ticker_hit_rates"].get(t, {})
            flag = bt["ticker_flags"].get(t, {})
            hr80 = hr.get("hit_rate_80", 0)
            hr50 = hr.get("hit_rate_50", 0)
            kurt = flag.get("kurtosis")
            skew = flag.get("skewness")
            fat = "Yes" if flag.get("fat_tailed") else "No"
            rel = _reliability_label(hr80)
            rel_color = _reliability_color(rel)
            kurt_color = _kurtosis_color(kurt)

            rows_html += (
                f'<tr>'
                f'<td style="font-weight:600;">{t}</td>'
                f'<td>{_fmt(hr80, "{:.1f}%")}</td>'
                f'<td>{_fmt(hr50, "{:.1f}%")}</td>'
                f'<td style="color:{kurt_color};">{_fmt(kurt, "{:.2f}")}</td>'
                f'<td>{_fmt(skew, "{:.2f}")}</td>'
                f'<td>{fat}</td>'
                f'<td style="color:{rel_color}; font-weight:600;">{rel}</td>'
                f'</tr>'
            )

        ui.html(f'''
        <div class="table-wrap">
        <table>
            <thead><tr>
                <th scope="col">Ticker</th>
                <th scope="col">Hit Rate 80% CI</th>
                <th scope="col">Hit Rate 50% CI</th>
                <th scope="col">Kurtosis</th>
                <th scope="col">Skewness</th>
                <th scope="col">Fat-tailed</th>
                <th scope="col">Reliability</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        ''')

    _caption(
        f"Simulated using up to {bt['train_days']} days of historical log-returns calibrated before "
        f"{bt['split_date']}. The model assumes returns are normally distributed and that historical "
        f"correlations are stable. Positions flagged as fat-tailed violate the normality assumption; "
        f"their confidence bands will understate tail risk. This is a statistical model, not financial advice."
    )


# ── Model Diagnostics ───────────────────────────────────────────────────────

def _render_model_diagnostics(
    tickers: list,
    price_data: dict,
) -> None:
    """Render the Model Diagnostics section with tests and QQ plots."""
    _section_header("Model Diagnostics")
    _section_intro(
        "The Monte Carlo simulation assumes that daily returns are <b>normally distributed</b> "
        "and <b>independent</b> from one day to the next. This section tests both assumptions "
        "for each position.<br><br>"
        "\u2022 <b>Jarque-Bera test</b> \u2014 checks whether returns follow a normal distribution. "
        "p < 0.05 means non-normal (fat tails or skew).<br>"
        "\u2022 <b>Ljung-Box test</b> \u2014 checks whether returns are independent (no autocorrelation). "
        "p < 0.01 means autocorrelated.<br>"
        "\u2022 <b>QQ plot</b> \u2014 points on the red line = normal. Tails curving away = fat tails."
    )

    diag = compute_model_diagnostics({t: price_data[t] for t in tickers if t in price_data})
    if not diag:
        _empty_state("Not enough price history to run diagnostics.")
        return

    diag_tickers = [t for t in tickers if t in diag]
    if not diag_tickers:
        _empty_state("No tickers with sufficient data for diagnostics.")
        return

    # Ticker selector for QQ plot
    ticker_names = {
        t: f"{t} \u2014 {diag[t]['verdict'][:50]}" if len(diag[t]["verdict"]) > 50
        else f"{t} \u2014 {diag[t]['verdict']}"
        for t in diag_tickers
    }
    qq_select = ui.select(
        options=ticker_names,
        value=diag_tickers[0],
        label="Select ticker for QQ plot",
    ).style("min-width:300px;")

    # Side by side: QQ plot | test table
    with ui.row().classes("diag-row w-full"):
        # QQ plot column
        with ui.column().classes("chart-card w-full"):
            _section_header("QQ Plot")
            _section_intro(
                "Points on the red line = normal distribution. "
                "Tails curving away = fat tails \u2014 extreme moves occur more often than expected."
            )

            qq_chart_container = ui.column().classes("w-full")
            qq_caption_container = ui.column().classes("w-full")

            def _update_qq() -> None:
                t = qq_select.value
                d = diag[t]
                fig = build_qq_plot(d["qq_theoretical"], d["qq_observed"], t)

                qq_chart_container.clear()
                with qq_chart_container:
                    ui.plotly(fig).classes("w-full")

                qq_caption_container.clear()
                with qq_caption_container:
                    _caption(
                        f"{t}: Jarque-Bera p = {d['jb_pvalue']:.4f} "
                        f"({'normal' if d['jb_normal'] else 'non-normal'}), "
                        f"Ljung-Box p = {d['lb_pvalue']:.4f} "
                        f"({'independent' if d['lb_independent'] else 'autocorrelated'}). "
                        f"{d['verdict']}"
                    )

            _update_qq()
            qq_select.on_value_change(lambda _: _update_qq())

        # Test table column
        with ui.column().classes("chart-card w-full"):
            _section_header("Statistical Tests")
            _section_intro(
                "Summary of normality and independence tests for all positions."
            )

            rows_html = ""
            for t in diag_tickers:
                d = diag[t]
                jb_label = "Pass" if d["jb_normal"] else "Fail"
                lb_label = "Pass" if d["lb_independent"] else "Fail"
                jb_color = GREEN if d["jb_normal"] else RED
                lb_color = GREEN if d["lb_independent"] else RED

                rows_html += (
                    f'<tr>'
                    f'<td style="font-weight:600;">{t}</td>'
                    f'<td style="color:{jb_color}; font-weight:500;">{jb_label}</td>'
                    f'<td style="color:{lb_color}; font-weight:500;">{lb_label}</td>'
                    f'<td style="font-size:11px; color:{TEXT_DIM};">'
                    f'{d["verdict"][:60]}{"..." if len(d["verdict"]) > 60 else ""}</td>'
                    f'</tr>'
                )

            ui.html(f'''
            <div class="table-wrap">
            <table>
                <thead><tr>
                    <th scope="col">Ticker</th>
                    <th scope="col">Normality (JB)</th>
                    <th scope="col">Independence (LB)</th>
                    <th scope="col">Verdict</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            </div>
            ''')


# ── Public entry points ──────────────────────────────────────────────────────

async def build_forecast_tab(portfolio: dict, currency: str) -> None:
    """Render the full Forecast tab content using NiceGUI widgets.

    Parameters
    ----------
    portfolio : dict
        Mapping of ticker -> list of lot dicts (the session portfolio).
    currency : str
        Base display currency code, e.g. "USD", "GBP", "EUR".
    """
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")
    tickers = list(portfolio.keys())

    if not tickers:
        _empty_state("Add positions to your portfolio to see forecasts.")
        return

    _section_intro(
        "Monte Carlo simulations project possible future paths for your portfolio and individual "
        "positions. The fan charts show the range of likely outcomes based on historical return patterns."
    )

    # Load simulation data once for both sections (off the event loop)
    notification = ui.notification("Running simulations...", spinner=True, timeout=None)
    try:
        price_data = await run.io_bound(_load_simulation_data, tickers)
    finally:
        notification.dismiss()

    if not price_data:
        ui.notify("Could not load simulation data. Try reloading.", type="warning")
        _empty_state("No price data available for simulation. Check your positions and try reloading.")
        return

    _render_portfolio_outlook(portfolio, tickers, price_data, currency, currency_symbol)

    ui.html('<hr class="content-divider">')

    _render_position_outlook(portfolio, tickers, price_data, currency, currency_symbol)


async def build_diagnostics_tab(portfolio: dict, currency: str) -> None:
    """Render the full Diagnostics tab content using NiceGUI widgets.

    Parameters
    ----------
    portfolio : dict
        Mapping of ticker -> list of lot dicts (the session portfolio).
    currency : str
        Base display currency code, e.g. "USD", "GBP", "EUR".
    """
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")
    tickers = list(portfolio.keys())

    if not tickers:
        _empty_state("Add positions to your portfolio to see diagnostics.")
        return

    ui.html(
        f'<div style="background:{BG_PILL};border:1px solid {BORDER};border-radius:8px;'
        f'padding:12px 16px;margin-bottom:8px;">'
        f'<div style="font-size:12px;color:{TEXT_MUTED};line-height:1.6;">'
        f'<b style="color:{TEXT_PRIMARY};">For most users:</b> check the '
        f'<b style="color:{TEXT_PRIMARY};">Reliability</b> column in the table below. '
        f'"Well-calibrated" means the model\'s confidence bands matched historical outcomes. '
        f'The rest of this tab is for advanced users who want to verify the simulation assumptions.'
        f'</div></div>'
    )

    _section_intro(
        "Validates whether the Monte Carlo model's assumptions hold for your positions. "
        "The backtest checks calibration against actual history; the diagnostics test normality "
        "and independence of returns."
    )

    # Load simulation data once for both sections (off the event loop)
    notification = ui.notification("Running diagnostics...", spinner=True, timeout=None)
    try:
        price_data = await run.io_bound(_load_simulation_data, tickers)
    finally:
        notification.dismiss()

    if not price_data:
        ui.notify("Could not load simulation data. Try reloading.", type="warning")
        _empty_state("No price data available for diagnostics. Check your positions and try reloading.")
        return

    _render_backtest(portfolio, tickers, price_data, currency, currency_symbol)

    ui.html('<hr class="content-divider">')

    _render_model_diagnostics(tickers, price_data)
