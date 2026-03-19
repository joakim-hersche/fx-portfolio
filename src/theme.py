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
TEXT_DIM      = "#7B8BA0"
TEXT_FAINT    = "#8494A7"
TEXT_GHOST    = "#7B8BA0"  # bumped from #5A6A7A for WCAG AA (4.8:1 on dark inputs)
TEXT_BRIGHT   = "#E2E8F0"

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
/* Self-hosted Inter font (local first, CDN fallback) */
@font-face { font-family:'Inter'; font-style:normal; font-weight:400; font-display:swap; src:url('/static/fonts/Inter-Regular.woff2') format('woff2'); }
@font-face { font-family:'Inter'; font-style:normal; font-weight:500; font-display:swap; src:url('/static/fonts/Inter-Medium.woff2') format('woff2'); }
@font-face { font-family:'Inter'; font-style:normal; font-weight:600; font-display:swap; src:url('/static/fonts/Inter-SemiBold.woff2') format('woff2'); }
@font-face { font-family:'Inter'; font-style:normal; font-weight:700; font-display:swap; src:url('/static/fonts/Inter-Bold.woff2') format('woff2'); }

/* ── Spacing scale ─────────────────────────────────────── */
:root {
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-5: 20px; --sp-6: 24px;
  --grid-gap: 12px;
}

/* ── Reset Quasar/NiceGUI defaults ─────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
body, .q-page, .nicegui-content {
  background: %(BG_PAGE)s !important;
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
  color: %(TEXT_PRIMARY)s !important;
}

/* ── Hide NiceGUI default header/drawer styling ────────── */
.q-header { background: %(BG_TOPBAR)s !important; border-bottom: 1px solid %(BORDER)s !important; box-shadow: none !important; overflow: hidden !important; padding-top: 0 !important; padding-bottom: 0 !important; }
.q-header .q-toolbar { min-height: 48px !important; padding: 0 20px !important; display: flex !important; align-items: center !important; }
.q-header .q-toolbar__title { display: none !important; }
.q-header > .nicegui-row,
.q-header .q-toolbar > .nicegui-row { margin: auto 0 !important; }
.q-header .q-field { max-height: 32px !important; }
.q-header .q-field__control { min-height: 32px !important; max-height: 32px !important; padding: 0 8px !important; align-items: center !important; }
.q-header .q-field__native { padding: 0 !important; font-size: 12px !important; height: auto !important; min-height: 0 !important; }
.q-header .q-btn { height: 32px !important; }
.q-drawer { background: %(BG_SIDEBAR)s !important; border-right: 1px solid %(BORDER)s !important; }
.q-tab-panels { background: %(BG_MAIN)s !important; padding: 0 !important; }
.q-tab-panel { background: %(BG_MAIN)s !important; padding: 24px 20px !important; }
.q-page { max-width: none !important; width: 100%% !important; }
.q-page > .nicegui-content,
.q-page .nicegui-content,
.nicegui-content { max-width: none !important; }
.q-page > .nicegui-content { padding: 0 !important; }
.q-tab-panel .nicegui-content,
.q-tab-panel > .nicegui-content,
.q-tab-panel > div > .nicegui-content { width: 100%% !important; max-width: none !important; padding: 0 !important; }
.q-tab-panel .nicegui-column { width: 100%% !important; gap: var(--grid-gap) !important; }
.q-tab-panel > .nicegui-content > .nicegui-column > :first-child {
    padding-top: 12px;
}
.q-tabs { background: %(BG_MAIN)s !important; border-bottom: none !important; padding: 6px 0 !important; }
.q-tabs__content { justify-content: center !important; }
.q-tab { flex: 0 0 auto !important; align-self: center !important; border-bottom: 1px solid %(BORDER)s !important; }
.q-tab { text-transform: none !important; font-family: 'Inter', sans-serif !important; font-size: 12px !important; font-weight: 500 !important; letter-spacing: 0.01em !important; color: %(TEXT_FAINT)s !important; }
.q-tab--active { color: %(TEXT_PRIMARY)s !important; font-weight: 600 !important; }
.q-tab-indicator { background: %(ACCENT)s !important; height: 3px !important; }

