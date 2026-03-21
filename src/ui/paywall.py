"""Paywall UI — locked tab overlay and pricing page."""
from __future__ import annotations

from nicegui import app, run, ui

from src.billing import (
    get_display_prices, create_checkout_session, is_pro,
    _LOCKED_TAB_DESCRIPTIONS,
)
from src.theme import (
    ACCENT, BG_CARD, BG_MAIN, BORDER_SUBTLE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY,
)


def render_locked_overlay(tab_name: str, currency: str) -> None:
    """Render a locked tab overlay with upgrade CTA."""
    description = _LOCKED_TAB_DESCRIPTIONS.get(tab_name, "This feature requires Pro")
    prices = get_display_prices(currency)
    symbol = prices["symbol"]
    monthly = prices["monthly"]

    with ui.column().classes("w-full items-center justify-center").style(
        "min-height:400px; padding:40px 20px;"
    ):
        # Blurred placeholder
        ui.html(
            '<div style="width:100%; max-width:600px; height:200px; border-radius:12px;'
            ' background:linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.08));'
            ' filter:blur(2px); margin-bottom:32px;"></div>'
        )

        ui.icon("lock").style("font-size:32px; color:rgba(255,255,255,0.3); margin-bottom:12px;")
        ui.label("Upgrade to Pro").style(
            f"font-size:22px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
        )
        ui.label(description).style(
            f"font-size:14px; color:{TEXT_MUTED}; margin-bottom:20px; text-align:center; max-width:400px;"
        )
        ui.label(f"From {symbol}{monthly}/month").style(
            f"font-size:13px; color:{TEXT_DIM}; margin-bottom:16px;"
        )
        ui.button("View plans", on_click=lambda: ui.navigate.to("/pricing")).props(
            "no-caps unelevated"
        ).style(f"background:{ACCENT}; border-radius:8px; font-size:14px; padding:8px 24px;")


def build_pricing_page(user_id: str | None, currency: str) -> None:
    """Build the /pricing page content."""
    prices = get_display_prices(currency)
    symbol = prices["symbol"]
    user_is_pro = is_pro(user_id)
    email = app.storage.user.get("auth_email")

    with ui.column().classes("w-full items-center").style(
        f"background:{BG_MAIN}; min-height:100vh; padding:40px 20px;"
    ):
        ui.label("FX Portfolio Pro").style(
            f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
        )
        ui.label("Unlock the full power of your portfolio tracker").style(
            f"font-size:14px; color:{TEXT_MUTED}; margin-bottom:32px;"
        )

        # All three plans side by side
        _CARD = (
            f"width:260px; min-height:520px; background:{BG_CARD};"
            f" border-radius:12px; padding:28px; display:flex; flex-direction:column;"
        )
        _PLANS = [
            ("Monthly", prices["monthly"], "/month", "monthly"),
            ("Yearly", prices["yearly"], "/year", "yearly"),
            ("Lifetime", prices["lifetime"], " one-time", "lifetime"),
        ]

        with ui.row().classes("items-stretch gap-5 justify-center flex-wrap"):
            # Free card
            with ui.card().style(
                f"{_CARD} border:1px solid rgba(255,255,255,0.08);"
            ):
                ui.label("Free").style(
                    f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:4px;"
                )
                ui.label(f"{symbol}0").style(
                    f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:16px;"
                )
                _feature_list([
                    ("Up to 10 positions", True),
                    ("Overview & Positions", True),
                    ("Portfolio Health", True),
                    ("Research & Guide", True),
                    ("Monte Carlo Forecast", False),
                    ("Income tracking", False),
                    ("Excel export", False),
                    ("Email alerts", False),
                ])

            # Pro cards — one per interval
            for plan_name, plan_price, period, interval in _PLANS:
                is_recommended = interval == "yearly"
                border = f"border:2px solid {ACCENT};" if is_recommended else f"border:1px solid rgba(255,255,255,0.08);"

                with ui.card().style(f"{_CARD} {border}"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"Pro {plan_name}").style(
                            f"font-size:20px; font-weight:700; color:{ACCENT}; margin-bottom:4px;"
                        )
                        if is_recommended:
                            ui.label("Best value").style(
                                f"font-size:10px; font-weight:600; color:white; background:{ACCENT};"
                                f" border-radius:4px; padding:2px 8px; margin-bottom:4px;"
                            )
                    ui.label(f"{symbol}{plan_price}{period}").style(
                        f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:16px;"
                    )
                    _feature_list([
                        ("Unlimited positions", True),
                        ("Overview & Positions", True),
                        ("Portfolio Health", True),
                        ("Research & Guide", True),
                        ("Monte Carlo Forecast", True),
                        ("Income tracking", True),
                        ("Excel export", True),
                        ("Email alerts", True),
                    ])

                    # Spacer to push button to bottom
                    ui.element("div").style("flex-grow:1;")

                    if user_is_pro:
                        ui.label("You're on Pro").style(
                            f"font-size:13px; color:{ACCENT}; font-weight:600; text-align:center; width:100%;"
                        )
                    elif not user_id:
                        ui.button("Sign in to upgrade", on_click=lambda: ui.navigate.to("/")).props(
                            "no-caps unelevated"
                        ).style(f"width:100%; background:{ACCENT}; border-radius:8px;")
                    else:
                        async def _checkout(iv=interval):
                            url = await run.io_bound(
                                create_checkout_session, user_id, email, currency, iv
                            )
                            ui.navigate.to(url, new_tab=False)

                        ui.button("Get started", on_click=_checkout).props(
                            "no-caps unelevated"
                        ).style(f"width:100%; background:{ACCENT}; border-radius:8px;")


def _feature_list(features: list[tuple[str, bool]]) -> None:
    """Render a feature checklist."""
    for label, included in features:
        icon = "check_circle" if included else "cancel"
        color = "#22C55E" if included else "rgba(255,255,255,0.2)"
        with ui.row().classes("items-center gap-2").style("margin-bottom:6px;"):
            ui.icon(icon).style(f"font-size:16px; color:{color};")
            ui.label(label).style(f"font-size:13px; color:{TEXT_MUTED};")
