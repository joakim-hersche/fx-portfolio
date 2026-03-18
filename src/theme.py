"""Design tokens extracted from design_proposal.html.

Centralises all colors, fonts, and CSS so the NiceGUI app matches the
approved visual concept.
"""

# ── Color palette ──────────────────────────────────────────
BG_PAGE      = "#0C0D10"
BG_SIDEBAR   = "#161719"
BG_TOPBAR    = "#161719"
BG_MAIN      = "#111318"
BG_CARD      = "#1C1D26"
BG_INPUT     = "#1D1E26"
BG_PILL      = "#191A21"
BG_PILL_ACT  = "#252A3A"

ACCENT       = "#3B82F6"
ACCENT_DARK  = "#2563EB"

TEXT_PRIMARY  = "#F1F5F9"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED    = "#94A3B8"
TEXT_DIM      = "#64748B"
TEXT_FAINT    = "#475569"
TEXT_GHOST    = "#374151"

BORDER        = "rgba(255,255,255,0.07)"
BORDER_INPUT  = "rgba(255,255,255,0.08)"
BORDER_SUBTLE = "rgba(255,255,255,0.06)"

GREEN  = "#16A34A"
RED    = "#DC2626"
AMBER  = "#D97706"

GREEN_BG  = "rgba(22,163,74,0.15)"
RED_BG    = "rgba(220,38,38,0.15)"
AMBER_BG  = "rgba(217,119,6,0.15)"

# Ticker / allocation chart colors (from design_proposal sidebar dots)
TICKER_PALETTE = [
    "#3B82F6", "#0EA5E9", "#6366F1", "#10B981",
    "#F59E0B", "#EC4899", "#8B5CF6", "#14B8A6",
]

# ── Global CSS ─────────────────────────────────────────────
# Injected via ui.add_head_html in main.py.  Mirrors the design proposal's
# type scale, spacing, and component styles.
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset Quasar/NiceGUI defaults ─────────────────────── */
body, .q-page, .nicegui-content {
  background: %(BG_PAGE)s !important;
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
  color: %(TEXT_PRIMARY)s !important;
}

/* ── Hide NiceGUI default header/drawer styling ────────── */
.q-header { background: %(BG_TOPBAR)s !important; border-bottom: 1px solid %(BORDER)s !important; box-shadow: none !important; }
.q-drawer { background: %(BG_SIDEBAR)s !important; border-right: 1px solid %(BORDER)s !important; }
.q-tab-panels, .q-tab-panel { background: %(BG_MAIN)s !important; padding: 20px !important; }
.q-tabs { background: %(BG_MAIN)s !important; border-bottom: 1px solid %(BORDER)s !important; }
.q-tab { text-transform: none !important; font-family: 'Inter', sans-serif !important; font-size: 12px !important; font-weight: 500 !important; letter-spacing: 0.01em !important; color: %(TEXT_FAINT)s !important; }
.q-tab--active { color: %(TEXT_PRIMARY)s !important; font-weight: 600 !important; }
.q-tab-indicator { background: %(ACCENT)s !important; height: 3px !important; }

/* ── Sidebar form styling ──────────────────────────────── */
.sidebar-section-header {
  font-size: 9.5px; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: %(TEXT_FAINT)s;
  padding: 4px 4px 6px 4px; margin-top: 4px;
}
.sidebar-divider {
  border: none; border-top: 1px solid %(BORDER_SUBTLE)s; margin: 8px 0;
}

/* Form inputs inside sidebar */
.sidebar .q-field__control { background: %(BG_INPUT)s !important; border: 1px solid %(BORDER_INPUT)s !important; border-radius: 5px !important; min-height: 30px !important; }
.sidebar .q-field__label { font-size: 10px !important; color: %(TEXT_DIM)s !important; font-weight: 500 !important; }
.sidebar .q-field__native, .sidebar .q-field__input { font-size: 11px !important; color: %(TEXT_MUTED)s !important; font-family: 'Inter', sans-serif !important; }

/* ── Position list in sidebar ──────────────────────────── */
.position-row {
  display: flex; align-items: center; gap: 7px;
  padding: 5px 4px; border-radius: 5px; cursor: default;
}
.position-row:hover { background: rgba(255,255,255,0.04); }
.pos-dot { width: 8px; height: 8px; border-radius: 50%%; flex-shrink: 0; }
.pos-info { flex: 1; min-width: 0; }
.pos-ticker { font-size: 11px; font-weight: 600; color: %(TEXT_SECONDARY)s; }
.pos-name { font-size: 9.5px; color: %(TEXT_FAINT)s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pos-value { font-size: 11px; font-weight: 500; color: %(TEXT_MUTED)s; text-align: right; }

/* ── Add button ────────────────────────────────────────── */
.add-btn {
  width: 100%%; background: %(ACCENT_DARK)s; border: none; border-radius: 5px;
  color: #fff; font-family: inherit; font-size: 11px; font-weight: 600;
  padding: 6px 0; cursor: pointer; margin-top: 4px; text-align: center;
}
.add-btn:hover { opacity: 0.9; }

/* ── Sidebar action buttons ────────────────────────────── */
.sidebar-btn {
  width: 100%%; background: transparent;
  border: 1px solid %(BORDER_INPUT)s; border-radius: 5px;
  color: %(TEXT_DIM)s; font-family: inherit; font-size: 11px;
  font-weight: 500; padding: 6px 0; cursor: pointer;
  margin-bottom: 4px; text-align: center;
}
.sidebar-btn:hover { border-color: rgba(255,255,255,0.15); color: %(TEXT_MUTED)s; }

/* ── KPI cards ─────────────────────────────────────────── */
.kpi-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 12px; margin-bottom: 8px; }
.kpi-card {
  background: %(BG_CARD)s; border: 1px solid %(BORDER)s;
  border-radius: 10px; padding: 16px 18px;
}
.kpi-card.hero { padding: 18px 20px; }
.kpi-label {
  font-size: 9.5px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: %(TEXT_FAINT)s; margin-bottom: 6px;
}
.kpi-value { font-size: 22px; font-weight: 700; color: %(TEXT_PRIMARY)s; line-height: 1.15; }
.kpi-card.hero .kpi-value { font-size: 26px; }
.kpi-sub { font-size: 11px; color: %(TEXT_DIM)s; margin-top: 4px; }
.kpi-badge {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 12px; font-weight: 600; padding: 2px 7px;
  border-radius: 4px; margin-top: 5px;
}
.badge-green { background: %(GREEN_BG)s; color: %(GREEN)s; }
.badge-red   { background: %(RED_BG)s; color: %(RED)s; }
.badge-amber { background: %(AMBER_BG)s; color: %(AMBER)s; }

