# Frontend Migration Assessment: Streamlit → NiceGUI

## Context

The market dashboard (~4,500 lines of Python) has outgrown Streamlit. Two specific pain points:

1. **Full-page reruns** — every widget interaction reruns the entire script, causing flicker, scroll loss, and sluggish UX
2. **Layout & styling limitations** — 228 lines of CSS hacked in via `unsafe_allow_html`, targeting Streamlit-internal `data-testid` selectors that break on upgrades. PWA support requires monkey-patching Streamlit's `index.html`.

---

## Code Portability Analysis

~63% of the codebase is already framework-agnostic:

| Layer | Lines | Streamlit dependency |
|-------|-------|---------------------|
| `monte_carlo.py`, `charts.py`, `excel_export.py`, `stocks.py` | 2,832 | **None** — pure Python/Plotly/openpyxl |
| `data_fetch.py`, `fx.py`, `portfolio.py` | 439 | **Cache only** — `@st.cache_data` decorators |
| `app.py`, `sections/*.py`, `state.py`, `ui.py` | ~2,175 | **Full rewrite** needed |

---

## Framework Comparison

| Criterion | **NiceGUI** | **Dash** | Reflex | FastAPI+React |
|-----------|-------------|----------|--------|---------------|
| Solves reruns? | Yes (WebSocket push) | Yes (callbacks) | Yes (React) | Yes (React) |
| Solves styling? | Yes (Tailwind+Quasar) | Yes (full CSS) | Yes (Tailwind) | Yes (anything) |
| Plotly charts.py reuse | `ui.plotly(fig)` — zero changes | `dcc.Graph(figure=fig)` — zero changes | `rx.plotly(fig)` — zero changes | Needs JSON serialization over API |
| localStorage support | Built-in `app.storage.browser` | `dcc.Store` | `rx.LocalStorage` | Native browser API |
| Caching replacement | `cachetools.TTLCache` | `flask_caching` | `cachetools` | `cachetools`/Redis |
| Python-only? | Yes | Yes | Yes (but needs Node.js build) | No — requires TypeScript/React |
| API maturity | Stable v2.x, growing | Very mature, enterprise-proven | v0.6.x, API still evolving | Industry standard |
| Migration effort | **~2,175 lines rewrite** | **~2,175 lines** (more verbose callbacks) | ~2,500+ lines (state restructure) | ~4,000+ lines (two codebases) |

---

## Recommendation: NiceGUI

### Why NiceGUI over Dash (the runner-up)

- **Most Pythonic API** — `ui.button('Add', on_click=handler)` vs Dash's separate callback graph with `@app.callback` decorators
- **Built-in browser localStorage** — `app.storage.browser` eliminates the custom Streamlit component entirely
- **Tailwind CSS is first-class**, not bolted on
- **The 5 `st.rerun()` calls simply disappear** — bound UI elements update reactively
- **Right-sized** for a single-page portfolio dashboard

### Why not the others

- **Dash** — solid choice but more boilerplate; callback wiring gets verbose for the ~20 widget interactions in this app
- **Reflex** — API still unstable (v0.6.x), requires Node.js, heaviest Python-side rewrite due to `rx.State` class restructuring
- **FastAPI+React** — doubles the codebase, requires JS/TS skills, 3-5x longer timeline; overkill for a personal dashboard

---

## Migration Strategy

7 phases, each producing a working application. The Streamlit version can run in parallel until feature parity.

### Phase 0: Decouple data layer from Streamlit (framework-independent)

**Files:** `data_fetch.py`, `fx.py`, `portfolio.py`

Replace 15 `@st.cache_data` decorators with `cachetools.TTLCache`:

```python
# src/cache.py (new utility module)
from cachetools import TTLCache, cached

short_cache = TTLCache(maxsize=256, ttl=900)    # 15 min
long_cache  = TTLCache(maxsize=256, ttl=86400)  # 24 hours

# Before: @st.cache_data(ttl=900)
# After:  @cached(short_cache)
```

Mechanical find-and-replace. Function bodies unchanged. **Can be done immediately, even before committing to a framework.**

### Phase 1: Scaffold NiceGUI app shell

