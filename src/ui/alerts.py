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
        portfolio: {ticker: [lots]}
        weights: {ticker: decimal weight}
        portfolio_data: raw portfolio dict (for reading/writing _alerts state)
    """
    alert_state = _get_alert_state(portfolio_data)
    settings = alert_state.get("settings", {})
    dismissed = set(alert_state.get("dismissed", []))

    # Check which price data is warm in cache (don't trigger fetches).
    # COUPLING NOTE: this assumes fetch_analytics_history uses @cached(long_cache_analytics)
    # with the default key function (hashkey). If that decorator changes to use
    # lenient_key or a custom key, this probe will silently miss cached data.
    warm_price_data = {}
    for ticker in portfolio:
        from cachetools.keys import hashkey
        key = hashkey(ticker)
        if key in long_cache_analytics:
            warm_price_data[ticker] = long_cache_analytics[key]

    alerts = evaluate_all(weights, warm_price_data or None, settings)
    active_alerts = [a for a in alerts if a.rule_id not in dismissed]

    # Save current snapshot
    alert_state["snapshots"] = {
        "weights": {t: round(w, 4) for t, w in weights.items()},
    }
    _save_alert_state(portfolio_data, alert_state)

    if not active_alerts:
        return

    with ui.column().classes("w-full").style(
        f"background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;"
        f"padding:12px 16px;margin-bottom:12px;"
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.html(
                f'<span style="font-size:12px;font-weight:600;color:{TEXT_PRIMARY};">'
                f'Portfolio Alerts</span>'
            )
            settings_visible = {"show": False}

            def _toggle_settings():
                settings_visible["show"] = not settings_visible["show"]
                settings_container.set_visibility(settings_visible["show"])

            ui.button(icon="settings", on_click=_toggle_settings).props(
                "flat dense round size=xs"
            ).style(f"color:{TEXT_DIM};")

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

                def _dismiss(rule_id=alert.rule_id):
                    dismissed.add(rule_id)
                    alert_state["dismissed"] = list(dismissed)
                    _save_alert_state(portfolio_data, alert_state)
                    ui.notify("Alert dismissed", type="info")

                ui.button(icon="close", on_click=_dismiss).props(
                    "flat dense round size=xs"
                ).style(f"color:{TEXT_DIM};opacity:0.5;")

        # Settings panel (hidden by default)
        settings_container = ui.column().classes("w-full")
        settings_container.set_visibility(False)
        with settings_container:
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
