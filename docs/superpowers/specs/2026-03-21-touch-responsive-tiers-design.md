# Touch-Responsive Device Tiers

## Problem

iPads receive the desktop UI because their screen width (768px+ portrait, 1024px+ landscape) exceeds the mobile breakpoint (`max-width: 767px`). iPadOS also sends a desktop User-Agent, making server-side detection unreliable. The dashboard needs a touch-optimized experience for tablets without forcing the phone layout onto a large screen.

## Approach

Pure CSS detection using `pointer: coarse` (touch) vs `pointer: fine` (mouse/trackpad), combined with width-based breakpoints to differentiate phones from tablets. New utility classes provide granular control over which components render on each tier.

## Device Tiers

| Tier | Detection | Examples |
|------|-----------|----------|
| **Desktop** | `pointer: fine` (default) | MacBook, iMac, mouse/trackpad devices |
| **Touch-large** | `pointer: coarse` AND `min-width: 768px` | iPad, Android tablets |
| **Touch-small** | `pointer: coarse` AND `max-width: 767px` | iPhone, Android phones |

## Feature Matrix

| Feature | Desktop | Touch-large (iPad) | Touch-small (phone) |
|---------|---------|-------------------|---------------------|
| Navigation | Top tab bar | Bottom tab bar | Bottom tab bar |
| Sidebar | Docked/visible | Hidden, hamburger, partial-width overlay (~320px / 75vw) | Hidden, hamburger, full-width overlay |
| Grid layout | Multi-column | 2-column | Single column |
| Touch targets | Default sizing | 44px minimum | 44px minimum |
| KPI row | Multi-column grid | 2-column grid | Single column stack |
| Charts | Multi-column | 2-column | Single column |
| Top bar | Desktop controls | Hamburger, desktop controls hidden | Hamburger, desktop controls hidden |

## New CSS Utility Classes

| Class | Visible on | Hidden on |
|-------|-----------|-----------|
| `desktop-only` | Desktop | Touch-large, Touch-small |
| `mobile-only` | Touch-small | Desktop, Touch-large |
| `touch-only` | Touch-large + Touch-small | Desktop |
| `touch-large-only` | Touch-large | Desktop, Touch-small |
| `not-phone` | Desktop + Touch-large | Touch-small |

## CSS Structure

Reorganize existing breakpoints into pointer-based tiers:

1. **Default** — Desktop styles (unchanged)
2. **`@media (pointer: coarse)`** — All touch devices:
   - Larger touch targets (44px min)
   - Show `touch-only`, hide `desktop-only`
   - Show bottom tab bar, hamburger
   - Hide top tab bar, desktop header controls
3. **`@media (pointer: coarse) and (min-width: 768px)`** — Touch-large (iPad):
   - 2-column grids for KPIs, charts, metrics, risk
   - Sidebar: partial-width overlay (~320px or 75vw, whichever smaller)
   - Show `touch-large-only`
   - Backdrop behind sidebar
4. **`@media (pointer: coarse) and (max-width: 767px)`** — Touch-small (phone):
   - Single-column layout
   - Full-width sidebar overlay
   - Show `mobile-only`
   - Current phone-specific styles preserved
5. **`@media (max-width: 479px)`** — Small phone font adjustments (unchanged)

### Migration from width-only breakpoints

- The existing `@media (max-width: 767px)` block gets its rules moved into `@media (pointer: coarse)` (shared touch rules) and `@media (pointer: coarse) and (max-width: 767px)` (phone-only rules)
- The existing `@media (max-width: 1023px)` tablet block is superseded by the touch-large tier
- Existing `pointer: coarse` touch-target block gets merged into the new touch tier

## Python Template Changes

### Positions: cards vs table experiment

Both components are rendered; CSS controls visibility:

- Position table: `desktop-only` class (hidden on all touch devices)
- Position cards: `touch-only` class (visible on all touch devices)

If testing shows tables work better on iPad:
- Position table gets `not-phone` → visible on desktop + iPad
- Position cards get `mobile-only` → visible on phones only

### Other mobile-only / desktop-only usage

- Overview KPI layouts: evaluate per-component during implementation
- Sidebar currency pills (`mobile-only`): switch to `touch-only` — relevant on all touch devices

## Sidebar Behavior on Touch-large

- Hidden by default (not docked)
- Opened via hamburger button in header
- Renders as overlay with semi-transparent backdrop
- Width: `min(320px, 75vw)`
- Not full-screen (unlike phone)
- Closes on backdrop tap or close button

## Edge Cases

- **Dual-input devices** (e.g., Surface Pro with keyboard): these report `pointer: coarse` in some browsers and would get the touch UI. This is acceptable — the target devices are MacBooks and iPads. If needed later, `@media (hover: hover) and (pointer: fine)` can disambiguate.
- **Browsers without `pointer` support**: fall through to default desktop styles. Acceptable fallback.
- **Dual rendering**: both table and card components are rendered server-side and toggled via CSS. Acceptable for a personal dashboard with limited position counts.

## Testing

- Use Chrome DevTools device emulation to test iPad (pointer: coarse + 1024x768)
- Test on a real iPad to verify safe-area-inset, drawer touch handling, and viewport behavior
- Test both portrait and landscape orientations
- Verify sidebar partial-width overlay on iPad
- Verify full-width overlay on phone
- A/B cards vs table on iPad to determine best fit