/* ── Sidebar form styling ──────────────────────────────── */
.sidebar-section-header {
  font-size: 10px; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: %(TEXT_FAINT)s;
  padding: 4px 4px 6px 4px; margin-top: 4px;
}
.sidebar-divider {
  border: none; border-top: 1px solid %(BORDER_SUBTLE)s; margin: 8px 0;
}

/* Form inputs inside sidebar */
.sidebar .q-field__control { background: %(BG_INPUT)s !important; border: 1px solid %(BORDER_INPUT)s !important; border-radius: 5px !important; min-height: 26px !important; padding: 0 8px !important; }
.sidebar .q-field__label { display: none !important; }
.sidebar .q-field__bottom { display: none !important; }
.sidebar .q-field__native, .sidebar .q-field__input { font-size: 12px !important; color: %(TEXT_MUTED)s !important; font-family: 'Inter', sans-serif !important; padding: 5px 0 !important; }
.sidebar .q-field__native::placeholder, .sidebar .q-field__input::placeholder { color: %(TEXT_GHOST)s !important; }
.sidebar .q-field { padding-bottom: 0 !important; margin-bottom: 6px !important; width: 100%% !important; }
.sidebar .q-field--dense { margin-bottom: 6px !important; }
.sidebar .q-btn.add-btn { width: 100%% !important; box-sizing: border-box !important; }
.sidebar .q-uploader { width: 100%% !important; }

/* Sidebar flex layout */
.sidebar .q-drawer__content > div {
  display: flex !important; flex-direction: column !important;
  gap: 4px !important;
}
.sidebar .nicegui-content { padding: 0 !important; }

/* Add button Quasar override */
.sidebar .add-btn.q-btn { min-height: 32px !important; padding: 8px 0 !important; }

/* Position row remove button */
.position-row .q-btn { opacity: 0.4; transition: opacity 0.15s; flex-shrink: 0; }
.position-row:hover .q-btn { opacity: 1; }

/* Form label above fields */
.form-label { display: block; font-size: 10px; font-weight: 500; color: %(TEXT_DIM)s; margin-bottom: 3px; padding-left: 2px; }

/* ── Position list in sidebar ──────────────────────────── */
.position-row {
  display: flex; align-items: center; gap: var(--sp-2); width: 100%%; box-sizing: border-box;
  padding: 5px 4px; border-radius: 5px; cursor: default;
}
.position-row:hover { background: rgba(255,255,255,0.04); }
.pos-dot { width: 8px; height: 8px; border-radius: 50%%; flex-shrink: 0; }
.pos-info { flex: 1; min-width: 0; }
.pos-ticker { font-size: 11px; font-weight: 600; color: %(TEXT_BRIGHT)s; }
.pos-name { font-size: 10px; color: %(TEXT_FAINT)s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pos-value { font-size: 11px; font-weight: 500; color: %(TEXT_MUTED)s; text-align: right; }

/* ── Add button ────────────────────────────────────────── */
.add-btn {
  width: 100%%; background: %(ACCENT_DARK)s; border: none; border-radius: 5px;
  color: #fff; font-family: inherit; font-size: 12px; font-weight: 600;
  padding: 6px 0; cursor: pointer; margin-top: 4px; text-align: center;
}
.add-btn:hover { opacity: 0.9; }

/* ── Sidebar action buttons ────────────────────────────── */
.sidebar-btn {
  width: 100%%; background: transparent;
  border: 1px solid %(BORDER_INPUT)s; border-radius: 5px;
  color: %(TEXT_DIM)s; font-family: inherit; font-size: 12px;
  font-weight: 500; padding: 6px 0; cursor: pointer;
  margin-bottom: 4px; text-align: center;
}
.sidebar-btn:hover { border-color: rgba(255,255,255,0.15); color: %(TEXT_MUTED)s; }

/* ── KPI cards ─────────────────────────────────────────── */
.kpi-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: var(--grid-gap); width: 100%%; }
.kpi-card {
  background: %(BG_CARD)s; border: 1px solid %(BORDER)s;
  border-radius: 10px; padding: 16px 18px; box-sizing: border-box;
}
.kpi-card.hero { padding: 18px 20px; }
.kpi-label {
  font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: %(TEXT_FAINT)s; margin-bottom: 6px;
}
.kpi-value { font-size: 22px; font-weight: 700; color: %(TEXT_PRIMARY)s; line-height: 1.15; }
.kpi-card.hero .kpi-value { font-size: 26px; }
.kpi-sub { font-size: 12px; color: %(TEXT_DIM)s; margin-top: 4px; }
.kpi-sub.sm { font-size: 10px; margin-top: 2px; }
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
  border-radius: 10px; padding: 16px; box-sizing: border-box;
}
.chart-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.chart-card .nicegui-column { padding-top: 0 !important; margin-top: 0 !important; gap: 8px !important; }
.chart-card .nicegui-column > :first-child { margin-top: 0 !important; }
.chart-card .nicegui-column > .nicegui-row { margin: 0 !important; padding: 0 !important; }
.chart-card .row { margin-left: 0 !important; margin-right: 0 !important; }
.chart-title {
  font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: %(TEXT_MUTED)s;
}
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--grid-gap); width: 100%%; align-items: stretch; }
.charts-row > * { display: flex; flex-direction: column; }
.charts-row .chart-card { flex: 1; display: flex; flex-direction: column; }

