"""Shared UI utilities used across tab modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from typing import Any

# Type alias for the shared state dict passed to all tab builders
SharedState = dict[str, Any]
