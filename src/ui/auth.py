"""Authentication UI — login, register, verify, reset forms.

Renders inside the main content area (not a separate page).
"""
from __future__ import annotations

import logging

from nicegui import app, run, ui

from src import auth, db
from src.theme import (
    ACCENT, BG_CARD, BG_INPUT, BORDER_INPUT, BORDER_SUBTLE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY,
)

_log = logging.getLogger(__name__)


async def show_auth_ui(
    container,
    on_login_success: callable,
):
    """Render the auth flow inside `container`. Calls on_login_success(result) on success."""
    container.clear()
    with container:
        _build_login_form(container, on_login_success)


def _build_login_form(container, on_login_success: callable):
    """Login form with email + password."""
    with ui.column().classes("w-full items-center").style("padding-top:60px;"):
        with ui.card().style(
            f"width:380px; max-width:90vw; background:{BG_CARD};"
            f" border:1px solid rgba(255,255,255,0.12); border-radius:12px; padding:32px;"
        ):
            ui.label("Sign in").style(
                f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:20px;"
            )
            email_input = ui.input("Email").props("outlined dense").style(
                f"width:100%; background:{BG_INPUT};"
            )
            password_input = ui.input("Password", password=True, password_toggle_button=True).props(
                "outlined dense"
            ).style(f"width:100%; background:{BG_INPUT}; margin-top:8px;")

            error_label = ui.label("").style(
                f"color:#EF4444; font-size:12px; min-height:18px; margin-top:4px;"
            )

            async def _do_login():
                error_label.text = ""
                try:
                    result = await run.io_bound(
                        auth.login, email_input.value, password_input.value
                    )
                    if not result["verified"]:
                        container.clear()
                        with container:
                            _build_verify_form(
                                container, result["user_id"],
                                result["email"], on_login_success,
                            )
                        return
                    await on_login_success(result)
                except auth.RateLimitError:
                    error_label.text = "Too many attempts — try again in 15 minutes."
                except auth.AuthError as e:
                    error_label.text = str(e)

            ui.button("Sign in", on_click=_do_login).props("no-caps unelevated").style(
                f"width:100%; margin-top:16px; background:{ACCENT}; border-radius:8px;"
            )

            with ui.row().classes("w-full justify-between").style("margin-top:16px;"):
                ui.link("Create account", "").style(
                    f"font-size:12px; color:{ACCENT}; cursor:pointer;"
                ).on("click", lambda: _swap_to_register(container, on_login_success))
                ui.link("Forgot password?", "").style(
                    f"font-size:12px; color:{TEXT_DIM}; cursor:pointer;"
                ).on("click", lambda: _swap_to_reset_request(container, on_login_success))


def _swap_to_register(container, on_login_success):
    container.clear()
    with container:
        _build_register_form(container, on_login_success)


def _build_register_form(container, on_login_success: callable):
    """Registration form with email + password."""
    with ui.column().classes("w-full items-center").style("padding-top:60px;"):
        with ui.card().style(
            f"width:380px; max-width:90vw; background:{BG_CARD};"
            f" border:1px solid rgba(255,255,255,0.12); border-radius:12px; padding:32px;"
        ):
            ui.label("Create account").style(
                f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:20px;"
            )
            email_input = ui.input("Email").props("outlined dense").style(
                f"width:100%; background:{BG_INPUT};"
            )
            password_input = ui.input("Password", password=True, password_toggle_button=True).props(
                "outlined dense"
            ).style(f"width:100%; background:{BG_INPUT}; margin-top:8px;")
            ui.label("Minimum 8 characters").style(
                f"font-size:11px; color:{TEXT_DIM}; margin-top:2px;"
            )

            error_label = ui.label("").style(
                f"color:#EF4444; font-size:12px; min-height:18px; margin-top:4px;"
            )

            async def _do_register():
                error_label.text = ""
                try:
                    user_id, code = await run.io_bound(
                        auth.register, email_input.value, password_input.value
                    )
                    # Send verification email (fire-and-forget for now)
                    await _send_verify_email(email_input.value, code)
                    container.clear()
                    with container:
                        _build_verify_form(
                            container, user_id, email_input.value, on_login_success
                        )
                except auth.ValidationError as e:
                    error_label.text = str(e)
                except db.DuplicateEmailError:
                    error_label.text = "An account with that email already exists."

            ui.button("Create account", on_click=_do_register).props("no-caps unelevated").style(
                f"width:100%; margin-top:16px; background:{ACCENT}; border-radius:8px;"
            )

            ui.link("Already have an account?", "").style(
                f"font-size:12px; color:{ACCENT}; cursor:pointer; margin-top:12px;"
            ).on("click", lambda: _swap_to_login(container, on_login_success))