/* Plotly charts fill their container */
.js-plotly-plot, .plotly, .plot-container { width: 100%% !important; }
.js-plotly-plot .main-svg { width: 100%% !important; }
.plotly-notifier { display: none; }

/* ── Content divider ───────────────────────────────────── */
.content-divider {
  border: none; border-top: 1px solid %(BORDER_SUBTLE)s; margin: 0;
}

/* ── Table styling ─────────────────────────────────────── */
.table-wrap {
  width: 100%%; overflow: hidden; border-radius: 8px; border: 1px solid %(BORDER)s; box-sizing: border-box;
}
.table-wrap table { width: 100%%; border-collapse: collapse; font-size: 12px; }
.table-wrap thead tr { background: %(BG_TOPBAR)s; border-bottom: 1px solid %(BORDER)s; }
.table-wrap thead th {
  padding: 10px 12px; text-align: left; font-size: 10px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase; color: %(TEXT_FAINT)s;
}
.table-wrap tbody tr { border-bottom: 1px solid rgba(255,255,255,0.04); }
.table-wrap tbody tr:last-child { border-bottom: none; }
.table-wrap tbody tr:hover { background: rgba(255,255,255,0.03); }
.table-wrap tbody td { padding: 9px 12px; color: %(TEXT_SECONDARY)s; }
.table-wrap tbody td.td-pos { color: %(GREEN)s; font-weight: 600; }
.table-wrap tbody td.td-neg { color: %(RED)s; font-weight: 600; }
.table-wrap tbody td.td-amb { color: %(AMBER)s; font-weight: 600; }
.td-ticker { font-weight: 700; color: %(TEXT_PRIMARY)s; display: flex; align-items: center; gap: 6px; }
.hm-cell { aspect-ratio: 1; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 600; color: rgba(255,255,255,0.85); }
.hm-label { font-size: 10px; font-weight: 700; color: %(TEXT_FAINT)s; display: flex; align-items: center; justify-content: center; }
.preview-card { background: %(BG_PILL)s; border: 1px solid %(BORDER_SUBTLE)s; border-radius: 8px; padding: 14px 18px; width: 100%%; box-sizing: border-box; }
.preview-grid > * { width: 100%%; min-width: 0; }
.preview-card-label { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: %(TEXT_FAINT)s; margin-bottom: 4px; }
.preview-card-text { font-size: 12px; color: %(TEXT_FAINT)s; }
.table-wrap thead th.right, .table-wrap tbody td.right { text-align: right; }

/* ── Tooltip on table headers ────────────────────────── */
.th-tip { cursor: help; }
.th-tip::after {
  content: ' \u24d8'; font-size: 9px; color: %(TEXT_DIM)s; font-weight: 400;
  vertical-align: super; letter-spacing: normal; text-transform: none;
}