Create `main.py` (NiceGUI entry point) with:
- Page config, tab layout (`ui.tabs` + `ui.tab_panels`)
- Design tokens/CSS ported to Tailwind + CSS custom properties
- `app.storage.browser` for portfolio persistence (replaces `state.py` + `localstorage_component.py`)

Key mappings:
| Streamlit | NiceGUI |
|-----------|---------|
| `st.set_page_config(layout="wide")` | `ui.page` decorator |
| `st.sidebar` | `ui.left_drawer` or `ui.header` |
| `st.tabs(["Overview", ...])` | `ui.tabs` + `ui.tab_panels` |
| `st.session_state` | `app.storage.user` |
| `ls_get`/`ls_set` (custom component) | `app.storage.browser` |
| `st.markdown(css, unsafe_allow_html=True)` | `ui.add_head_html` or Tailwind classes |

### Phase 2: Port sidebar (Add/Manage Positions)

Rewrite `sections/positions.py` `render_add_manage` (~240 lines).

| Streamlit | NiceGUI |
|-----------|---------|
| `st.selectbox` | `ui.select` |
| `st.number_input` | `ui.number` |
| `st.date_input` | `ui.date` with `ui.input` |
| `st.button("Add")` | `ui.button("Add", on_click=handler)` |
| `st.file_uploader` | `ui.upload` |
| `st.download_button` | `ui.button` + `ui.download` |
| `st.rerun()` | Not needed — reactive updates |

### Phase 3: Port Overview tab (KPIs + allocation + comparison)

- KPI cards: existing HTML reusable initially, then refactor to Tailwind `ui.card` components
- Charts: `ui.plotly(fig)` — `charts.py` unchanged
- Excel download: `ui.button` + `ui.download`

### Phase 4: Port Positions tab (table + price history)

**Highest-risk element:** Pandas Styler conditional formatting → Quasar QTable slots. Interim approach: `ui.html(styled.to_html())`. **Prototype early to validate.**

### Phase 5: Port Risk & Analytics tab (~221 lines)

Standard pattern: `ui.row`/`ui.column` for layout, `ui.plotly` for charts, `ui.table` for data.

### Phase 6: Port Forecast + Diagnostics tabs (~615 lines)

| Streamlit | NiceGUI |
|-----------|---------|
| `st.metric("VaR", value, delta)` | Custom KPI card |
| `st.expander("How does...")` | `ui.expansion("How does...")` |
| `st.spinner("Simulating...")` | `ui.spinner()` |
| `st.radio("Horizon", [...], horizontal=True)` | `ui.toggle_group` or `ui.radio` |

### Phase 7: Polish and PWA

- PWA meta tags via `ui.add_head_html` (clean, no monkey-patching)
- Finalize responsive design with Tailwind breakpoints
- Remove `streamlit` from `requirements.txt`
- Delete `localstorage_component.py` and its frontend directory

---

## Files Impact Summary

| File | Action |
|------|--------|
| `src/data_fetch.py` | Replace 10 `@st.cache_data` → `cachetools` |
| `src/fx.py` | Replace 2 `@st.cache_data` → `cachetools` |
| `src/portfolio.py` | Replace 3 `@st.cache_data` → `cachetools` |
| `src/cache.py` | **New** — shared TTL cache utilities |
| `main.py` | **New** — NiceGUI entry point |
| `src/theme.py` | **New** — design tokens, Tailwind config |
| `src/state.py` | Rewrite → `app.storage.browser` |
| `src/sections/*.py` (6 files) | Full rewrite → NiceGUI widgets |
| `src/ui.py` | Rewrite → NiceGUI helpers |
| `src/localstorage_component.py` | **Delete** |
| `src/charts.py` | **No changes** |
| `src/monte_carlo.py` | **No changes** |
| `src/excel_export.py` | **No changes** |
| `src/stocks.py` | **No changes** |

---

## Parallelization

- **Phase 0** is independent of all other phases
- **Phases 3–6** are independent of each other (separate tabs); can be developed in parallel once Phases 1–2 are complete
- **`charts.py`** requires zero changes across all phases

## Risk Mitigation

1. **Both apps coexist**: `streamlit run app.py` vs `python main.py` — switch when ready
2. **Phase 0 is reversible**: `cachetools` decorators work with both frameworks
3. **Prototype the positions table early** (Phase 4) — it's the hardest UI element to port faithfully
