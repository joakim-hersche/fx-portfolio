# Mobile Sidebar Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the mobile sidebar as a purpose-built fullscreen panel with three zones (fixed top, scrollable positions, pinned bottom) and swipe-to-reveal edit/delete actions on position rows.

**Architecture:** Mobile-only changes using CSS classes and conditional rendering. Desktop sidebar stays untouched. Position rows use Quasar's `QSlideItem` for native swipe gestures on mobile, with the existing inline icons on desktop. The sidebar layout uses CSS flexbox to create the three-zone structure.

**Tech Stack:** NiceGUI 3.8.0, Quasar QSlideItem, CSS media queries

**Spec:** `docs/superpowers/specs/2026-03-21-mobile-sidebar-redesign.md`

---

## File Structure

| File | Changes |
|------|---------|
| `src/theme.py` | Replace existing mobile sidebar CSS with three-zone flex layout, slide-item styling, action button grid, position row styles |
| `src/ui/sidebar.py` | Dual-render position rows (desktop: current inline icons, mobile: QSlideItem rows), restructure action buttons into grid layout on mobile |
| `main.py` | Restructure sidebar header (title + close + search as Zone 1), move currency selector into Zone 3 with action buttons, add swipe hint JS |

---

### Task 1: Mobile Sidebar CSS — Three-Zone Layout

**Files:**
- Modify: `src/theme.py` (mobile media query section)

- [ ] **Step 1.1: Read the current mobile sidebar CSS**

Read `src/theme.py` lines 396-430 to see existing mobile sidebar rules.

- [ ] **Step 1.2: Replace mobile sidebar CSS**

Remove all existing mobile sidebar rules inside the `@media (max-width: 767px)` block (the `.q-drawer`, `.q-drawer .sidebar`, `.q-drawer__content`, `.sidebar-bottom-actions`, etc. rules) and replace with:

```css
  /* ── Mobile sidebar: three-zone flex layout ── */
  .q-drawer { width: 100vw !important; max-width: 100vw !important; }
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
    padding: 0 !important;
  }

  /* Zone 1: Fixed top — title + close + search */
  .sidebar-zone-top {
    flex-shrink: 0;
    padding: 12px 20px 8px;
    padding-top: calc(12px + env(safe-area-inset-top, 0px));
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }

  /* Zone 2: Scrollable middle — positions */
  .sidebar-zone-positions {
    flex: 1;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    min-height: 0;
    padding: 8px 0;
  }

  /* Zone 3: Pinned bottom — actions + currency */
  .sidebar-zone-bottom {
    flex-shrink: 0;
    border-top: 1px solid rgba(255,255,255,0.08);
    background: #161719;
    padding: 12px 20px;
    padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  }

  /* Mobile position rows */
  .mobile-position-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 20px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
  }

  /* QSlideItem overrides for dark theme */
  .q-slide-item { background: transparent !important; }
  .q-slide-item__left { background: #2563EB !important; }
  .q-slide-item__right { background: #DC2626 !important; }

  /* Action button grid */
  .sidebar-action-grid {
    display: flex !important;
    gap: 8px;
    margin-bottom: 10px;
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

  /* Ensure mobile-only elements render inside drawer */
  .q-drawer .mobile-only { display: block !important; visibility: visible !important; }
  .q-drawer .desktop-only { display: none !important; }

  /* Sidebar tighten */
  .q-drawer .sidebar .q-field { margin-bottom: 0 !important; }
  .sidebar .q-btn, .sidebar .sidebar-btn {
    min-height: 40px !important;
    font-size: 13px !important;
  }

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
    min-height: 36px !important;
  }
```

- [ ] **Step 1.3: Verify theme.py parses**

Run: `python3 -c "from src.theme import GLOBAL_CSS; print('OK', len(GLOBAL_CSS))"`

- [ ] **Step 1.4: Commit**

```bash
git add src/theme.py
git commit -m "style: mobile sidebar three-zone CSS — top, scrollable positions, pinned bottom"
```

---

### Task 2: Restructure Sidebar Content Into Zones

**Files:**
- Modify: `main.py` (sidebar section, lines ~460-499)
- Modify: `src/ui/sidebar.py` (position list and action buttons)

- [ ] **Step 2.1: Read current main.py sidebar section**

Read `main.py` lines 460-500 to understand the current sidebar structure.

- [ ] **Step 2.2: Restructure main.py sidebar into three zones**

Replace the current sidebar content in `main.py` (from `_drawer_ref["drawer"] = sidebar_drawer` to end of the `with sidebar_drawer:` block) with:

