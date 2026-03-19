"""Launcher for integration testing -- runs the app on port 8081."""
import glob
import os
import sys

# Patch __file__ in the module namespace for main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Clear stale user storage from previous test runs
nicegui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".nicegui")
for f in glob.glob(os.path.join(nicegui_dir, "storage-user-*.json")):
    os.remove(f)

# We need to intercept ui.run() to override port/show/reload
from nicegui import ui

_original_run = ui.run

def _patched_run(**kwargs):
    kwargs["port"] = 8081
    kwargs["show"] = False
    kwargs["reload"] = False
    _original_run(**kwargs)

ui.run = _patched_run

# Now import main which will trigger ui.run at module level
import main  # noqa: F401