/* ── Chart cards ───────────────────────────────────────── */
.chart-card {
  background: %(BG_CARD)s; border: 1px solid %(BORDER)s;
  border-radius: 10px; padding: 16px;
}
.chart-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.chart-title {
  font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: %(TEXT_MUTED)s;
}
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

/* ── Content divider ───────────────────────────────────── */
.content-divider {
  border: none; border-top: 1px solid %(BORDER_SUBTLE)s; margin: 16px 0;
}

/* ── Table styling ─────────────────────────────────────── */
.table-wrap {
  width: 100%%; overflow: hidden; border-radius: 8px; border: 1px solid %(BORDER)s;
}
.table-wrap table { width: 100%%; border-collapse: collapse; font-size: 12px; }
.table-wrap thead tr { background: %(BG_TOPBAR)s; border-bottom: 1px solid %(BORDER)s; }
.table-wrap thead th {
  padding: 10px 12px; text-align: left; font-size: 9.5px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase; color: %(TEXT_FAINT)s;
}
.table-wrap tbody tr { border-bottom: 1px solid %(BORDER_SUBTLE)s; }
.table-wrap tbody tr:last-child { border-bottom: none; }
.table-wrap tbody tr:hover { background: rgba(255,255,255,0.03); }
.table-wrap tbody td { padding: 9px 12px; color: %(TEXT_SECONDARY)s; }
.td-pos { color: %(GREEN)s; font-weight: 600; }
.td-neg { color: %(RED)s; font-weight: 600; }

/* ── Metric cards (forecast) ───────────────────────────── */
.metric-card {
  background: %(BG_PILL)s; border: 1px solid %(BORDER)s;
  border-radius: 8px; padding: 12px 14px;
}
.metric-label {
  font-size: 9px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: %(TEXT_FAINT)s; margin-bottom: 5px;
}
.metric-value { font-size: 20px; font-weight: 700; color: %(TEXT_PRIMARY)s; }
.metric-sub { font-size: 10px; color: %(TEXT_DIM)s; margin-top: 3px; }

/* ── Pill toggles ──────────────────────────────────────── */
.pill-row { display: flex; gap: 4px; align-items: center; }
.pill {
  font-size: 10px; font-weight: 500; padding: 3px 8px; border-radius: 4px;
  cursor: pointer; color: %(TEXT_DIM)s; background: %(BG_PILL)s;
  border: 1px solid %(BORDER)s;
}
.pill.active { background: %(BG_PILL_ACT)s; color: #93C5FD; border-color: rgba(59,130,246,0.4); }

/* ── Topbar controls ───────────────────────────────────── */
.topbar-select {
  background: %(BG_INPUT)s; border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px; color: %(TEXT_MUTED)s; font-family: inherit;
  font-size: 12px; padding: 4px 8px; cursor: pointer;
}
</style>
""" % {
    "BG_PAGE": BG_PAGE, "BG_TOPBAR": BG_TOPBAR, "BG_SIDEBAR": BG_SIDEBAR,
    "BG_MAIN": BG_MAIN, "BG_CARD": BG_CARD, "BG_INPUT": BG_INPUT,
    "BG_PILL": BG_PILL, "BG_PILL_ACT": BG_PILL_ACT,
    "ACCENT": ACCENT, "ACCENT_DARK": ACCENT_DARK,
    "TEXT_PRIMARY": TEXT_PRIMARY, "TEXT_SECONDARY": TEXT_SECONDARY,
    "TEXT_MUTED": TEXT_MUTED, "TEXT_DIM": TEXT_DIM,
    "TEXT_FAINT": TEXT_FAINT, "TEXT_GHOST": TEXT_GHOST,
    "BORDER": BORDER, "BORDER_INPUT": BORDER_INPUT,
    "BORDER_SUBTLE": BORDER_SUBTLE,
    "GREEN": GREEN, "RED": RED, "AMBER": AMBER,
    "GREEN_BG": GREEN_BG, "RED_BG": RED_BG, "AMBER_BG": AMBER_BG,
}