/* ── 52-week range bar ────────────────────────────────── */
.range-bar-bg {
  width: 100%%; height: 6px; background: rgba(255,255,255,0.08);
  border-radius: 3px; position: relative;
}
.range-bar-fill {
  position: absolute; height: 100%%;
  background: linear-gradient(90deg, #334155, #475569);
  border-radius: 3px;
}
.range-bar-dot {
  position: absolute; width: 8px; height: 8px;
  background: #94A3B8; border-radius: 50%%;
  top: -1px; transform: translateX(-50%%);
  border: 1.5px solid %(BG_MAIN)s;
}

/* ── Metric cards (forecast) ───────────────────────────── */
.metric-card {
  background: %(BG_PILL)s; border: 1px solid %(BORDER)s;
  border-radius: 8px; padding: 12px 14px; box-sizing: border-box;
  min-height: 94px;
}
.metric-label {
  font-size: 10px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: %(TEXT_FAINT)s; margin-bottom: 5px;
}
.metric-value { font-size: 20px; font-weight: 700; color: %(TEXT_PRIMARY)s; }
.metric-sub { font-size: 10px; color: %(TEXT_DIM)s; margin-top: 3px; }

/* Override Quasar toggle to match design pill buttons */
.q-btn-toggle { border: none !important; background: transparent !important; gap: 4px !important; padding: 0 !important; }
.q-btn-toggle .q-btn {
    font-size: 10px !important; font-weight: 500 !important;
    padding: 4px 10px !important; border-radius: 4px !important;
    min-height: 28px !important; min-width: 0 !important;
    color: %(TEXT_DIM)s !important; background: #191A21 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    text-transform: none !important;
    line-height: 1.2 !important;
    letter-spacing: normal !important;
}
.q-btn-toggle .q-btn .q-btn__content { padding: 0 !important; gap: 0 !important; }
.q-btn-toggle .q-btn--active {
    background: #252A3A !important; color: #93C5FD !important;
    border-color: rgba(59,130,246,0.4) !important;
}
/* Remove Quasar's separator between toggle buttons */
.q-btn-toggle .q-btn-group { gap: 4px !important; }
.q-btn-toggle .q-btn + .q-btn { margin-left: 0 !important; }
.q-btn-toggle .q-btn:not(:first-child) { border-left: 1px solid rgba(255,255,255,0.07) !important; }

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

/* ── Responsive grid classes ─────────────────────────── */
.risk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--grid-gap); width: 100%%; align-items: stretch; }
.risk-grid > * { display: flex; flex-direction: column; }
.risk-grid > * > .chart-card { flex: 1; display: flex; flex-direction: column; }
.metric-grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--grid-gap); width: 100%%; }
.metric-grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--grid-gap); width: 100%%; }
.preview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--grid-gap); width: 100%%; }
.diag-row { display: flex; gap: var(--grid-gap); align-items: stretch !important; flex-wrap: wrap; width: 100%%; }
.diag-row > * { flex: 1; min-width: 280px; }
.diag-row > * { align-self: stretch !important; }
.diag-row > .nicegui-column.chart-card,
.diag-row > .chart-card { height: auto !important; flex: 1 1 0 !important; display: flex !important; flex-direction: column !important; }

/* ── Responsive: KPI at medium width ─────────────────── */
@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: 1fr 1fr; gap: 10px; }
}

/* ── Responsive: Tablet (< 1024px) ────────────────────── */
@media (max-width: 1023px) {
  .charts-row { grid-template-columns: 1fr; gap: 12px; }
  .risk-grid { grid-template-columns: 1fr; }
  .metric-grid-4 { grid-template-columns: repeat(2, 1fr); }
  .metric-grid-3 { grid-template-columns: repeat(2, 1fr); }
  .preview-grid { grid-template-columns: repeat(2, 1fr); }
  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .table-wrap table { min-width: 600px; }
}

