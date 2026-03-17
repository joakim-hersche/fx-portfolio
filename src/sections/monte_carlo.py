"""Monte Carlo sections — Backtest, Portfolio Outlook, Position Outlook."""

import pandas as pd
import streamlit as st

from src.charts import (
    C_POSITIVE, C_NEGATIVE, C_AMBER,
    build_fan_chart, build_portfolio_histogram, build_qq_plot,
)
from src.data_fetch import cached_run_monte_carlo_ticker, fetch_company_name
from src.fx import get_ticker_currency, get_fx_rate
from src.monte_carlo import compute_var_cvar, compute_model_diagnostics
from src.ui import section_header, render_styled_table


# ── Backtest ─────────────────────────────────────────────────────────────────

def render_backtest(
    bt: dict | None,
    tickers: list,
    base_currency: str,
    currency_symbol: str,
) -> None:
    """Render the Monte Carlo Backtest section."""
    section_header("Monte Carlo Backtest")
    st.markdown(
        '<p class="section-intro">'
        'Tests the Monte Carlo model against your portfolio\'s actual history to check whether '
        'the simulated confidence bands were well-calibrated.'
        '</p>',
        unsafe_allow_html=True
    )
    with st.expander("How does the backtest work?"):
        st.markdown(
            '<p class="section-intro">'
            'It runs thousands of possible futures by randomly sampling from the asset\'s historical daily return distribution. '
            'Each simulated day draws a return that is plausible given how the stock has behaved in the past. '
            'Run 1,000 times, this produces a fan of outcomes — wide when the asset is volatile, narrow when it is stable.'
            '<br><br>'
            'Rather than only showing a forward projection (which cannot be verified), this section first tests the model against history. '
            'It takes data from up to 4 years ago, runs the simulation forward for one year using only that older data, '
            'then compares the simulated fan to what your portfolio actually did. '
            'If the model is well-calibrated, the actual value should fall inside the 80% band roughly 80% of the time.'
            '</p>',
            unsafe_allow_html=True
        )

    if not st.session_state.portfolio:
        st.info("Add positions to run the backtest.")
    elif not bt:
        st.warning(
            "Not enough price history to run the backtest. "
            "Each position needs at least 2 years of trading data."
        )
    else:
        # ── KPI row ──
        _col1, _col2, _col3 = st.columns(3)
        _col1.metric(
            "Hit Rate — 80% band",
            f"{bt['hit_rate_80']}%",
            help="Percentage of trading days over the past year where the actual portfolio value fell within the simulated 80% confidence interval (p10–p90).",
        )
        _col2.metric(
            "Hit Rate — 50% band",
            f"{bt['hit_rate_50']}%",
            help="Same check for the tighter 50% band (p25–p75). A well-calibrated model should be close to 50%.",
        )
        _col3.metric(
            "Training window",
            f"{bt['train_days']} days",
            help=f"Number of trading days used to calibrate the model (data before {bt['split_date']}).",
        )

        # ── Fan chart ──
        st.markdown(
            '<p class="section-intro">'
            '• <b>Dark band</b> — 50% of simulated portfolios ended up in this range. Think of it as the most likely zone.<br>'
            '• <b>Light band</b> — 80% of simulations fell here. Outcomes outside this band were the rare, extreme scenarios.<br>'
            '• <b>Dashed line</b> — the median simulation path (exactly half above, half below).<br>'
            '• <b>Black line</b> — what your portfolio actually did. If it stayed mostly inside the fan, the model was a good fit for your holdings.'
            '</p>',
            unsafe_allow_html=True
        )

        st.caption(
            "Assumes normally distributed returns and stable correlations. "
            "Fat-tailed assets (flagged below) may have higher real tail risk than shown. "
            "Not financial advice."
        )

        fig = build_fan_chart(
            dates=list(bt["sim_dates"]),
            percentiles=bt["percentiles"],
            actual=bt["actual"],
            currency_symbol=currency_symbol,
            y_title=f"Portfolio Value ({base_currency})",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        # ── Per-ticker reliability table ──
        section_header("Model Reliability by Position")
        st.markdown(
            '<p class="section-intro">'
            'Shows how well the model performed for each position individually over the past year. '
            'The same simulation is run per stock and compared to its actual price path.'
            '<br><br>'
            '• <b>Hit Rate 80% CI</b> — the percentage of trading days over the past year where the actual price stayed inside the simulated 80% band. '
            'A well-calibrated model scores close to 80%. Much lower means the real moves were more extreme than the model expected.<br>'
            '• <b>Hit Rate 50% CI</b> — the same check for the tighter middle band. Should be close to 50% for a well-calibrated model.<br>'
            '• <b>Kurtosis</b> — measures how "fat" the tails of the return distribution are compared to a normal distribution (which scores 0). '
            'A score above 3 means unusually large moves happen more often than the model assumes — the model will understate risk for that stock. '
            'Crypto, small caps, and individual growth stocks typically score high here.<br>'
            '• <b>Skewness</b> — measures whether big moves tend to be up or down. Positive means the distribution has a longer right tail (large gains are more common than large losses). '
            'Negative means the opposite — losses tend to be more extreme than gains.<br>'
            '• <b>Fat-tailed</b> — a flag that fires when kurtosis exceeds 3. Treat confidence bands for these positions with extra scepticism.'
            '</p>',
            unsafe_allow_html=True
        )

        def _reliability_label(hit_rate_80: float) -> str:
            if hit_rate_80 >= 80:  return "Good"
            if hit_rate_80 >= 65:  return "Moderate"
            return "Low"

        def _color_reliability(val: str) -> str:
            if val == "Good":     return f"color: {C_POSITIVE}; font-weight: 500"
            if val == "Moderate": return f"color: {C_AMBER}; font-weight: 500"
            return f"color: {C_NEGATIVE}; font-weight: 500"

        def _color_kurtosis(val) -> str:
            if not isinstance(val, (int, float)): return ""
            if val <= 1:  return f"color: {C_POSITIVE}"
            if val <= 3:  return f"color: {C_AMBER}"
            return f"color: {C_NEGATIVE}"

        _rel_rows = []
        for _t in bt["tickers_used"]:
            _hr   = bt["ticker_hit_rates"].get(_t, {})
            _flag = bt["ticker_flags"].get(_t, {})
            _rel_rows.append({
                "Ticker":          _t,
                "Hit Rate 80% CI": _hr.get("hit_rate_80"),
                "Hit Rate 50% CI": _hr.get("hit_rate_50"),
                "Kurtosis":        _flag.get("kurtosis"),
                "Skewness":        _flag.get("skewness"),
                "Fat-tailed":      "Yes" if _flag.get("fat_tailed") else "No",
                "Reliability":     _reliability_label(_hr.get("hit_rate_80", 0)),
            })

        _rel_df = pd.DataFrame(_rel_rows).set_index("Ticker")
        _styled_rel = (
            _rel_df.style
            .format({
                "Hit Rate 80% CI": "{:.1f}%",
                "Hit Rate 50% CI": "{:.1f}%",
                "Kurtosis":        "{:.2f}",
                "Skewness":        "{:.2f}",
            }, na_rep="—")
            .map(_color_reliability, subset=["Reliability"])
            .map(_color_kurtosis,    subset=["Kurtosis"])
        )
        render_styled_table(_styled_rel)

        st.caption(
            f"Simulated using up to {bt['train_days']} days of historical log-returns calibrated before "
            f"{bt['split_date']}. The model assumes returns are normally distributed and that historical "
            f"correlations are stable — both simplifications. Positions flagged as fat-tailed violate the "
            f"normality assumption; their confidence bands will understate tail risk. "
            f"This is a statistical model, not financial advice."
        )


# ── Model Diagnostics ───────────────────────────────────────────────────────

def render_model_diagnostics(
    price_data_5y: dict,
    tickers: list,
) -> None:
    """Render the Model Diagnostics section — tests whether MC assumptions hold."""
    section_header("Model Diagnostics")
    st.markdown(
        '<p class="section-intro">'
        'The Monte Carlo simulation assumes that daily returns are <b>normally distributed</b> '
        'and <b>independent</b> from one day to the next. When these assumptions break down, '
        'the model\'s confidence bands become unreliable. This section tests both assumptions '
        'for each of your positions and flags where the model is likely to mislead.'
        '<br><br>'
        '• <b>Jarque-Bera test</b> — checks whether returns follow a normal (bell-curve) distribution. '
        'A low p-value (< 0.05) means the data has fatter tails or more skew than a normal distribution allows. '
        'When this fails, extreme moves happen more often than the model expects.<br>'
        '• <b>Ljung-Box test</b> — checks whether today\'s return is statistically independent of recent days. '
        'A low p-value means returns are autocorrelated — there is momentum or mean-reversion that the model ignores.<br>'
        '• <b>QQ plot</b> — a visual check. If returns were perfectly normal, all points would sit on the red dashed line. '
        'Points curving away from the line at the edges reveal fat tails — the further the deviation, the worse the fit.'
        '</p>',
        unsafe_allow_html=True
    )

    if not st.session_state.portfolio:
        st.info("Add positions to run diagnostics.")
        return

    diag = compute_model_diagnostics({t: price_data_5y[t] for t in tickers if t in price_data_5y})
    if not diag:
        st.warning("Not enough price history to run diagnostics.")
        return

    # ── Build summary table rows ──
    def _color_pass_fail(val: str) -> str:
        if val == "Pass":
            return f"color: {C_POSITIVE}; font-weight: 500"
        return f"color: {C_NEGATIVE}; font-weight: 500"

    rows = []
    for t in tickers:
        d = diag.get(t)
        if d is None:
            continue
        rows.append({
            "Ticker":            t,
            "Normality (JB)":    "Pass" if d["jb_normal"] else "Fail",
            "JB p-value":        d["jb_pvalue"],
            "Independence (LB)": "Pass" if d["lb_independent"] else "Fail",
            "LB p-value":        d["lb_pvalue"],
            "Verdict":           d["verdict"],
        })

    if not rows:
        st.warning("No tickers with sufficient data for diagnostics.")
        return

    diag_df = pd.DataFrame(rows).set_index("Ticker")

    styled = (
        diag_df.style
        .format({"JB p-value": "{:.4f}", "LB p-value": "{:.4f}"})
        .map(_color_pass_fail, subset=["Normality (JB)", "Independence (LB)"])
    )

    # ── QQ plot selector ──
    diag_tickers = [t for t in tickers if t in diag]
    qq_ticker = st.selectbox(
        "Select ticker for QQ plot",
        diag_tickers,
        format_func=lambda t: f"{t} — {diag[t]['verdict'][:50]}…" if len(diag[t]["verdict"]) > 50 else f"{t} — {diag[t]['verdict']}",
        key="diag_qq_ticker",
    )

    # ── Side-by-side: QQ plot | test table ──
    col_qq, col_tbl = st.columns([1, 1])

    with col_qq:
        section_header("QQ Plot")
        st.markdown(
            '<p class="section-intro">'
            'Points on the red line = normal distribution. '
            'Tails curving away = fat tails — extreme moves occur more often than expected.'
            '</p>',
            unsafe_allow_html=True
        )
        d = diag[qq_ticker]
        fig = build_qq_plot(d["qq_theoretical"], d["qq_observed"], qq_ticker)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption(
            f"{qq_ticker}: Jarque-Bera p = {d['jb_pvalue']:.4f} "
            f"({'normal' if d['jb_normal'] else 'non-normal'}), "
            f"Ljung-Box p = {d['lb_pvalue']:.4f} "
            f"({'independent' if d['lb_independent'] else 'autocorrelated'}). "
            f"{d['verdict']}"
        )

    with col_tbl:
        section_header("Statistical Tests")
        st.markdown(
            '<p class="section-intro">'
            'Summary of normality and independence tests for all positions.'
            '</p>',
            unsafe_allow_html=True
        )
        render_styled_table(styled)


# ── Portfolio Outlook ────────────────────────────────────────────────────────

def render_portfolio_outlook(
    portfolio_mc: dict | None,
    tickers: list,
    base_currency: str,
    currency_symbol: str,
) -> None:
    """Render the Portfolio Outlook section."""
    section_header("Portfolio Outlook")
    st.markdown(
        '<p class="section-intro">'
        'Projects your full portfolio value forward using correlated Monte Carlo simulation — '
        'accounting for how your positions move together, not just individually.'
        '</p>',
        unsafe_allow_html=True
    )
    with st.expander("What do the metrics mean?"):
        st.markdown(
            '<p class="section-intro">'
            '• <b>Fan chart</b> — 1,000 simulated portfolio paths. The dark band covers the middle 50% of outcomes; '
            'the light band covers 80%. The further out you look, the wider the fan grows.'
            '<br>'
            '• <b>Value at Risk (VaR 95%)</b> — the minimum loss you would face in the worst 5% of scenarios.'
            '<br>'
            '• <b>Expected Shortfall (CVaR 95%)</b> — given that you are in the worst 5% of scenarios, '
            'the average loss. Always worse than VaR.'
            '<br>'
            '• <b>Diversification effect</b> — compares the realistic (correlated) simulation to an independent one. '
            'The difference in the 10th-percentile outcome shows whether your positions amplify or offset each other\'s downside.'
            '</p>',
            unsafe_allow_html=True
        )

    if not st.session_state.portfolio:
        st.info("Add positions to run the portfolio outlook.")
    elif not portfolio_mc:
        st.warning(
            "Not enough price history to run the portfolio outlook. "
            "Each position needs at least 1 year of data."
        )
    else:
        _po_horizon_label = st.radio(
            "Horizon", ["3 months", "6 months", "1 year"],
            index=2, horizontal=True, key="portfolio_outlook_horizon"
        )
        _po_day_idx = {"3 months": 62, "6 months": 125, "1 year": 251}[_po_horizon_label]

        _po_pct     = portfolio_mc["percentiles"]
        _po_paths   = portfolio_mc["portfolio_paths"]
        _po_paths_i = portfolio_mc["portfolio_paths_i"]
        _po_start   = portfolio_mc["start_value"]
        _po_dates   = list(portfolio_mc["dates"])[:_po_day_idx + 1]

        sliced_pct = {
            k: list(_po_pct[k].iloc[:_po_day_idx + 1])
            for k in ("p10", "p25", "p50", "p75", "p90")
        }

        fig = build_fan_chart(
            dates=_po_dates,
            percentiles=sliced_pct,
            hlines=[{
                "y": _po_start,
                "text": f"Current  {currency_symbol}{_po_start:,.0f}",
                "color": "#9CA3AF",
                "width": 1,
            }],
            currency_symbol=currency_symbol,
            y_title=f"Portfolio Value ({base_currency})",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        # ── Risk metrics ──
        _po_end   = _po_paths[:, _po_day_idx]
        _po_end_i = _po_paths_i[:, _po_day_idx]
        _po_vc    = compute_var_cvar(_po_end, _po_start)

        _corr_p10  = float(sorted(_po_end)[int(len(_po_end) * 0.10)])
        _indep_p10 = float(sorted(_po_end_i)[int(len(_po_end_i) * 0.10)])
        _div_diff  = _indep_p10 - _corr_p10

        _rm1, _rm2, _rm3, _rm4 = st.columns(4)
        _rm1.metric(
            f"VaR 95% ({_po_horizon_label})",
            f"{_po_vc['var'] * 100:.1f}%",
            delta=f"{currency_symbol}{_po_vc['var_abs']:,.0f}",
            delta_color="inverse",
            help=f"In the worst 5% of simulations, the portfolio loses at least "
                 f"{_po_vc['var'] * 100:.1f}% ({currency_symbol}{_po_vc['var_abs']:,.0f}) "
                 f"over {_po_horizon_label}.",
        )
        _rm2.metric(
            f"CVaR 95% ({_po_horizon_label})",
            f"{_po_vc['cvar'] * 100:.1f}%",
            delta=f"{currency_symbol}{_po_vc['cvar_abs']:,.0f}",
            delta_color="inverse",
            help=f"Given that you are in the worst 5% of scenarios, the average loss is "
                 f"{_po_vc['cvar'] * 100:.1f}% ({currency_symbol}{_po_vc['cvar_abs']:,.0f}). "
                 f"This is always at least as bad as VaR.",
        )
        _rm3.metric(
            "p10 outcome",
            f"{currency_symbol}{_corr_p10:,.0f}",
            delta=f"{(_corr_p10 - _po_start) / _po_start * 100:+.1f}%",
            delta_color="normal",
            help="The 10th-percentile portfolio value at the chosen horizon — "
                 "9 out of 10 simulations end above this level.",
        )
        _div_label = "narrows" if _div_diff < 0 else "widens"
        _rm4.metric(
            "Diversification effect",
            f"{currency_symbol}{abs(_div_diff):,.0f}",
            delta=f"Correlation {_div_label} p10",
            delta_color="normal" if _div_diff < 0 else "inverse",
            help=(
                f"Correlated p10: {currency_symbol}{_corr_p10:,.0f}  |  "
                f"Independent p10: {currency_symbol}{_indep_p10:,.0f}. "
                + (
                    f"Your positions tend to move together, which widens the downside tail by "
                    f"{currency_symbol}{_div_diff:,.0f} compared to uncorrelated positions."
                    if _div_diff > 0 else
                    f"Your positions partially offset each other, tightening the downside tail by "
                    f"{currency_symbol}{abs(_div_diff):,.0f} compared to uncorrelated positions."
                )
            ),
        )

        # ── Outcome distribution histogram ──
        section_header("Distribution of Simulated Outcomes")
        st.markdown(
            '<p class="section-intro">'
            'Each bar represents the number of simulated portfolios that ended within that value range. '
            'A tall central peak means outcomes are tightly clustered; a wide spread means high uncertainty. '
            'The dashed lines mark the 10th percentile (left tail), median, and 90th percentile.'
            '</p>',
            unsafe_allow_html=True
        )

        fig_hist = build_portfolio_histogram(
            end_values=_po_end,
            start_value=_po_start,
            p10=_corr_p10,
            p50=float(_po_pct["p50"].iloc[_po_day_idx]),
            p90=float(_po_pct["p90"].iloc[_po_day_idx]),
            currency_symbol=currency_symbol,
            base_currency=base_currency,
        )
        st.plotly_chart(fig_hist, width="stretch", config={"displayModeBar": False})

        st.caption(
            f"Based on {portfolio_mc['train_days']} trading days of calibration data. "
            f"Positions included: {', '.join(portfolio_mc['tickers_used'])}. "
            + (
                f"Excluded (insufficient history): "
                f"{', '.join(t for t in tickers if t not in portfolio_mc['tickers_used'])}. "
                if any(t not in portfolio_mc["tickers_used"] for t in tickers) else ""
            )
            + "This is a statistical model, not financial advice."
        )


# ── Position Outlook ─────────────────────────────────────────────────────────

def render_position_outlook(
    df: pd.DataFrame,
    price_data_5y: dict,
    tickers: list,
    base_currency: str,
    currency_symbol: str,
) -> None:
    """Render the Position Outlook section."""
    section_header("Position Outlook")
    st.markdown(
        '<p class="section-intro">'
        'Projects a single position forward using Monte Carlo simulation — useful for thinking through whether to hold or sell.'
        '</p>',
        unsafe_allow_html=True
    )
    with st.expander("How to read this section"):
        st.markdown(
            '<p class="section-intro">'
            '• <b>Calibration window</b> — how far back the model looks. A shorter window (1 year) reflects recent behaviour; '
            'a longer window (5 years) smooths out noise and captures multiple market regimes. '
            'If the two produce very different fans, the stock\'s behaviour has changed meaningfully.'
            '<br><br>'
            '<b>Not financial advice.</b> The probabilities are model outputs based on historical patterns. '
            'They do not account for news, earnings, or macroeconomic changes.'
            '</p>',
            unsafe_allow_html=True
        )

    if not st.session_state.portfolio:
        st.info("Add positions to run the outlook.")
    else:
        _ol_col1, _ol_col2, _ol_col3 = st.columns([2, 2, 2])

        with _ol_col1:
            _ol_ticker = st.selectbox(
                "Position",
                options=tickers,
                format_func=lambda t: f"{t} — {fetch_company_name(t)}",
                key="outlook_ticker",
            )
        with _ol_col2:
            _ol_horizon_label = st.radio(
                "Horizon", ["3 months", "6 months", "1 year", "2 years"], index=1,
                horizontal=True, key="outlook_horizon"
            )
        with _ol_col3:
            _ol_lookback_label = st.radio(
                "Calibration window", ["1 year", "2 years", "5 years"], index=1,
                horizontal=True, key="outlook_lookback"
            )

        _ol_horizon_days  = {"3 months": 63, "6 months": 126, "1 year": 252, "2 years": 504}[_ol_horizon_label]
        _ol_lookback_days = {"1 year": 252, "2 years": 504, "5 years": None}[_ol_lookback_label]

        _ol_hist = price_data_5y.get(_ol_ticker, pd.DataFrame())
        _ol_fx   = get_fx_rate(get_ticker_currency(_ol_ticker), base_currency)

        _ol_current_price = None
        _ol_close = _ol_hist["Close"].dropna() if not _ol_hist.empty and "Close" in _ol_hist.columns else pd.Series(dtype=float)
        if not _ol_close.empty:
            _ol_current_price = float(_ol_close.iloc[-1]) * _ol_fx

        if _ol_current_price is None or _ol_current_price <= 0:
            st.warning(f"Could not fetch a current price for {_ol_ticker}.")
        else:
            with st.spinner(f"Simulating {_ol_ticker}…"):
                _ol_result = cached_run_monte_carlo_ticker(
                    ticker=_ol_ticker,
                    hist=_ol_hist,
                    current_price=_ol_current_price,
                    horizon_days=_ol_horizon_days,
                    lookback_days=_ol_lookback_days,
                )

            if not _ol_result:
                st.warning(
                    f"{_ol_ticker} does not have enough price history for the selected calibration window. "
                    f"Try a shorter calibration window."
                )
            else:
                _ol_lots = df[df["Ticker"] == _ol_ticker][["Purchase", "Buy Price", "Shares"]].copy()
                _ol_wavg = None
                if not _ol_lots.empty:
                    _ol_wavg = float(
                        (_ol_lots["Buy Price"] * _ol_lots["Shares"]).sum()
                        / _ol_lots["Shares"].sum()
                    )

                # Build hlines for buy prices
                hlines = []
                if _ol_wavg is not None:
                    hlines.append({
                        "y": _ol_wavg,
                        "text": f"Avg buy {currency_symbol}{_ol_wavg:,.2f}",
                        "color": "#D97706",
                        "width": 1.5,
                    })
                if len(_ol_lots) > 1:
                    for _, _lot_row in _ol_lots.iterrows():
                        hlines.append({
                            "y": _lot_row["Buy Price"],
                            "text": f"Lot {int(_lot_row['Purchase'])}  {currency_symbol}{_lot_row['Buy Price']:,.2f}",
                            "color": "#9CA3AF",
                            "width": 1,
                            "position": "top right",
                        })

                fig = build_fan_chart(
                    dates=list(_ol_result["dates"]),
                    percentiles=_ol_result["percentiles"],
                    hlines=hlines,
                    currency_symbol=currency_symbol,
                    y_title=f"Price ({base_currency})",
                )
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

                # ── Probability metrics ──
                _ol_end = _ol_result["end_paths"]
                _m1, _m2, _m3 = st.columns(3)

                if _ol_wavg is not None:
                    _prob_above = float((_ol_end >= _ol_wavg).mean() * 100)
                    _m1.metric(
                        f"Prob. above avg buy price",
                        f"{_prob_above:.0f}%",
                        help=f"Fraction of simulations ending above your average buy price of "
                             f"{currency_symbol}{_ol_wavg:,.2f} after {_ol_horizon_label}.",
                    )

                _prob_above_current = float((_ol_end >= _ol_current_price).mean() * 100)
                _m2.metric(
                    "Prob. above today's price",
                    f"{_prob_above_current:.0f}%",
                    help=f"Fraction of simulations ending above the current price of "
                         f"{currency_symbol}{_ol_current_price:,.2f} — i.e. probability of a positive return.",
                )

                _m3.metric(
                    "Annualised volatility",
                    f"{_ol_result['sigma_annual']:.1f}%",
                    help="Annualised standard deviation of daily log-returns, used to calibrate the simulation width.",
                )

                st.markdown(
                    '<p class="section-intro">'
                    'A probability above 50% means the model\'s calibrated return rate is positive — based on historical patterns, '
                    'the stock has tended to go up over the chosen horizon. Below 50% means the opposite: '
                    'the historical drift was negative, and more simulated paths end lower than they started. '
                    'The width of the fan matters as much as the median: a highly volatile stock may show 55% probability of being above breakeven, '
                    'but the downside tail could be severe. Check the volatility figure alongside the probability.'
                    '</p>',
                    unsafe_allow_html=True
                )

                _ol_flag = _ol_result["flag"]
                if _ol_flag.get("fat_tailed"):
                    st.warning(
                        f"**{_ol_ticker} has fat-tailed returns** (excess kurtosis: {_ol_flag['kurtosis']:.1f}). "
                        f"Extreme price moves occur more often than a normal distribution predicts. "
                        f"The confidence bands above will understate the real tail risk for this position."
                    )

                st.caption(
                    f"Calibrated on {_ol_result['train_days']} trading days of {_ol_ticker} history "
                    f"({_ol_lookback_label} window). Assumes log-normally distributed daily returns with "
                    f"μ = {_ol_result['mu_annual']:+.1f}%/yr, σ = {_ol_result['sigma_annual']:.1f}%/yr. "
                    f"This is a statistical model, not financial advice."
                )
