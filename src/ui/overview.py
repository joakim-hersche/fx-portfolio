"""Overview tab — KPI cards, allocation chart, comparison chart, Excel export."""

import asyncio
import datetime
import io
import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from nicegui import run, ui

from src.charts import (
    CHART_COLORS, C_CARD_BRD, C_NEGATIVE, C_POSITIVE,
    build_comparison_chart, is_mobile,
)
from src.data_fetch import (
    fetch_company_name, fetch_price_history_range,
)
from src.fx import (
    CURRENCY_SYMBOLS, get_fx_rate, get_ticker_currency,
)
from src.portfolio import build_portfolio_df
from src.risk_free import fetch_risk_free_yields, risk_free_label
from src.theme import (
    ACCENT, BG_CARD, BORDER, BORDER_SUBTLE,
    GREEN, RED, AMBER, TEXT_FAINT,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

# Unicode symbols for f-strings
UP_ARROW = '\u25b2'
DOWN_ARROW = '\u25bc'


async def build_overview_tab(
    portfolio: dict, currency: str, portfolio_color_map: dict[str, str],
) -> None:
    """Overview tab — KPI cards + allocation chart + comparison chart."""
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")

    if not portfolio:
        # Mobile: tell user to set up on desktop
        with ui.element("div").classes("touch-only w-full"):
            ui.html(f'''
                <div style="display:flex;flex-direction:column;align-items:center;
                            justify-content:center;padding:60px 20px 40px;max-width:480px;
                            margin:0 auto;text-align:center;">
                    <div style="font-size:20px;font-weight:700;color:{TEXT_PRIMARY};
                                margin-bottom:6px;">No positions yet</div>
                    <div style="font-size:13px;color:{TEXT_DIM};line-height:1.6;
                                margin-bottom:20px;">
                        Sign in and add your portfolio on a desktop browser.
                        Your positions will sync automatically to this device.</div>
                    <div style="font-size:12px;color:{TEXT_FAINT};line-height:1.5;">
                        Open <b style="color:{TEXT_PRIMARY};">fxportfolio.app</b>
                        on your computer to get started.</div>
                </div>
            ''')

        # Desktop: full onboarding flow
        with ui.element("div").classes("desktop-only w-full"):
            ui.html(f'''
                <div style="display:flex;flex-direction:column;align-items:center;
                            justify-content:center;padding:60px 20px 40px;max-width:480px;
                            margin:0 auto;text-align:center;">
                    <div style="font-size:20px;font-weight:700;color:{TEXT_PRIMARY};
                                margin-bottom:6px;">No positions yet</div>
                <div style="font-size:13px;color:{TEXT_DIM};line-height:1.6;
                            margin-bottom:32px;">
                    Add your first stock in the sidebar to see portfolio analytics,
                    or load sample data to explore the dashboard.</div>

                <div style="display:flex;flex-direction:column;gap:16px;width:100%;
                            text-align:left;">
                    <div style="display:flex;gap:12px;align-items:flex-start;">
                        <div style="width:24px;height:24px;border-radius:6px;
                                    background:{ACCENT};color:#fff;font-size:12px;
                                    font-weight:700;display:flex;align-items:center;
                                    justify-content:center;flex-shrink:0;">1</div>
                        <div>
                            <div style="font-size:13px;font-weight:600;color:{TEXT_PRIMARY};">
                                Search for a stock</div>
                            <div style="font-size:12px;color:{TEXT_DIM};margin-top:2px;">
                                Use the sidebar search — e.g. AAPL, MSFT, ASML.AS</div>
                        </div>
                    </div>
                    <div style="display:flex;gap:12px;align-items:flex-start;">
                        <div style="width:24px;height:24px;border-radius:6px;
                                    background:{ACCENT};color:#fff;font-size:12px;
                                    font-weight:700;display:flex;align-items:center;
                                    justify-content:center;flex-shrink:0;">2</div>
                        <div>
                            <div style="font-size:13px;font-weight:600;color:{TEXT_PRIMARY};">
                                Enter your position</div>
                            <div style="font-size:12px;color:{TEXT_DIM};margin-top:2px;">
                                Shares, buy price, and purchase date</div>
                        </div>
                    </div>
                    <div style="display:flex;gap:12px;align-items:flex-start;">
                        <div style="width:24px;height:24px;border-radius:6px;
                                    background:{ACCENT};color:#fff;font-size:12px;
                                    font-weight:700;display:flex;align-items:center;
                                    justify-content:center;flex-shrink:0;">3</div>
                        <div>
                            <div style="font-size:13px;font-weight:600;color:{TEXT_PRIMARY};">
                                Dashboard fills in automatically</div>
                            <div style="font-size:12px;color:{TEXT_DIM};margin-top:2px;">
                                Returns, risk metrics, charts, and more</div>
                        </div>
                    </div>
                </div>

                <div style="border-top:1px solid {BORDER};margin-top:28px;
                            padding-top:16px;width:100%;text-align:center;">
                    <div style="font-size:12px;color:{TEXT_DIM};margin-bottom:14px;">
                        Want to explore first? Load a demo portfolio with stocks
                        across different markets and asset types.</div>
                </div>
            </div>
            ''')
            ui.button(
                "Load Sample Portfolio", icon="science",
                on_click=lambda: ui.run_javascript(
                    'document.getElementById("btn-load-sample")?.click()'
                ),
            ).props("unelevated no-caps size=lg").style(
                f"background:{ACCENT}; color:white; border-radius:8px; padding:12px 32px;"
                f" font-size:14px; font-weight:600; margin:0 auto; display:block;"
            )

        return

    # ── Build portfolio DataFrame (cached 5 min) ──────────
    notification = ui.notification("Loading overview data...", spinner=True, timeout=None)
    try:
        df = await run.io_bound(build_portfolio_df, portfolio, currency)
    except Exception:
        df = None
    finally:
        notification.dismiss()
    if df is None or df.empty:
        ui.html(
            '<div style="color:#94A3B8;font-size:13px;padding:24px;">'
            'Could not retrieve price data for any positions.</div>'
        )
        return

    fx_warnings = df.attrs.get("fx_warnings", [])
    if fx_warnings:
        tickers_str = ", ".join(fx_warnings)
        ui.html(
            f'<div style="background:rgba(220,38,38,0.1);border:1px solid rgba(220,38,38,0.3);'
            f'border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
            f'<span style="color:#DC2626;font-weight:600;">FX rate unavailable</span>'
            f'<span style="color:{TEXT_DIM};font-size:12px;"> for {tickers_str}. '
            f'Values shown with 1:1 rate — figures may be inaccurate.</span></div>'
        ).classes("w-full")

    # ── Shared helpers ─────────────────────────────────────
    with ThreadPoolExecutor(max_workers=min(10, len(portfolio))) as _ex:
        _names = list(_ex.map(lambda t: (t, fetch_company_name(t)), portfolio))
    name_map = dict(_names)

    # ── Alert banner ──────────────────────────────────────
    from src.ui.alerts import render_alert_banner
    from src.ui.shared import load_portfolio

    alert_weights = {}
    for ticker in portfolio:
        ticker_value = df[df["Ticker"] == ticker]["Total Value"].sum()
        total_value = df["Total Value"].sum()
        if total_value > 0:
            alert_weights[ticker] = ticker_value / total_value

    portfolio_data = load_portfolio()
    render_alert_banner(portfolio, alert_weights, portfolio_data)

    # ── KPI values ─────────────────────────────────────────
    total_value = df["Total Value"].sum()
    daily_pnl = df["Daily P&L"].sum()
    n_positions = len(portfolio)
    cost_basis = df["Cost Basis"].sum()
    total_contributed = 0.0
    for ticker, lots in portfolio.items():
        ticker_ccy = get_ticker_currency(ticker)
        fallback_fx, _ = get_fx_rate(ticker_ccy, currency)
        for lot in lots:
            lot_fx = lot.get("buy_fx_rate", fallback_fx)
            total_contributed += lot["shares"] * lot.get("buy_price", 0) * lot_fx
    total_divs = df["Dividends"].sum()
    total_return = total_value + total_divs - cost_basis
    total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

    pnl_color = C_POSITIVE if daily_pnl >= 0 else C_NEGATIVE
    ret_color = C_POSITIVE if total_return >= 0 else C_NEGATIVE

    n_purchases = sum(len(lots) for lots in portfolio.values())
    purchases_sub = (
        f'<div class="kpi-sub sm" style="color:{TEXT_MUTED};">{n_purchases} purchases</div>'
        if n_purchases != n_positions else ""
    )

    all_dates = [
        lot["purchase_date"]
        for lots in portfolio.values() for lot in lots
        if lot.get("purchase_date")
    ]
    first_purchase = min(all_dates) if all_dates else None
    return_sub = (
        f'<div class="kpi-sub sm" style="color:{TEXT_MUTED};">Gross, pre-tax · since {first_purchase}</div>'
        if first_purchase else ""
    )

    spacer_md = '<div class="kpi-sub" style="visibility:hidden;">.</div>'
    spacer_sm = '<div class="kpi-sub sm" style="visibility:hidden;">.</div>'

    def _kpi_card(label, value, border_color, line1="", line2="", hero=False, font_size=None):
        is_neutral = border_color == C_CARD_BRD
        value_color = TEXT_PRIMARY if is_neutral else border_color
        font = font_size or ("26px" if hero else "22px")
        return (
            f'<div style="background:{BG_CARD};border-radius:10px;'
            f'padding:16px 18px;border:1px solid {BORDER};'
            f'display:flex;flex-direction:column;">'
            f'<div class="kpi-label">{label}</div>'
            f'<div style="font-size:{font};font-weight:700;line-height:1.2;color:{value_color};white-space:nowrap;">{value}</div>'
            f'{line1 or spacer_md}'
            f'{line2 or spacer_sm}'
            f'</div>'
        )

    sign_ret = "+" if total_return >= 0 else ""
    sign_pnl = "+" if daily_pnl >= 0 else ""

    cache_time = datetime.datetime.now().strftime("%H:%M")

    val_int = f"{currency_symbol}{int(total_value):,}"
    val_dec = f"{total_value:.2f}".split('.')[-1]
    card_1 = _kpi_card(
        "Total Portfolio Value",
        f'{val_int}<span style="font-size:16px;font-weight:700;">.{val_dec}</span>',
        C_CARD_BRD,
        line1=f'<div class="kpi-sub" style="color:{TEXT_DIM};">Updated {cache_time} \u00b7 5 min cache</div>',
        line2='',
        hero=True,
    )
    card_2 = _kpi_card(
        "Total Return",
        f"{sign_ret}{currency_symbol}{total_return:,.2f}",
        ret_color,
        line1=f'<span class="kpi-badge {"badge-green" if total_return >= 0 else "badge-red"}" style="margin-top:6px;">{UP_ARROW if total_return >= 0 else DOWN_ARROW} {sign_ret}{total_ret_pct:,.2f}%</span>',
        line2=return_sub or spacer_sm,
        hero=True,
    )
    daily_pnl_pct = (daily_pnl / (total_value - daily_pnl) * 100) if (total_value - daily_pnl) else 0.0
    card_3 = _kpi_card(
        "Today's Change",
        f"{sign_pnl}{currency_symbol}{daily_pnl:,.2f}",
        pnl_color,
        line1=f'<span class="kpi-badge {"badge-green" if daily_pnl >= 0 else "badge-red"}" style="margin-top:5px; font-size:11px;">{UP_ARROW if daily_pnl >= 0 else DOWN_ARROW} {sign_pnl}{daily_pnl_pct:,.2f}%</span>',
        line2=f'<div class="kpi-sub">Since yesterday\'s close</div>',
        font_size="20px",
    )
    card_4 = (
        f'<div style="background:{BG_CARD};border-radius:10px;padding:16px 18px;'
        f'border:1px solid {BORDER};">'
        f'<div class="kpi-label">Positions</div>'
        f'<div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY};line-height:1.1;">{n_positions}</div>'
        f'<div style="font-size:12px;color:{TEXT_DIM};margin-top:4px;">'
        f'{n_positions} stocks &middot; {n_purchases} lots</div>'
        f'</div>'
    )

    card_5 = _kpi_card(
        "Total Contributed",
        f"{currency_symbol}{total_contributed:,.2f}",
        C_CARD_BRD,
        line1=f'<div class="kpi-sub" style="color:{TEXT_DIM};">Cost basis at purchase FX</div>',
        font_size="20px",
    )

    # Desktop: 5-column KPI grid
    ui.html(
        f'<div class="kpi-row kpi-row-5">'
        f'{card_1}{card_2}{card_3}{card_4}{card_5}</div>'
    ).classes("w-full not-phone")

    # Mobile: consolidated hero card
    sign_pnl_m = "+" if daily_pnl >= 0 else ""
    sign_ret_m = "+" if total_return >= 0 else ""
    pnl_color_m = "#16A34A" if daily_pnl >= 0 else "#DC2626"
    ret_color_m = "#16A34A" if total_return >= 0 else "#DC2626"
    pnl_bg_m = "rgba(22,163,74,0.15)" if daily_pnl >= 0 else "rgba(220,38,38,0.15)"

    ui.html(f'''<div style="margin-bottom:16px;">
  <div style="background:{BG_CARD};border-radius:10px;padding:16px;
    border:1px solid {BORDER};">
    <div style="font-size:10px;color:{TEXT_MUTED};text-transform:uppercase;
      letter-spacing:0.08em;">Portfolio Value</div>
    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY};margin-top:4px;">
      {val_int}<span style="font-size:16px;color:{TEXT_DIM};">.{val_dec}</span></div>
    <div style="display:flex;align-items:center;gap:8px;margin-top:6px;">
      <span style="font-size:12px;color:{pnl_color_m};font-weight:600;">
        {sign_pnl_m}{currency_symbol}{daily_pnl:,.2f}</span>
      <span style="font-size:10px;background:{pnl_bg_m};color:{pnl_color_m};
        padding:2px 6px;border-radius:4px;font-weight:600;">
        {sign_pnl_m}{daily_pnl_pct:,.2f}%</span>
      <span style="font-size:10px;color:{TEXT_DIM};">today</span>
    </div>
    <div style="border-top:1px solid {BORDER_SUBTLE};margin:12px 0;"></div>
    <div style="display:flex;justify-content:space-between;">
      <div>
        <div style="font-size:9px;color:{TEXT_DIM};text-transform:uppercase;
          letter-spacing:0.06em;">Total Return</div>
        <div style="font-size:14px;font-weight:600;color:{ret_color_m};margin-top:2px;">
          {sign_ret_m}{currency_symbol}{total_return:,.2f}
          <span style="font-size:10px;opacity:0.7;">
            {sign_ret_m}{total_ret_pct:,.2f}%</span></div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:9px;color:{TEXT_DIM};text-transform:uppercase;
          letter-spacing:0.06em;">Positions</div>
        <div style="font-size:14px;font-weight:600;color:{TEXT_PRIMARY};margin-top:2px;">
          {n_positions} <span style="font-size:10px;color:{TEXT_DIM};">stocks</span></div>
      </div>
    </div>
  </div>
  <div style="display:flex;justify-content:space-between;padding:0 4px;margin-top:8px;">
    <div style="font-size:10px;color:{TEXT_DIM};">Contributed:
      <span style="color:{TEXT_MUTED};font-weight:500;">{currency_symbol}{total_contributed:,.2f}</span></div>
  </div>
</div>''').classes("w-full touch-only")

    # ── Allocation + Comparison side by side ───────────────
    with ui.element("div").classes("charts-row w-full").style("width:100%;"):
        # Allocation chart
        with ui.column().classes("chart-card").style("min-width:0;"):
            with ui.row().classes("w-full items-center justify-between").style("margin:0;"):
                ui.html('<div class="chart-title">Portfolio Allocation</div>')
                ui.html(f'<div style="font-size:10px;color:{TEXT_DIM};">by market value</div>')
            alloc_df = (
                df.groupby("Ticker")["Total Value"]
                .sum()
                .reset_index()
                .assign(**{"Portfolio Share (%)": lambda x: (x["Total Value"] / x["Total Value"].sum() * 100).round(2)})
                .sort_values("Portfolio Share (%)", ascending=False)
            )

            # Build HTML bars — scale bar height + gap dynamically based on stock count
            max_pct = alloc_df["Portfolio Share (%)"].max() if not alloc_df.empty else 100
            n_bars = len(alloc_df)
            bar_h = max(18, min(40, int(280 / max(n_bars, 1))))
            bar_gap = max(4, min(14, int(100 / max(n_bars, 1))))

            currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")
            total_val = alloc_df["Total Value"].sum()

            bar_rows = ""
            for _, row in alloc_df.iterrows():
                ticker = row["Ticker"]
                pct = row["Portfolio Share (%)"]
                val = row["Total Value"]
                bar_width = (pct / max_pct * 100) if max_pct > 0 else 0
                color = portfolio_color_map.get(ticker, "#3B82F6")
                company = name_map.get(ticker, ticker)
                bar_rows += (
                    f'<div class="alloc-bar" style="display:flex;align-items:center;gap:8px;line-height:1.4;position:relative;">'
                    f'<div style="width:64px;font-size:11px;font-weight:600;color:{TEXT_SECONDARY};flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{ticker}</div>'
                    f'<div style="flex:1;height:{bar_h}px;background:rgba(255,255,255,0.04);border-radius:4px;overflow:hidden;cursor:pointer;">'
                    f'<div style="width:{bar_width:.1f}%;height:100%;background:{color};border-radius:4px;transition:opacity 0.15s;"></div>'
                    f'</div>'
                    f'<div style="width:36px;font-size:11px;color:{TEXT_DIM};text-align:right;flex-shrink:0;">{pct:.0f}%</div>'
                    f'<div class="alloc-tip">'
                    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
                    f'<div style="width:8px;height:8px;border-radius:2px;background:{color};flex-shrink:0;"></div>'
                    f'<span style="font-weight:600;color:{TEXT_PRIMARY};font-size:11px;">{ticker}</span>'
                    f'<span style="color:{TEXT_DIM};font-size:10px;">{company}</span>'
                    f'</div>'
                    f'<div style="display:flex;gap:12px;font-size:11px;">'
                    f'<span style="color:{TEXT_PRIMARY};font-weight:600;">{currency_symbol}{val:,.0f}</span>'
                    f'<span style="color:{TEXT_MUTED};">{pct:.1f}%</span>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                )

            alloc_html = (
                f'<div style="display:flex;flex-direction:column;flex:1;width:100%;">'
                f'<div style="display:flex;flex-direction:column;gap:{bar_gap}px;flex:1;justify-content:center;width:100%;">'
                f'{bar_rows}'
                f'</div>'
                f'</div>'
            )

            ui.html(alloc_html).classes("w-full").style("flex:1;display:flex;width:100%;min-width:0;")

        # Comparison chart — compute height to match allocation card
        # Allocation height: n_bars * (bar_h + bar_gap) + card padding (~32px) + header (~30px)
        alloc_content_h = n_bars * (bar_h + bar_gap)
        # Subtract comparison card padding (32px) + header/controls (~70px) to get chart height
        chart_h = max(300, alloc_content_h - 40)

        with ui.column().classes("chart-card").style("min-width:0;"):
            await build_comparison(portfolio, name_map, portfolio_color_map, currency, chart_height=chart_h)

    # ── Contributions vs. Portfolio Value chart ─────────────
    from src.portfolio import build_contribution_timeline

    async def _build_contribution_chart():
        timeline = await run.io_bound(build_contribution_timeline, portfolio, currency)
        if timeline is not None and not timeline.empty:
            import plotly.graph_objects as go
            from src.charts import _mobile_overrides

            mobile = is_mobile()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=timeline.index, y=timeline["Contributed"],
                mode="lines", name="In" if mobile else "Contributed",
                line=dict(color=TEXT_FAINT, width=1.5, dash="dot"),
                fill="tozeroy",
                fillcolor="rgba(132,148,167,0.08)",
            ))
            fig.add_trace(go.Scatter(
                x=timeline.index, y=timeline["Portfolio Value"],
                mode="lines", name="Value" if mobile else "Portfolio Value",
                line=dict(color=ACCENT, width=2),
                fill="tonexty",
                fillcolor="rgba(59,130,246,0.10)",
            ))

            if mobile:
                fig.update_layout(
                    template="plotly",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02,
                        xanchor="left", x=0,
                        font=dict(size=9, color="#94A3B8"),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    margin=dict(l=45, r=10, t=10, b=30),
                )
                fig.update_xaxes(
                    tickformat="%b '%y",
                    gridcolor="rgba(255,255,255,0.04)",
                )
                fig.update_yaxes(
                    tickprefix=currency_symbol,
                    tickformat="~s",
                    gridcolor="rgba(255,255,255,0.04)",
                )
                _mobile_overrides(fig)
                fig.update_layout(height=200)
            else:
                fig.update_layout(
                    template="plotly",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(title="Date"),
                    yaxis=dict(tickprefix=currency_symbol, title=f"Value ({currency})"),
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02,
                        xanchor="left", x=0,
                        font=dict(size=10, color="#94A3B8"),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    margin=dict(l=40, r=20, t=30, b=40),
                    hoverlabel=dict(
                        bgcolor="#1C1D26", bordercolor="#1E293B",
                        font=dict(color="#F1F5F9", size=11, family="Inter, sans-serif"),
                        namelength=-1,
                    ),
                    modebar=dict(
                        bgcolor="rgba(0,0,0,0)",
                        color="#64748B",
                        activecolor="#94A3B8",
                    ),
                )
                fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#CBD5E1", size=10), title_font=dict(color="#CBD5E1", size=11))
                fig.update_yaxes(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#CBD5E1", size=10), title_font=dict(color="#CBD5E1", size=11))

            with ui.column().classes("chart-card w-full").style("min-width:0;"):
                ui.html('<div class="chart-title">Contributions vs. Portfolio Value</div>')

                if mobile:
                    # Inline gain summary instead of paragraph
                    contributed = timeline["Contributed"].iloc[-1]
                    value = timeline["Portfolio Value"].iloc[-1]
                    delta = value - contributed
                    delta_pct = (delta / contributed * 100) if contributed > 0 else 0
                    delta_color = "#16A34A" if delta >= 0 else "#DC2626"
                    sign = "+" if delta >= 0 else ""
                    if abs(delta) >= 1000:
                        delta_str = f"{sign}{currency_symbol}{delta/1000:,.1f}K"
                    else:
                        delta_str = f"{sign}{currency_symbol}{delta:,.0f}"
                    ui.html(
                        f'<div style="font-size:11px;color:{delta_color};font-weight:600;margin-bottom:4px;">'
                        f'{delta_str} ({sign}{delta_pct:.1f}%)'
                        f'</div>'
                    )
                else:
                    ui.html(
                        f'<p style="font-size:11px;color:{TEXT_DIM};margin:0 0 6px 0;line-height:1.5;">'
                        "The blue line is what you put in (total money invested). "
                        "The green line is what it's worth now. "
                        "The gap between them is your real investment gain or loss."
                        "</p>"
                    )
                ui.plotly(fig).classes("w-full")

    await _build_contribution_chart()



async def build_comparison(
    portfolio: dict, name_map: dict, portfolio_color_map: dict, base_currency: str,
    chart_height: int | None = None,
) -> None:
    """Comparison chart with time-range toggle and FX adjustment."""
    range_options = {"3M": "3mo", "6M": "6mo", "1Y": "1y", "Max": "since"}

    # Compute earliest purchase date for "Max" option
    all_dates = [
        lot["purchase_date"]
        for lots in portfolio.values() for lot in lots
        if lot.get("purchase_date")
    ]
    earliest_date = min(all_dates) if all_dates else None

    with ui.row().classes("w-full items-start justify-between flex-wrap").style("margin:0;gap:8px;"):
        ui.html('<div class="chart-title" style="margin-top:2px;">Portfolio Comparison</div>')
        ui.html(f'<div style="font-size:10px;color:{TEXT_DIM};margin-top:2px;">All positions rebased to 100 at period start</div>')
        with ui.row().classes("items-center gap-2 flex-wrap"):
            range_toggle = ui.toggle(
                list(range_options.keys()), value="6M",
            ).props("dense size=sm no-caps").style("font-size:10px;")
            fx_switch = ui.switch("FX-adjusted", value=False).style(f"font-size:12px;color:{TEXT_MUTED};")
            bench_switch = ui.switch("Show benchmark", value=False).style(f"font-size:12px;color:{TEXT_MUTED};")
            rf_switch = ui.switch("Risk-free", value=False).style(f"font-size:12px;color:{TEXT_MUTED};")

    # ── Ticker toggle pills ──
    ticker_visibility: dict[str, bool] = {t: True for t in portfolio}
    pill_container = ui.row().classes("w-full items-center gap-1 flex-wrap").style(
        "overflow-x:auto;padding:4px 0;margin:0;"
    )

    chart_container = ui.column().classes("w-full")
    with chart_container:
        ui.spinner('dots', size='xl').classes('self-center').style('padding:40px 0;')

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
                    f"padding:6px 12px;font-size:11px;color:#F1F5F9;"
                    f"background:{'rgba(0,0,0,0)' if not active else color + '15'};"
                    f"transition:all 0.2s ease;min-height:32px;line-height:1.4;"
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
            ).style("font-size:10px;color:#94A3B8;min-height:28px;padding:4px 8px;")
            ui.html('<span style="font-size:10px;color:#64748B;">/</span>')
            ui.button("None", on_click=lambda: _set_all(False)).props(
                "flat dense no-caps size=xs"
            ).style("font-size:10px;color:#94A3B8;min-height:28px;padding:4px 8px;")

    async def update_chart():
        chart_container.clear()
        range_label = range_toggle.value
        selected_range = range_options[range_label]
        fx_adjust = fx_switch.value
        show_bench = bench_switch.value
        show_rf = rf_switch.value

        def _fetch_comparison_data():
            from concurrent.futures import ThreadPoolExecutor
            from src.data_fetch import fetch_price_history_long

            def _fetch_one(t):
                try:
                    if selected_range == "since" and earliest_date:
                        hist = fetch_price_history_long(t)
                        if not hist.empty:
                            hist = hist[hist.index >= pd.Timestamp(earliest_date)]
                    else:
                        hist = fetch_price_history_range(t, selected_range if selected_range != "since" else "max")
                except Exception:
                    return t, None
                if hist.empty:
                    return t, None
                ticker_currency = get_ticker_currency(t)
                if fx_adjust and ticker_currency != base_currency:
                    fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
                    try:
                        if selected_range == "since" and earliest_date:
                            fx_hist = fetch_price_history_long(f"{fx_pair}{base_currency}=X")
                            if not fx_hist.empty:
                                fx_hist = fx_hist[fx_hist.index >= pd.Timestamp(earliest_date)]
                        else:
                            fx_hist = fetch_price_history_range(f"{fx_pair}{base_currency}=X", selected_range if selected_range != "since" else "max")
                    except Exception:
                        return t, hist["Close"]
                    if fx_hist.empty:
                        return t, hist["Close"]
                    fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
                    if ticker_currency == "GBX":
                        fx_series = fx_series / 100
                    return t, hist["Close"] * fx_series
                else:
                    return t, hist["Close"]

            with ThreadPoolExecutor(max_workers=min(10, len(portfolio))) as ex:
                results = list(ex.map(_fetch_one, portfolio))
            data = {t: series for t, series in results if series is not None}

            # Fetch local market benchmark if requested
            bench_series = None
            _BENCH_MAP = {
                "USD": ("SPY", "S&P 500"),
                "CHF": ("^SSMI", "SMI"),
                "EUR": ("^STOXX50E", "Euro Stoxx 50"),
                "GBP": ("^FTSE", "FTSE 100"),
                "SEK": ("^OMX", "OMX Stockholm 30"),
            }
            bench_ticker, bench_name = _BENCH_MAP.get(base_currency, ("SPY", "S&P 500"))
            if show_bench and bench_ticker not in portfolio:
                try:
                    period = selected_range if selected_range != "since" else "max"
                    bench_hist = fetch_price_history_range(bench_ticker, period)
                    if selected_range == "since" and earliest_date and not bench_hist.empty:
                        bench_hist = bench_hist[bench_hist.index >= pd.Timestamp(earliest_date)]
                    if not bench_hist.empty:
                        bench_series = bench_hist["Close"]
                except Exception:
                    pass

            # Fetch risk-free yield curve if requested
            rf_cumulative = None
            rf_label = None
            if show_rf:
                rf_label = f"Risk-Free ({risk_free_label(base_currency)})"
                try:
                    all_series = [s for s in data.values() if s is not None and not s.empty]
                    if all_series:
                        chart_start = min(s.index.min() for s in all_series)
                        chart_end = max(s.index.max() for s in all_series)
                        # Fetch from well before chart range so we always have data
                        # even if the API lags behind the current date
                        fetch_start = str((chart_start - pd.DateOffset(years=1)).date())
                        fetch_end = str(chart_end.date())
                        yields = fetch_risk_free_yields(base_currency, fetch_start, fetch_end)
                        if not yields.empty:
                            # Extend to cover the chart range via forward-fill
                            full_range = pd.date_range(start=yields.index.min(), end=chart_end, freq="D")
                            yields = yields.reindex(full_range).ffill().dropna()
                            # Trim to chart range
                            yields = yields[yields.index >= chart_start]
                            if not yields.empty:
                                daily_rate = (1 + yields / 100) ** (1 / 365) - 1
                                rf_cumulative = (1 + daily_rate).cumprod() * 100
                except Exception:
                    pass

            return data, bench_series, bench_name, rf_cumulative, rf_label

        result = await run.io_bound(_fetch_comparison_data)
        if result is None:
            with chart_container:
                ui.html(f'<p style="font-size:12px;color:{TEXT_DIM};padding:20px 0;">Could not load comparison data.</p>')
            return
        comparison_data, bench_series, bench_name, rf_cumulative, rf_label = result

        comparison_df = pd.DataFrame(comparison_data).dropna()
        if not comparison_df.empty:
            comparison_df = comparison_df / comparison_df.iloc[0] * 100

        fig = build_comparison_chart(
            comparison_df, name_map, portfolio_color_map,
            range_label, fx_adjust, base_currency,
            title="Portfolio Comparison",
            mobile=is_mobile(),
        )

        # Add local market benchmark overlay
        if show_bench and bench_series is not None and not bench_series.empty:
            bench_rebased = bench_series / bench_series.iloc[0] * 100
            import plotly.graph_objects as go
            fig.add_trace(go.Scatter(
                x=bench_rebased.index, y=bench_rebased.values,
                mode="lines", name=bench_name,
                line=dict(color="#F59E0B", width=2),
                hovertemplate=f"{bench_name}: %{{y:.1f}}<extra></extra>",
            ))

        # Add risk-free rate overlay
        if show_rf and rf_cumulative is not None and not rf_cumulative.empty:
            import plotly.graph_objects as go
            fig.add_trace(go.Scatter(
                x=rf_cumulative.index, y=rf_cumulative.values,
                mode="lines", name=rf_label,
                line=dict(color="#10B981", width=2, dash="dash"),
                hovertemplate=f"{rf_label}: %{{y:.1f}}<extra></extra>",
            ))

        # Apply ticker visibility toggles — match by trace name, not index
        for trace in fig.data:
            for ticker, visible in ticker_visibility.items():
                if ticker in trace.name:
                    trace.visible = True if visible else "legendonly"
                    break

        if chart_height:
            fig.update_layout(height=chart_height)
        if is_mobile():
            fig.update_layout(height=220)

        with chart_container:
            ui.plotly(fig).classes("w-full")

    async def _toggle_ticker(ticker: str):
        ticker_visibility[ticker] = not ticker_visibility[ticker]
        _render_pills()
        await _debounced_update()

    async def _set_all(visible: bool):
        for t in ticker_visibility:
            ticker_visibility[t] = visible
        _render_pills()
        await _debounced_update()

    # Debounce rapid toggles (#27)
    _debounce_timer = {"handle": None}
    async def _debounced_update(_=None):
        if _debounce_timer["handle"]:
            _debounce_timer["handle"].cancel()
        loop = asyncio.get_event_loop()
        _debounce_timer["handle"] = loop.call_later(0.3, lambda: asyncio.ensure_future(update_chart()))
    range_toggle.on_value_change(_debounced_update)
    fx_switch.on_value_change(_debounced_update)
    bench_switch.on_value_change(_debounced_update)
    rf_switch.on_value_change(_debounced_update)

    # Initial render
    _render_pills()
    await update_chart()