/* ── Responsive: Mobile (< 768px) ─────────────────────── */
@media (max-width: 767px) {
  /* Sidebar: collapse via NiceGUI drawer breakpoint; reduce width when open */
  .q-drawer { width: 260px !important; max-width: 80vw !important; }

  /* KPI cards: single column */
  .kpi-row { flex-direction: column !important; gap: 8px !important; }
  .kpi-card { min-width: 100%% !important; }
  .kpi-card, .kpi-card.hero { padding: 14px 16px; }
  .kpi-value { font-size: 20px; }
  .kpi-card.hero .kpi-value { font-size: 22px; }
  .kpi-label { font-size: 10px; letter-spacing: 0.1em; }

  /* Charts: full width, stack vertically */
  .charts-row { grid-template-columns: 1fr; gap: 10px; }
  .chart-card { padding: 12px !important; }

  /* Tables: horizontal scroll */
  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .table-wrap table { min-width: 600px; }

  /* Tab panels: reduce padding */
  .q-tab-panels, .q-tab-panel { padding: 12px !important; }

  /* Tabs: scroll horizontally if many tabs */
  .q-tabs { overflow-x: auto; }
  .q-tab { font-size: 11px !important; min-width: auto !important; padding: 0 10px !important; }

  /* Topbar: tighten */
  .q-header { padding-left: 8px !important; padding-right: 8px !important; }

  /* Metric cards: stack */
  .metric-card { padding: 10px 12px; }
  .metric-value { font-size: 18px; }

  /* Sidebar section headers */
  .sidebar-section-header { font-size: 10px; }

  .metric-grid-4 { grid-template-columns: 1fr 1fr; }
  .metric-grid-3 { grid-template-columns: 1fr; }
  .preview-grid { grid-template-columns: 1fr; }
  .diag-row > * { min-width: 0; flex-basis: 100%%; }

  .q-drawer__backdrop {
    background: rgba(0, 0, 0, 0.5) !important;
  }

  .tab-bar-wrapper {
    position: relative;
    width: 100%%;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }
  .tab-bar-wrapper::after {
    content: '';
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 40px;
    background: linear-gradient(to right, transparent, %(BG_MAIN)s);
    pointer-events: none;
    z-index: 1;
  }
}

/* ── Responsive: Small mobile (< 480px) ───────────────── */
@media (max-width: 479px) {
  .kpi-value { font-size: 18px; }
  .kpi-card.hero .kpi-value { font-size: 20px; }
  .kpi-sub { font-size: 10px; }
  .chart-title { font-size: 10px; }
  .table-wrap table { font-size: 11px; }
  .table-wrap thead th { padding: 8px 8px; font-size: 10px; }
  .table-wrap tbody td { padding: 7px 8px; }
}

/* ── Touch-friendly targets ───────────────────────────── */
@media (pointer: coarse) {
  .pill { padding: 6px 12px; font-size: 11px; }
  .add-btn { padding: 10px 0; font-size: 12px; }
  .sidebar-btn { padding: 10px 0; font-size: 12px; }
  .position-row { padding: 8px 6px; }
  .q-btn-toggle .q-btn { min-height: 44px !important; min-width: 44px !important; }
  .position-row .q-btn { opacity: 1 !important; min-width: 32px !important; min-height: 32px !important; }
}

/* ── Quasar notification dark theme overrides ─────────── */
.q-notification { background: %(BG_CARD)s !important; border: 1px solid %(BORDER)s !important; color: %(TEXT_PRIMARY)s !important; font-family: 'Inter', sans-serif !important; }
.q-notification__message { color: %(TEXT_PRIMARY)s !important; }

/* ── Dropdown menus (select, date picker, context menus) ── */
.q-menu {
    background: %(BG_CARD)s !important;
    border: 1px solid %(BORDER)s !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4) !important;
}
.q-item {
    color: %(TEXT_SECONDARY)s !important;
    font-size: 12px !important;
    min-height: 36px !important;
}
.q-item:hover, .q-item--active {
    background: rgba(59,130,246,0.1) !important;
    color: %(TEXT_PRIMARY)s !important;
}
.q-item__label {
    color: inherit !important;
}

/* ── Date picker ── */
.q-date {
    background: %(BG_CARD)s !important;
    color: %(TEXT_PRIMARY)s !important;
    border: 1px solid %(BORDER)s !important;
}
.q-date__header {
    background: rgba(59,130,246,0.15) !important;
    color: %(TEXT_PRIMARY)s !important;
}
.q-date__calendar-item .q-btn {
    color: %(TEXT_SECONDARY)s !important;
}
.q-date__calendar-item .q-btn--unelevated {
    background: %(ACCENT)s !important;
    color: #fff !important;
}
.q-date__navigation .q-btn {
    color: %(TEXT_MUTED)s !important;
}

/* ── Switch ── */
.q-toggle__inner {
    color: %(TEXT_DIM)s !important;
}
.q-toggle__inner--truthy {
    color: %(ACCENT)s !important;
}

/* ── Checkbox ── */
.q-checkbox__inner {
    color: %(TEXT_DIM)s !important;
}
.q-checkbox__inner--truthy {
    color: %(ACCENT)s !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(255,255,255,0.2);
}
/* Firefox */
* {
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.12) transparent;
}

/* ── Text selection ── */
::selection {
    background: rgba(59,130,246,0.3);
    color: %(TEXT_PRIMARY)s;
}