def _swap_to_login(container, on_login_success):
    container.clear()
    with container:
        _build_login_form(container, on_login_success)


def _build_verify_form(container, user_id: str, email: str, on_login_success: callable):
    """6-digit verification code form."""
    with ui.column().classes("w-full items-center").style("padding-top:60px;"):
        with ui.card().style(
            f"width:380px; max-width:90vw; background:{BG_CARD};"
            f" border:1px solid rgba(255,255,255,0.12); border-radius:12px; padding:32px;"
        ):
            ui.label("Verify your email").style(
                f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
            )
            ui.label(f"Enter the 6-digit code sent to {email}").style(
                f"font-size:13px; color:{TEXT_DIM}; margin-bottom:20px;"
            )
            code_input = ui.input("Verification code").props("outlined dense").style(
                f"width:100%; background:{BG_INPUT};"
            )
            error_label = ui.label("").style(
                f"color:#EF4444; font-size:12px; min-height:18px; margin-top:4px;"
            )

            async def _do_verify():
                error_label.text = ""
                try:
                    ok = await run.io_bound(auth.verify_email, user_id, code_input.value.strip())
                except auth.RateLimitError:
                    error_label.text = "Too many attempts. Please request a new code."
                    return
                if ok:
                    # Fetch user data directly (no re-login needed)
                    user = await run.io_bound(db.get_user_by_id, user_id)
                    from src.auth import _unwrap_key
                    enc_key = user["encryption_key"]
                    if not isinstance(enc_key, bytes):
                        enc_key = enc_key.encode()
                    encryption_key = await run.io_bound(_unwrap_key, enc_key)
                    await on_login_success({
                        "user_id": user_id,
                        "email": email,
                        "verified": True,
                        "encryption_key": encryption_key,
                    })
                else:
                    error_label.text = "Wrong code. Please try again."

            ui.button("Verify", on_click=_do_verify).props("no-caps unelevated").style(
                f"width:100%; margin-top:16px; background:{ACCENT}; border-radius:8px;"
            )

            async def _resend():
                new_code = await run.io_bound(auth.generate_new_verify_code, user_id)
                await _send_verify_email(email, new_code)
                ui.notify("New code sent.", type="positive")

            ui.button("Resend code", on_click=_resend).props("flat no-caps").style(
                f"color:{TEXT_DIM}; font-size:12px; margin-top:8px;"
            )


def _swap_to_reset_request(container, on_login_success):
    container.clear()
    with container:
        _build_reset_request_form(container, on_login_success)