async def export_excel(portfolio: dict, currency: str) -> None:
    """Build and download the Excel report."""
    if not portfolio:
        ui.notify("No positions to export.", type="warning")
        return

    from src.data_fetch import (
        fetch_analytics_history, fetch_fundamentals, fetch_price_history_short,
        cached_run_monte_carlo_backtest, cached_run_monte_carlo_portfolio,
        cached_run_monte_carlo_ticker, fetch_simulation_history,
    )
    from src.excel_export import build_excel_report
    from src.portfolio import compute_analytics

    notification = ui.notification("Building Excel report...", spinner=True, timeout=None)

    def _build():
        base_currency = currency
        df = build_portfolio_df(portfolio, base_currency)
        if df.empty:
            return None

        name_map = {t: fetch_company_name(t) for t in portfolio}
        tickers = list(portfolio.keys())

        # Analytics
        price_data_1y = {t: fetch_analytics_history(t) for t in tickers}
        _bench = {"USD": "SPY", "CHF": "^SSMI", "EUR": "^STOXX50E", "GBP": "^FTSE", "SEK": "^OMX"}
        bench_ticker = _bench.get(base_currency, "SPY")
        bench_data = fetch_analytics_history(bench_ticker)
        analytics_df = compute_analytics(portfolio, price_data_1y, bench_data, base_currency)

        # Monte Carlo
        price_data_5y = {t: fetch_simulation_history(t) for t in tickers}
        bt = cached_run_monte_carlo_backtest(portfolio, price_data_5y)

        start_prices_base = {}
        ticker_mc_results = {}
        for t in tickers:
            hist_5y = price_data_5y.get(t, pd.DataFrame())
            fx_mc, _ = get_fx_rate(get_ticker_currency(t), base_currency)
            close_mc = hist_5y["Close"].dropna() if not hist_5y.empty and "Close" in hist_5y.columns else pd.Series(dtype=float)
            if not close_mc.empty:
                cur_mc = float(close_mc.iloc[-1]) * fx_mc
                start_prices_base[t] = cur_mc
                ticker_mc_results[t] = cached_run_monte_carlo_ticker(
                    ticker=t, hist=hist_5y, current_price=cur_mc, horizon_days=252,
                    lookback_days=504,
                )

        portfolio_mc = cached_run_monte_carlo_portfolio(
            portfolio=portfolio, price_data=price_data_5y,
            start_prices_base=start_prices_base, horizon_days=252,
        )

        # Fundamentals
        fund_rows = []
        excel_target_prices: dict[str, float | None] = {}
        for t in tickers:
            f = fetch_fundamentals(t)
            if f:
                tc = get_ticker_currency(t)
                # Build target price map for Excel (FX-converted, GBX /100 handled by get_fx_rate)
                tp = f.get("Target Price")
                if tp is not None and tc != base_currency:
                    fx_tp, _ = get_fx_rate(tc, base_currency)
                    excel_target_prices[t] = round(tp * fx_tp, 2)
                elif tp is not None:
                    excel_target_prices[t] = tp
                if tc != base_currency:
                    fx, _ = get_fx_rate(tc, base_currency)
                    if f.get("1-Year Low"):
                        f["1-Year Low"] = round(f["1-Year Low"] * fx, 2)
                    if f.get("1-Year High"):
                        f["1-Year High"] = round(f["1-Year High"] * fx, 2)
                fund_rows.append({"Ticker": t, **f})

        # KPIs
        total_value = df["Total Value"].sum()
        daily_pnl = df["Daily P&L"].sum()
        cost_basis = df["Cost Basis"].sum()
        total_divs = df["Dividends"].sum()
        total_return = total_value + total_divs - cost_basis
        total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

        # Dividend timeline for forward calendar
        from src.portfolio import build_dividend_timeline
        try:
            div_timeline = build_dividend_timeline(portfolio, base_currency)
        except Exception:
            div_timeline = []

        # Health score — uses same 1Y price data as dashboard health tab
        from src.health import compute_health_score, generate_findings, ticker_to_region
        from src.ui.health import _compute_weighted_corr, _compute_portfolio_vol

        ticker_weights_dec = (
            df.groupby("Ticker")["Weight (%)"].sum() / 100
        ).to_dict()

        h_sectors: set[str] = set()
        h_regions: set[str] = set()
        h_sector_weights: dict[str, float] = {}
        h_ticker_sector: dict[str, str] = {}
        for fr in fund_rows:
            t = fr.get("Ticker")
            sector = fr.get("Sector", "Unknown")
            if sector and sector != "Unknown":
                h_sectors.add(sector)
            if t:
                h_regions.add(ticker_to_region(t))
                h_ticker_sector[t] = sector
                w = ticker_weights_dec.get(t, 0) * 100
                h_sector_weights[sector] = h_sector_weights.get(sector, 0) + w

        h_corr = _compute_weighted_corr(price_data_1y, tickers, ticker_weights_dec)
        h_vol = _compute_portfolio_vol(price_data_1y, tickers, ticker_weights_dec)

        # Portfolio-level Sharpe and Max Drawdown for Summary sheet
        _port_returns = {}
        for t in tickers:
            _h = price_data_1y.get(t)
            if _h is not None and not _h.empty and "Close" in _h.columns:
                _r = _h["Close"].pct_change().dropna()
                if len(_r) >= 30:
                    _port_returns[t] = _r
        _port_sharpe = None
        _port_max_dd = None
        if _port_returns:
            _port_df = pd.DataFrame(_port_returns).dropna()
            if not _port_df.empty:
                _port_daily = sum(
                    _port_df[t] * ticker_weights_dec.get(t, 0) for t in _port_df.columns
                )
                # Sharpe (same risk-free rate as compute_analytics)
                from src.risk_free import fetch_risk_free_yields
                try:
                    _rf_yields = fetch_risk_free_yields(
                        base_currency,
                        str((pd.Timestamp.today() - pd.DateOffset(years=1)).date()),
                        str(pd.Timestamp.today().date()),
                    )
                    _avg_rf = _rf_yields.mean() / 100 if not _rf_yields.empty else 0.04
                except Exception:
                    _avg_rf = 0.04
                _daily_rf = _avg_rf / 252
                _excess = _port_daily - _daily_rf
                if _excess.std() > 0:
                    _port_sharpe = round(float((_excess.mean() / _excess.std()) * (252 ** 0.5)), 2)
                # Max Drawdown
                _cumulative = (1 + _port_daily).cumprod()
                _rolling_max = _cumulative.cummax()
                _dd = (_cumulative - _rolling_max) / _rolling_max
                _port_max_dd = round(float(_dd.min()) * 100, 1)
        h_top = sorted(
            [(t, w * 100) for t, w in ticker_weights_dec.items()],
            key=lambda x: x[1], reverse=True,
        )

        h_score = compute_health_score(
            ticker_weights_dec, h_sectors, h_regions, h_corr, h_vol,
        )
        h_findings = generate_findings(
            ticker_weights_dec, h_sectors, h_regions, h_sector_weights,
            h_corr, h_vol, h_top,
        )

        return build_excel_report(
            positions_df=df,
            analytics_df=analytics_df,
            fund_rows=fund_rows,
            price_histories={t: fetch_price_history_short(t) for t in portfolio},
            name_map=name_map,
            currency=base_currency,
            summary_kpis={
                "total_value": total_value,
                "daily_pnl": daily_pnl,
                "cost_basis": cost_basis,
                "total_divs": total_divs,
                "total_return": total_return,
                "total_ret_pct": total_ret_pct,
                "n_positions": len(portfolio),
                "portfolio_sharpe": _port_sharpe,
                "portfolio_max_dd": _port_max_dd,
                "portfolio_vol": round(h_vol * 100, 1) if h_vol else None,
            },
            bt_result=bt,
            ticker_mc_results=ticker_mc_results,
            portfolio_mc=portfolio_mc,
            target_prices=excel_target_prices,
            dividend_timeline=div_timeline,
            portfolio=portfolio,
            health_score=h_score,
            health_findings=h_findings,
            health_sector_weights=h_sector_weights,
            health_ticker_sector=h_ticker_sector,
        )

    try:
        excel_bytes = await run.io_bound(_build)
    except Exception as exc:
        notification.dismiss()
        ui.notify(f"Excel export failed: {exc}", type="negative")
        import traceback
        traceback.print_exc()
        return

    notification.dismiss()

    if excel_bytes is None:
        ui.notify("Could not build report — no price data.", type="negative")
        return

    filename = f"portfolio_{pd.Timestamp.today().strftime('%Y%m%d')}.xlsx"
    ui.download(excel_bytes, filename)
    ui.notify("Report downloaded", type="positive")