```python
        _drawer_ref["drawer"] = sidebar_drawer

        # ── Zone 1: Fixed top (mobile) — title + close + search ──
        with ui.element("div").classes("sidebar-zone-top mobile-only"):
            with ui.row().classes("w-full items-center justify-between").style("margin-bottom:10px;"):
                ui.label("Portfolio").style(
                    f"font-size:15px;font-weight:700;color:{TEXT_PRIMARY};"
                )
                ui.button(
                    icon="close", on_click=lambda: sidebar_drawer.hide()
                ).props("flat dense round size=md color=none").style(
                    f"color:{TEXT_MUTED};min-width:44px;min-height:44px;"
                )

        # ── Zone 2 wrapper: scrollable positions area ──
        # The sidebar build function renders search + positions inside here
        # On desktop, the entire sidebar scrolls normally (no zones)
        build_sidebar(portfolio, stock_options, _shared, _active_tab, on_mutation=_mutation_ref)

        # ── Zone 3: Pinned bottom (mobile) — actions + currency ──
        # Currency selector (already rendered by build_sidebar's action buttons)
        # We add the currency pills here
        with ui.element("div").classes("sidebar-zone-bottom mobile-only"):
            # Currency selector
            ui.html(
                f'<div style="font-size:10px;font-weight:700;color:{TEXT_MUTED};'
                f'letter-spacing:0.04em;text-transform:uppercase;margin-bottom:6px;">Currency</div>'
            )
            sidebar_pill = ui.element("div").classes("sidebar-currency-pills").style(
                f"display:flex;width:100%;border:1px solid rgba(59,130,246,0.3);border-radius:8px;overflow:hidden;"
            )
            with sidebar_pill:
                for i, ccy in enumerate(currencies):
                    style = _pill_active if ccy == currency else _pill_inactive
                    if i == 0:
                        style = style.replace("border-left:1px solid rgba(59,130,246,0.2); ", "")
                    ui.button(
                        ccy,
                        on_click=lambda c=ccy: _on_pill_click(c),
                    ).props("flat dense no-caps size=sm unelevated").style(style)
```

Remove the old mobile close button and old mobile currency selector that were previously in main.py.

- [ ] **Step 2.3: Wrap sidebar.py sections with zone classes**

In `src/ui/sidebar.py`, in `build_sidebar()`:

**a)** Wrap the "Add Position" section (search bar + detail fields, lines ~80-183) and the positions list section (lines ~350-508) in a div with class `sidebar-zone-positions`:

Find the start of the Add Position section:
```python
    ui.html(
        f'<div style="font-size:10px;font-weight:700;color:{TEXT_MUTED};letter-spacing:0.04em;'
        f'text-transform:uppercase;margin-bottom:4px;">Add Position</div>'
    )
```

Wrap everything from here through `positions_list()` call (line ~508) inside:
```python
    with ui.element("div").classes("sidebar-zone-positions"):
        # ... all existing Add Position + positions list code ...
```

This requires re-indenting a large block of code. Be careful with indentation.

**b)** Change the action buttons from stacked to grid layout on mobile. In the action buttons section (~line 687), change:

```python
    with ui.column().classes("w-full sidebar-bottom-actions").style("gap:6px;"):
```

To:

```python
    with ui.element("div").classes("sidebar-action-grid mobile-only"):
```

And keep the existing stacked layout for desktop:

```python
    with ui.column().classes("w-full desktop-only").style("gap:6px;"):
```

So you render both: a mobile grid and a desktop column, each showing/hiding via CSS.

For the mobile grid buttons, simplify labels:
- "Import Portfolio" → "Import" (with `upload` icon)
- "Load Sample" → "Sample" (with `science` icon)
- "Clear All" → "Clear" (with `delete_outline` icon)

- [ ] **Step 2.4: Verify no syntax errors**

Run: `python3 -c "import ast; ast.parse(open('main.py').read()); print('main OK')"` and `python3 -c "from src.ui.sidebar import build_sidebar; print('sidebar OK')"`

- [ ] **Step 2.5: Commit**

```bash
git add main.py src/ui/sidebar.py
git commit -m "feat: restructure mobile sidebar into three zones — top, positions, bottom"
```

---

### Task 3: Swipe-to-Reveal Position Rows

**Files:**
- Modify: `src/ui/sidebar.py` (position list rendering, lines ~438-508)

- [ ] **Step 3.1: Read the current position row rendering**

Read `src/ui/sidebar.py` lines 438-508 to understand the current `positions_list()` refreshable function.

- [ ] **Step 3.2: Add mobile position rows with QSlideItem**

Inside the `positions_list()` function, after the existing position row HTML (line ~501), add a mobile-only version using `q-slide-item`:

For each ticker in the loop, after the existing `ui.html(...)` desktop row, add:

