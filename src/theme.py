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
.tab-bar-wrapper { position: sticky; top: 48px; z-index: 10; background: %(BG_MAIN)s; border-bottom: 1px solid %(BORDER)s; }
.q-tabs__content { justify-content: center !important; }
.q-tab { flex: 0 0 auto !important; align-self: center !important; border-bottom: none !important; }
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

/* ── Risk tab hero KPIs ── */
.risk-hero .kpi-value {
    font-size: 24px;
}
.risk-hero .kpi-card {
    padding-top: 20px;
    padding-bottom: 20px;
}

/* ── Section spacing for Risk tab ── */
.risk-sections {
    display: flex;
    flex-direction: column;
    gap: 24px;
    width: 100%%;
}
.risk-sections .risk-triple {
    gap: 12px;
}

/* ── Section labels ── */
.section-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: %(TEXT_DIM)s;
    margin-bottom: 8px;
}

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
  padding: 10px 12px; text-align: left;
  color: %(TEXT_DIM)s !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.table-wrap tbody tr { border-bottom: 1px solid rgba(255,255,255,0.04); }
.table-wrap tbody tr:last-child { border-bottom: none; }
.table-wrap tbody tr:hover { background: rgba(59,130,246,0.06) !important; }
.table-wrap tbody td { padding: 9px 12px; color: %(TEXT_SECONDARY)s; }
.table-wrap tbody td.td-pos { color: %(GREEN)s; font-weight: 600; background: rgba(22,163,74,0.06); }
.table-wrap tbody td.td-neg { color: %(RED)s; font-weight: 600; background: rgba(220,38,38,0.06); }
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
.risk-triple { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--grid-gap); width: 100%%; align-items: stretch; }
.risk-triple > * { display: flex; flex-direction: column; min-width: 0; }
.risk-triple .chart-card { flex: 1; display: flex; flex-direction: column; }
.diag-row { display: flex; gap: var(--grid-gap); align-items: stretch !important; flex-wrap: wrap; width: 100%%; }
.diag-row > * { flex: 1; min-width: 280px; }
.diag-row > * { align-self: stretch !important; }
.diag-row > .nicegui-column.chart-card,
.diag-row > .chart-card { height: auto !important; flex: 1 1 0 !important; display: flex !important; flex-direction: column !important; }

/* ── Responsive: KPI at medium width ─────────────────── */
@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: 1fr 1fr; gap: 10px; }
}

/* ── Device-tier utility classes ── */
.mobile-only { display: none !important; }
.desktop-only { /* visible by default; hidden via pointer queries */ }
.touch-only { display: none !important; }
.touch-large-only { display: none !important; }
.not-phone { /* visible by default; hidden on touch-small */ }