/* ── Spinner ── */
.q-spinner {
    color: %(ACCENT)s !important;
}

/* ── Toggle button hover/focus ── */
.q-btn-toggle .q-btn:not(.q-btn--active):hover {
    background: rgba(255,255,255,0.06) !important;
}
.q-btn-toggle .q-btn:focus-visible {
    outline: 1px solid %(ACCENT)s !important;
    outline-offset: -1px;
}

/* ── Notification variants ── */
.q-notification {
    font-family: 'Inter', system-ui, sans-serif !important;
}
.q-notification .q-btn {
    color: %(TEXT_PRIMARY)s !important;
}

/* ── Table zebra striping ── */
.table-wrap tbody tr:nth-child(even) {
    background: rgba(255,255,255,0.015);
}

/* ── Plotly modebar ── */
.js-plotly-plot .modebar {
    background: transparent !important;
}
.js-plotly-plot .modebar-btn path {
    fill: %(TEXT_DIM)s !important;
}
.js-plotly-plot .modebar-btn:hover path {
    fill: %(TEXT_MUTED)s !important;
}

/* ── PWA standalone mode: hide browser chrome padding ─── */
@media (display-mode: standalone) {
  body { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
  .q-header { padding-top: env(safe-area-inset-top); }
}

/* Dialog styling — match dashboard dark theme */
.q-dialog__backdrop { background: rgba(0,0,0,0.6) !important; }
.q-dialog .q-card {
    box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
}
.q-dialog .q-card .q-btn { min-height: 0 !important; }

/* Allocation bar chart — custom hover tooltip */
.alloc-bar { position: relative; }
.alloc-tip {
    display: none;
    position: absolute;
    left: 70px; bottom: calc(100%% + 6px);
    background: %(BG_CARD)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 8px 10px;
    white-space: nowrap;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    pointer-events: none;
}
.alloc-tip::after {
    content: '';
    position: absolute;
    top: 100%%; left: 20px;
    border: 5px solid transparent;
    border-top-color: %(BORDER)s;
}
.alloc-bar:hover .alloc-tip { display: block; }
.alloc-bar:hover > div:nth-child(2) { opacity: 0.85; }

/* Sidebar search — vertically center input text */
.sidebar-search .q-field__control {
    min-height: 36px !important;
    height: 36px !important;
    align-items: center !important;
}
.sidebar-search .q-field__control-container {
    padding-top: 0 !important;
}
.sidebar-search .q-field__native,
.sidebar-search .q-field__input {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    min-height: 36px !important;
    display: flex !important;
    align-items: center !important;
}
.sidebar-search .q-field__label {
    top: 50%% !important;
    transform: translateY(-50%%) !important;
}
.sidebar-search.q-field--focused .q-field__label,
.sidebar-search.q-field--float .q-field__label {
    transform: translateY(-130%%) scale(0.75) !important;
    top: 0 !important;
}

/* Reserve space for Plotly charts to prevent scroll jumps */
.chart-card .js-plotly-plot,
.chart-card .plotly {
    min-height: 380px;
}
</style>
""" % {
    "BG_PAGE": BG_PAGE, "BG_TOPBAR": BG_TOPBAR, "BG_SIDEBAR": BG_SIDEBAR,
    "BG_MAIN": BG_MAIN, "BG_CARD": BG_CARD, "BG_INPUT": BG_INPUT,
    "BG_PILL": BG_PILL, "BG_PILL_ACT": BG_PILL_ACT,
    "ACCENT": ACCENT, "ACCENT_DARK": ACCENT_DARK,
    "TEXT_PRIMARY": TEXT_PRIMARY, "TEXT_SECONDARY": TEXT_SECONDARY,
    "TEXT_MUTED": TEXT_MUTED, "TEXT_DIM": TEXT_DIM,
    "TEXT_FAINT": TEXT_FAINT, "TEXT_GHOST": TEXT_GHOST, "TEXT_BRIGHT": TEXT_BRIGHT,
    "BORDER": BORDER, "BORDER_INPUT": BORDER_INPUT,
    "BORDER_SUBTLE": BORDER_SUBTLE,
    "GREEN": GREEN, "RED": RED, "AMBER": AMBER,
    "GREEN_BG": GREEN_BG, "RED_BG": RED_BG, "AMBER_BG": AMBER_BG,
}