```python
                    # Mobile: swipe-to-reveal row
                    with ui.element("div").classes("mobile-only w-full"):
                        slide = ui.element("q-slide-item")
                        slide.on("left", lambda _, t=_t: _edit_lot(t, 0) if edit_bridges else None)
                        slide.on("right", lambda _, t=_t: _confirm_remove(t))

                        # Left action (swipe right to reveal) — Edit
                        with slide.add_slot("left"):
                            ui.html(
                                '<div style="display:flex;align-items:center;gap:6px;padding:0 20px;color:white;'
                                'font-size:13px;font-weight:600;">'
                                '<span class="material-icons" style="font-size:18px;">edit</span> Edit</div>'
                            )

                        # Right action (swipe left to reveal) — Delete
                        with slide.add_slot("right"):
                            ui.html(
                                '<div style="display:flex;align-items:center;gap:6px;padding:0 20px;color:white;'
                                'font-size:13px;font-weight:600;">'
                                '<span class="material-icons" style="font-size:18px;">delete</span> Delete</div>'
                            )

                        # Default slot — the position row content
                        with slide:
                            ui.html(
                                f'<div class="mobile-position-row">'
                                f'<div style="width:8px;height:8px;border-radius:50%;background:{color};flex-shrink:0;"></div>'
                                f'<div style="flex:1;min-width:0;">'
                                f'<div style="font-size:14px;font-weight:600;color:{TEXT_PRIMARY};">{ticker}</div>'
                                f'<div style="font-size:11px;color:{TEXT_DIM};">{company_name} \u00b7 {total_shares:g} shares</div>'
                                f'</div>'
                                f'<div style="text-align:right;">'
                                f'<div style="font-size:14px;font-weight:600;color:{TEXT_PRIMARY};">{value_text}</div>'
                                f'</div>'
                                f'</div>'
                            )
```

Also wrap the existing desktop row in a `desktop-only` container:

Change:
```python
                    ui.html(
                        f'<div style="display:flex;align-items:center;gap:8px;width:100%;'
```

To:
```python
                    with ui.element("div").classes("desktop-only w-full"):
                        ui.html(
                            f'<div style="display:flex;align-items:center;gap:8px;width:100%;'
```

(Adjust indentation of the closing `.classes("w-full")` accordingly.)

- [ ] **Step 3.3: Verify no syntax errors**

Run: `python3 -c "from src.ui.sidebar import build_sidebar; print('OK')"`

- [ ] **Step 3.4: Commit**

```bash
git add src/ui/sidebar.py
git commit -m "feat: swipe-to-reveal edit/delete on mobile position rows via QSlideItem"
```

---

### Task 4: Swipe Hint Animation

**Files:**
- Modify: `main.py` (add JS after sidebar auto-close)

- [ ] **Step 4.1: Read current sidebar auto-close JS**

Read `main.py` to find the `ui.run_javascript` block that auto-closes the sidebar on mobile (~line 501-508).

- [ ] **Step 4.2: Add swipe hint JS**

In the `<script>` block in `main.py` (where the a2hs banner JS lives), add:

```javascript
// Swipe hint: peek first position row on first sidebar open
function triggerSwipeHint() {
  if (localStorage.getItem('sidebar_swipe_hint')) return;
  localStorage.setItem('sidebar_swipe_hint', '1');
  setTimeout(function() {
    var firstSlide = document.querySelector('.q-slide-item .q-slide-item__content');
    if (!firstSlide) return;
    firstSlide.style.transition = 'transform 0.4s ease-out';
    firstSlide.style.transform = 'translateX(-40px)';
    setTimeout(function() {
      firstSlide.style.transition = 'transform 0.6s ease-in-out';
      firstSlide.style.transform = 'translateX(0)';
    }, 1500);
  }, 500);
}
```

Then wire it to the hamburger button. In the hamburger `on_click` handler in main.py, after `sidebar_drawer.toggle()` / `sidebar_drawer.show()`, add:

```python
ui.run_javascript("setTimeout(triggerSwipeHint, 300);")
```

Or alternatively, add a MutationObserver in the JS that triggers when the drawer opens:

```javascript
// Watch for sidebar open to trigger hint
var obs = new MutationObserver(function(muts) {
  for (var m of muts) {
    if (m.target.classList && m.target.classList.contains('q-drawer--opened')) {
      triggerSwipeHint();
      break;
    }
  }
});
var drawer = document.querySelector('.q-drawer--left');
if (drawer) obs.observe(drawer, {attributes: true, attributeFilter: ['class']});
```

The MutationObserver approach is more reliable since it catches all open methods (hamburger, programmatic).

- [ ] **Step 4.3: Verify no syntax errors**

Run: `python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"`

- [ ] **Step 4.4: Commit**

```bash
git add main.py
git commit -m "feat: swipe hint animation on first sidebar open — peeks first position row"
```

---

### Task 5: Visual Testing

**Files:** None (testing only)

- [ ] **Step 5.1: Take screenshots with Playwright**

Write and run a Playwright script that:
1. Opens the site at mobile viewport (390x844)
2. Waits for load, then opens sidebar via hamburger
3. Screenshots: sidebar with positions visible, zone layout, bottom pinned section
4. Attempts to interact with a slide item (if possible via Playwright touch events)
5. Resizes to desktop and verifies sidebar is unchanged

- [ ] **Step 5.2: Verify desktop regression**

At 1400x900:
- Sidebar shows normally with inline edit/remove icons
- No mobile-only elements visible
- Position rows use the old layout

- [ ] **Step 5.3: Final commit if fixups needed**

```bash
git add src/theme.py main.py src/ui/sidebar.py
git commit -m "fix: mobile sidebar visual adjustments"
```