/* ── Bottom tab bar (base — hidden on desktop) ── */
.mobile-tab-bar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2000;
  background: #161719;
  border-top: 1px solid rgba(255,255,255,0.07);
  justify-content: space-around;
  padding: 8px 0 calc(8px + env(safe-area-inset-bottom, 12px)) 0;
}
.hamburger-btn { display: none; }
.mobile-tab-bar .tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 44px;
  justify-content: center;
  min-width: 48px;
  gap: 3px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.mobile-tab-bar .tab-item svg { stroke: #64748B; }
.mobile-tab-bar .tab-item .q-icon { color: #64748B; }
.mobile-tab-bar .tab-item .tab-label { font-size: 10px; color: #64748B; }
.mobile-tab-bar .tab-item.active svg { stroke: #3B82F6; }
.mobile-tab-bar .tab-item.active .q-icon { color: #3B82F6; }
.mobile-tab-bar .tab-item.active .tab-label { color: #3B82F6; font-weight: 600; }

/* ── Touch-small tier (phones) ───────────────────────── */
@media (pointer: coarse) and (max-width: 767px) {
  /* Utility class */
  .not-phone { display: none !important; }

  /* ── Mobile sidebar: three-zone flex layout ── */
  .q-drawer { width: 100vw !important; max-width: 100vw !important; }
  .q-drawer__content {
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    height: 100%% !important;
  }
  .q-drawer .sidebar {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    overflow: hidden !important;
    min-height: 0 !important;
    padding: 0 !important;
    height: 100%% !important;
  }

  /* Zone 1: Fixed top — title + close + search */
  .sidebar-zone-top {
    flex-shrink: 0;
    padding: 12px 20px 8px;
    padding-top: calc(12px + env(safe-area-inset-top, 0px));
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }

  /* Zone 2: Scrollable middle — everything between top and bottom zones */
  .sidebar-zone-positions {
    flex: 1;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    min-height: 0;
    padding: 8px 0;
  }
  /* Make the entire mid-section (search + form + positions + actions) scroll as one */
  .q-drawer .sidebar > .nicegui-content {
    flex: 1 !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
  }
  /* Zone-positions should NOT independently scroll — the parent scrolls */
  .q-drawer .sidebar > .nicegui-content .sidebar-zone-positions {
    flex: none !important;
    overflow-y: visible !important;
  }

  /* Zone 3: Pinned bottom — actions + currency */
  .sidebar-zone-bottom {
    flex-shrink: 0 !important;
    flex-grow: 0 !important;
    border-top: 1px solid rgba(255,255,255,0.08);
    background: #161719;
    padding: 12px 20px;
    padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  }
  /* Move mobile action grid into the bottom zone visually */
  .sidebar-action-grid {
    position: sticky !important;
    bottom: 0;
    background: #161719;
    padding-bottom: 8px !important;
    z-index: 2;
  }

  /* Add horizontal padding to sidebar content on mobile (sidebar itself has padding:0) */
  .q-drawer .sidebar > .nicegui-content > * {
    padding-left: 16px;
    padding-right: 16px;
  }
  .q-drawer .sidebar > .nicegui-content .sidebar-zone-positions {
    padding-left: 0;
    padding-right: 0;
  }

  /* Mobile position rows */
  .mobile-position-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 20px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
  }

  /* Search bar: touch-friendly sizing */
  .q-drawer .sidebar-search .q-field__control {
    min-height: 44px !important;
    height: 44px !important;
    padding: 0 12px !important;
    border-radius: 10px !important;
  }
  .sidebar-search .q-field__prepend .q-icon { font-size: 20px !important; }

  /* QSlideItem overrides for dark theme */
  .q-slide-item { background: transparent !important; }
  .q-slide-item__left { background: #2563EB !important; }
  .q-slide-item__right { background: #DC2626 !important; }

  /* Action button grid — full-bleed past zone padding */
  .sidebar-action-grid {
    display: flex !important;
    gap: 8px;
    margin-bottom: 10px;
    margin-left: -20px;
    margin-right: -20px;
    padding: 0 12px;
  }
  .sidebar-action-grid .q-btn {
    flex: 1 !important;
    flex-direction: column !important;
    gap: 2px !important;
    padding: 10px 4px !important;
    min-height: 56px !important;
    font-size: 11px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 8px !important;
  }
  .sidebar-action-grid .q-btn .q-icon { font-size: 18px !important; }

  /* Currency pills — full-bleed past zone padding */
  .sidebar-currency-pills {
    margin-left: -20px !important;
    margin-right: -20px !important;
    padding: 0 12px !important;
  }

  /* KPI cards: single column */
  .kpi-row { grid-template-columns: 1fr !important; gap: 8px !important; }
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
  .table-wrap table.wide-table { min-width: 600px; }

  /* Metric cards: stack */
  .metric-card { padding: 10px 12px; }
  .metric-value { font-size: 18px; }

  .metric-grid-4 { grid-template-columns: 1fr 1fr; }
  .metric-grid-3 { grid-template-columns: 1fr; }
  .preview-grid { grid-template-columns: 1fr; }
  .diag-row > * { min-width: 0; flex-basis: 100%%; }

  /* Show mobile — override Quasar's body:not(.mobile) .mobile-only rule */
  .mobile-only { display: block !important; }
  body:not(.mobile) .mobile-only { display: block !important; }

  /* Health findings: stack vertically on mobile */
  .findings-row { flex-direction: column !important; }
  .findings-row > div { min-width: 100%% !important; flex: none !important; }

  /* Health score: compact on mobile */
  .health-score-container { flex-direction: row !important; gap: 16px !important; padding: 14px !important; }
  .health-score-container > div:first-child {
    width: 64px !important; height: 64px !important;
    font-size: 1.5rem !important; border-width: 3px !important;
  }

  /* Hide sections on mobile */
  .rebalancer-section { display: none !important; }
  .detailed-metrics-section { display: none !important; }

  /* Positions card list */
  .position-cards { display: flex !important; flex-direction: column; gap: 6px; }

  /* Research fundamentals 2-col */
  .fundamentals-grid { grid-template-columns: 1fr 1fr !important; }

  /* Research charts-row stack on mobile */
  .charts-row { grid-template-columns: 1fr !important; }

  /* Research search dropdown: full width on mobile */
  .q-menu { max-width: 100vw !important; left: 0 !important; right: 0 !important; }

  /* Add-to-homescreen banner */
  .a2hs-banner {
    position: fixed;
    bottom: calc(64px + env(safe-area-inset-bottom, 0px));
    left: 12px;
    right: 12px;
    z-index: 1999;
    background: #1C1D26;
    border: 1px solid rgba(59,130,246,0.3);
    border-radius: 12px;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
  }
  .a2hs-banner .a2hs-close {
    position: absolute;
    top: 8px;
    right: 10px;
    background: none;
    border: none;
    color: #64748B;
    font-size: 18px;
    cursor: pointer;
    padding: 4px;
    line-height: 1;
  }
}

/* ── Responsive: Small mobile (< 480px) ───────────────── */
@media (pointer: coarse) and (max-width: 479px) {
  .kpi-value { font-size: 18px; }
  .kpi-card.hero .kpi-value { font-size: 20px; }
  .kpi-sub { font-size: 10px; }
  .chart-title { font-size: 10px; }
  .table-wrap table { font-size: 11px; }
  .table-wrap thead th { padding: 8px 8px; font-size: 10px; }
  .table-wrap tbody td { padding: 7px 8px; }
}

/* ── Shared touch tier (all touch devices) ────────────── */
@media (pointer: coarse) {
  /* Touch targets */
  .pill { padding: 6px 12px; font-size: 11px; }
  .add-btn { padding: 10px 0; font-size: 12px; }
  .sidebar-btn { padding: 10px 0; font-size: 12px; }
  .position-row { padding: 8px 6px; }
  .q-btn-toggle .q-btn { min-height: 44px !important; min-width: 44px !important; }
  .position-row .q-btn { opacity: 1 !important; min-width: 32px !important; min-height: 32px !important; }

  /* Utility classes: show touch, hide desktop — override Quasar specificity */
  .touch-only { display: block !important; }
  body:not(.mobile) .touch-only { display: block !important; }
  .desktop-only { display: none !important; }
  body:not(.mobile) .desktop-only { display: none !important; }

  /* Bottom tab bar visible */
  .mobile-tab-bar { display: flex !important; }

  /* Hide top tab bar */
  .tab-bar-wrapper {
    position: absolute !important;
    opacity: 0 !important;
    pointer-events: none !important;
    height: 1px !important;
    overflow: hidden !important;
    z-index: -1 !important;
  }
  .tab-bar-wrapper::after { display: none !important; }

  /* Body padding for fixed bottom bar */
  .q-page, .nicegui-content {
    padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px)) !important;
  }

  /* Header: show hamburger, hide desktop controls */
  .hamburger-btn {
    display: flex !important;
    min-width: 44px !important;
    min-height: 44px !important;
    color: #F1F5F9 !important;
    opacity: 1 !important;
  }
  .hamburger-btn .q-icon { font-size: 24px !important; }
  .header-export-btn { display: none !important; }
  .header-info-btn { display: none !important; }
  .header-currency-pills { display: none !important; }

  /* Topbar: safe area for standalone PWA */
  .q-header {
    padding-left: 8px !important;
    padding-right: 8px !important;
    padding-top: env(safe-area-inset-top, 0px) !important;
    min-height: calc(48px + env(safe-area-inset-top, 0px)) !important;
  }

  /* Allow panning in both axes (needed for QSlideItem horizontal swipes)
     but block double-tap zoom. Prevent iOS back-swipe via overscroll. */
  .q-drawer--left { touch-action: manipulation !important; overscroll-behavior-x: none !important; }

  /* Drawer container: invisible and non-interactive when closed.
     Quasar handles visibility internally — we just ensure the
     container itself doesn't block touches when the drawer is off-screen. */
  .q-drawer-container {
    pointer-events: none !important;
  }
  /* Only re-enable pointer events on the backdrop and the drawer when open */
  .q-drawer__backdrop {
    pointer-events: auto !important;
    background: rgba(0, 0, 0, 0.5) !important;
  }
  .q-drawer--left.q-drawer--opened {
    pointer-events: auto !important;
  }

  /* Tab panels: reduce padding */
  .q-tab-panels, .q-tab-panel { padding: 12px !important; }

  /* Tabs: scroll horizontally */
  .q-tabs { overflow-x: auto; }
  .q-tab { font-size: 11px !important; min-width: auto !important; padding: 0 10px !important; }

  /* Sidebar buttons: touch-friendly */
  .sidebar .q-btn, .sidebar .sidebar-btn {
    min-height: 44px !important;
    font-size: 13px !important;
  }

  /* Sidebar: ensure touch/mobile elements render — override Quasar specificity */
  .q-drawer .touch-only { display: block !important; visibility: visible !important; }
  body:not(.mobile) .q-drawer .touch-only { display: block !important; visibility: visible !important; }
  .q-drawer .mobile-only { display: block !important; visibility: visible !important; }
  body:not(.mobile) .q-drawer .mobile-only { display: block !important; visibility: visible !important; }

  /* Plotly: hide modebar on touch */
  .modebar-container { display: none !important; }
  .js-plotly-plot, .plotly { width: 100%% !important; }
  .js-plotly-plot .main-svg { width: 100%% !important; }

  /* Prevent iOS zoom on input focus */
  input, select, textarea,
  .q-field__native, .q-field__input, .q-select__input,
  .q-header .q-field__native,
  .sidebar .q-field__native, .sidebar .q-field__input {
    font-size: 16px !important;
  }

  /* Sidebar section headers */
  .sidebar-section-header { font-size: 10px; }

  /* Mobile currency pills: fill width */
  .sidebar-currency-pills {
    display: flex !important;
    width: 100%% !important;
  }
  .sidebar-currency-pills .q-btn {
    flex: 1 !important;
    min-width: 0 !important;
    padding: 8px 4px !important;
    font-size: 13px !important;
    min-height: 44px !important;
  }
}

/* ── Touch-large tier (tablets: iPad etc.) ────────────── */
@media (pointer: coarse) and (min-width: 768px) {
  /* Utility classes */
  .touch-large-only { display: block !important; }
  .mobile-only { display: none !important; }

  /* Grids: 2-column layout */
  .kpi-row { grid-template-columns: 1fr 1fr; gap: 10px; }
  .charts-row { grid-template-columns: 1fr 1fr; gap: 12px; }
  .risk-triple { grid-template-columns: 1fr 1fr; gap: 12px; }
  .risk-grid { grid-template-columns: 1fr 1fr; }
  .metric-grid-4 { grid-template-columns: repeat(2, 1fr); }
  .metric-grid-3 { grid-template-columns: repeat(2, 1fr); }
  .preview-grid { grid-template-columns: repeat(2, 1fr); }

  /* Sidebar: partial-width overlay, not full-screen */
  .q-drawer { width: min(320px, 75vw) !important; max-width: min(320px, 75vw) !important; }
  .q-drawer .sidebar {
    padding: 12px 20px !important;
    padding-top: calc(8px + env(safe-area-inset-top, 0px)) !important;
  }

  /* Three-zone sidebar layout for tablets too */
  .q-drawer__content {
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
  }
  .q-drawer .sidebar {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    overflow: hidden !important;
    min-height: 0 !important;
  }
  .sidebar-zone-top { flex-shrink: 0; }
  .sidebar-zone-positions { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; min-height: 0; }
  .sidebar-zone-bottom { flex-shrink: 0; }

  /* Sidebar bottom actions: sticky */
  .q-drawer .sidebar .sidebar-bottom-actions {
    position: sticky !important;
    bottom: 0 !important;
    background: #161719 !important;
    padding-top: 8px !important;
    margin: 0 -20px !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
    padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px)) !important;
    z-index: 1;
  }
  .q-drawer .sidebar .q-field { margin-bottom: 0 !important; }

  /* Tables: horizontal scroll */
  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .table-wrap table.wide-table { min-width: 600px; }

  /* Diag row: 2-col */
  .diag-row > * { min-width: 0; flex-basis: calc(50%% - var(--grid-gap)); }

  /* Chart card padding */
  .chart-card { padding: 12px !important; }

  /* Health score: compact */
  .health-score-container { padding: 14px !important; }
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
    background: rgba(255,255,255,0.025);
}
.table-wrap thead {
    position: sticky;
    top: 0;
    z-index: 2;
    background: %(BG_CARD)s;
}

/* ── Plotly modebar — hidden for clean minimal look ── */
.js-plotly-plot .modebar {
    display: none !important;
}

/* ── PWA standalone mode: hide browser chrome padding ─── */
@media (display-mode: standalone) {
  body { padding-bottom: env(safe-area-inset-bottom); }
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

/* ── Tertiary card (rebalancing calculator) ── */
.card-tertiary {
    border-top: 2px solid %(BORDER)s;
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
