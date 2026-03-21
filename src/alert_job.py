"""Background alert job — daily portfolio checks with email digest.

Runs as an asyncio task inside the NiceGUI process.
Checks opted-in users at 07:00 CET daily.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from zoneinfo import ZoneInfo

from src import db
from src.alerts import evaluate_all
from src.auth import _unwrap_key
from src.portfolio import build_portfolio_df
from src.ui.shared import _server_load

_log = logging.getLogger(__name__)

CET = ZoneInfo("Europe/Zurich")
SCHEDULE_HOUR = 7
SCHEDULE_MINUTE = 0


# ── Scheduler ─────────────────────────────────────────────


def start_alert_scheduler() -> None:
    """Launch the daily alert check as a background asyncio task."""
    asyncio.create_task(_run_daily_loop())
    _log.info("Alert scheduler started — next run at %02d:%02d CET", SCHEDULE_HOUR, SCHEDULE_MINUTE)


async def _run_daily_loop() -> None:
    """Sleep until 07:00 CET, run checks, repeat."""
    while True:
        now = datetime.datetime.now(CET)
        target = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        _log.info("Alert job sleeping %.0f seconds until %s", sleep_seconds, target.isoformat())
        await asyncio.sleep(sleep_seconds)

        try:
            await _run_all_checks()
        except Exception:
            _log.exception("Alert job failed")


async def _run_all_checks() -> None:
    """Process all opted-in users."""
    from nicegui import run

    users = await run.io_bound(db.get_alerted_users)
    _log.info("Alert job running for %d users", len(users))

    for user in users:
        try:
            enc_key = user["encryption_key"]
            if not isinstance(enc_key, bytes):
                enc_key = enc_key.encode()
            raw_key = _unwrap_key(enc_key)
            await run.io_bound(check_user_alerts, user["id"], raw_key)
        except Exception:
            _log.exception("Alert check failed for user %s", user["id"])


# ── Per-user check ────────────────────────────────────────


def check_user_alerts(user_id: str, encryption_key: bytes) -> None:
    """Check alerts for a single user. Send email if new alerts found."""
    # Load portfolio
    portfolio_data = _server_load(encryption_key, user_id)
    portfolio = portfolio_data.get("portfolio", {})
    if not portfolio:
        return

    currency = portfolio_data.get("currency", "USD")
    settings = portfolio_data.get("_alerts", {}).get("settings", {})

    # Compute weights
    df = build_portfolio_df(portfolio, currency)
    if df.empty:
        return

    total_value = df["Total Value"].sum()
    if total_value <= 0:
        return

    weights = {}
    for ticker in portfolio:
        ticker_value = df[df["Ticker"] == ticker]["Total Value"].sum()
        weights[ticker] = ticker_value / total_value

    # Evaluate concentration alerts only. Correlation alerts are skipped in the
    # background job because they require 1y price history per ticker pair —
    # fetching that for every user daily is too expensive. Users still see
    # correlation alerts when they open the Overview tab (warm cache only).
    alerts = evaluate_all(weights, price_data=None, settings=settings)
    if not alerts:
        return

    # Diff against last-sent
    current_ids = [a.rule_id for a in alerts]
    user = db.get_user_by_id(user_id)
    last_sent = json.loads(user.get("last_alert_ids", "[]"))

    new_ids = compute_new_alerts(current_ids, last_sent)
    if not new_ids:
        return

    # Filter to only new alerts for the email
    new_alerts = [a for a in alerts if a.rule_id in new_ids]

    # Send email
    email = user["email"]
    subject, html = build_alert_email(new_alerts)
    _send_alert_email(email, subject, html)

    # Update last-sent state
    db.update_last_alert_ids(user_id, current_ids)


def compute_new_alerts(current_ids: list[str], last_sent_ids: list[str]) -> list[str]:
    """Return rule_ids that are in current but not in last_sent."""
    last_set = set(last_sent_ids)
    return [rid for rid in current_ids if rid not in last_set]


# ── Email construction ────────────────────────────────────


_SEVERITY_COLORS = {
    "critical": "#EF4444",
    "warning": "#F59E0B",
    "info": "#3B82F6",
}


def build_alert_email(alerts: list) -> tuple[str, str]:
    """Build subject line and HTML body for an alert digest email.

    Returns (subject, html_body).
    """
    if len(alerts) == 1:
        subject = f"Portfolio Alert: {alerts[0].message}"
    else:
        subject = f"Portfolio Alert: {len(alerts)} new warnings"

    app_url = os.environ.get("APP_URL", "http://localhost:8080")

    cards = []
    for a in alerts:
        color = _SEVERITY_COLORS.get(a.severity, "#3B82F6")
        cards.append(
            f'<div style="border-left:4px solid {color}; padding:8px 12px; margin:8px 0;'
            f' background:rgba(0,0,0,0.05); border-radius:4px;">'
            f'<strong style="color:{color}; text-transform:uppercase; font-size:12px;">'
            f'{a.severity} — {a.title}</strong><br>'
            f'<span style="font-size:14px;">{a.message}</span></div>'
        )

    html = (
        f'<div style="font-family:sans-serif; max-width:500px; margin:0 auto;">'
        f'<h2 style="font-size:18px; margin-bottom:4px;">Market Dashboard — Portfolio Alerts</h2>'
        f'<p style="color:#666; font-size:14px;">'
        f'{len(alerts)} new alert{"s" if len(alerts) != 1 else ""} detected for your portfolio:</p>'
        f'{"".join(cards)}'
        f'<hr style="border:none; border-top:1px solid #ddd; margin:16px 0;">'
        f'<p style="font-size:12px; color:#888;">'
        f'<a href="{app_url}" style="color:#3B82F6;">Manage alert settings in your dashboard</a><br>'
        f'You\'re receiving this because you enabled email alerts.</p>'
        f'</div>'
    )

    return subject, html


# ── Email sending ─────────────────────────────────────────


def _send_alert_email(to_email: str, subject: str, html: str) -> None:
    """Send an alert digest email via Resend."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "noreply@example.com")
    if not api_key:
        _log.warning("RESEND_API_KEY not set — skipping alert email to %s", to_email)
        return
    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "html": html,
        })
    except Exception:
        _log.exception("Failed to send alert email to %s", to_email)