def _build_reset_request_form(container, on_login_success: callable):
    """Password reset — enter email step."""
    with ui.column().classes("w-full items-center").style("padding-top:60px;"):
        with ui.card().style(
            f"width:380px; max-width:90vw; background:{BG_CARD};"
            f" border:1px solid rgba(255,255,255,0.12); border-radius:12px; padding:32px;"
        ):
            ui.label("Reset password").style(
                f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
            )
            ui.label("We'll send a reset link to your email.").style(
                f"font-size:13px; color:{TEXT_DIM}; margin-bottom:20px;"
            )
            email_input = ui.input("Email").props("outlined dense").style(
                f"width:100%; background:{BG_INPUT};"
            )
            status_label = ui.label("").style(
                f"font-size:12px; min-height:18px; margin-top:4px;"
            )

            async def _do_request():
                status_label.style(f"color:{TEXT_DIM};")
                try:
                    token = await run.io_bound(auth.create_password_reset, email_input.value)
                    if token:
                        await _send_reset_email(email_input.value, token)
                except auth.RateLimitError:
                    status_label.style("color:#EF4444;")
                    status_label.text = "Too many requests. Try again later."
                    return
                status_label.text = "If that email is registered, we sent a reset link."

            ui.button("Send reset link", on_click=_do_request).props("no-caps unelevated").style(
                f"width:100%; margin-top:16px; background:{ACCENT}; border-radius:8px;"
            )

            ui.link("Back to sign in", "").style(
                f"font-size:12px; color:{ACCENT}; cursor:pointer; margin-top:12px;"
            ).on("click", lambda: _swap_to_login(container, on_login_success))


def build_reset_complete_form(token: str):
    """Password reset — enter new password step (rendered on /reset?token=xxx)."""
    with ui.column().classes("w-full items-center").style("padding-top:60px;"):
        with ui.card().style(
            f"width:380px; max-width:90vw; background:{BG_CARD};"
            f" border:1px solid rgba(255,255,255,0.12); border-radius:12px; padding:32px;"
        ):
            ui.label("Set new password").style(
                f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:20px;"
            )
            password_input = ui.input("New password", password=True, password_toggle_button=True).props(
                "outlined dense"
            ).style(f"width:100%; background:{BG_INPUT};")
            ui.label("Minimum 8 characters").style(
                f"font-size:11px; color:{TEXT_DIM}; margin-top:2px;"
            )
            status_label = ui.label("").style(
                f"font-size:12px; min-height:18px; margin-top:4px;"
            )

            async def _do_reset():
                try:
                    await run.io_bound(
                        auth.complete_password_reset, token, password_input.value
                    )
                    status_label.style(f"color:#22C55E;")
                    status_label.text = "Password updated. You can now sign in."
                except auth.ValidationError as e:
                    status_label.style("color:#EF4444;")
                    status_label.text = str(e)
                except auth.AuthError as e:
                    status_label.style("color:#EF4444;")
                    status_label.text = str(e)

            ui.button("Update password", on_click=_do_reset).props("no-caps unelevated").style(
                f"width:100%; margin-top:16px; background:{ACCENT}; border-radius:8px;"
            )


# ── Email helpers ─────────────────────────────────────────


async def _send_verify_email(email: str, code: str) -> None:
    """Send verification code email via Resend."""
    import os
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "noreply@example.com")
    if not api_key:
        _log.warning("RESEND_API_KEY not set — skipping verification email to %s (code: %s)", email, code)
        return
    try:
        import resend
        resend.api_key = api_key
        await run.io_bound(
            resend.Emails.send,
            {
                "from": from_email,
                "to": email,
                "subject": "Your verification code",
                "html": f"<p>Your verification code is: <strong>{code}</strong></p>"
                        f"<p>This code expires in 15 minutes.</p>",
            },
        )
    except Exception:
        _log.exception("Failed to send verification email to %s", email)


async def _send_reset_email(email: str, token: str) -> None:
    """Send password reset email via Resend."""
    import os
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "noreply@example.com")
    host = os.environ.get("APP_URL", "http://localhost:8080")
    if not api_key:
        _log.warning("RESEND_API_KEY not set — skipping reset email to %s", email)
        return
    try:
        import resend
        resend.api_key = api_key
        reset_url = f"{host}/reset?token={token}"
        await run.io_bound(
            resend.Emails.send,
            {
                "from": from_email,
                "to": email,
                "subject": "Reset your password",
                "html": f'<p>Click here to reset your password:</p>'
                        f'<p><a href="{reset_url}">{reset_url}</a></p>'
                        f'<p>This link expires in 1 hour.</p>',
            },
        )
    except Exception:
        _log.exception("Failed to send reset email to %s", email)
