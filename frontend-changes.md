# Frontend Changes

## Dark/Light Mode Toggle Button

### What was added

A theme toggle button positioned fixed in the top-right corner of the UI, allowing users to switch between dark mode (default) and light mode.

### Files modified

**`frontend/index.html`**
- Added a `<button id="themeToggle">` element with `aria-label` and `title` for accessibility, placed outside the main `.container` so it overlays everything.
- Contains two inline SVGs: a sun icon (shown in dark mode) and a moon icon (shown in light mode).
- Bumped cache-busting version on `style.css` and `script.js` to `v=10`.

**`frontend/style.css`**
- Added `[data-theme="light"]` CSS variable overrides for a clean light palette (`#f8fafc` background, white surface, dark text).
- Added `.theme-toggle` button styles: fixed position top-right, 44×44px circle, bordered, subtle shadow, hover scale + focus ring.
- Sun/moon icon visibility is controlled via `display: block/none` scoped to `[data-theme="light"]`.
- Added a global transition rule for smooth color interpolation across background, border, and text when the theme switches.

**`frontend/script.js`**
- Added `initTheme()` — reads `localStorage.getItem('theme')` on load and sets `data-theme` attribute on `<html>` (defaults to `'dark'`).
- Added `toggleTheme()` — reads current `data-theme`, switches it, and persists to `localStorage`.
- Wired the button's `click` event to `toggleTheme()` inside `setupEventListeners()`.
- Called `initTheme()` from the `DOMContentLoaded` handler before session setup to prevent flash of wrong theme.

### Design decisions

- **`data-theme` on `<html>`** — setting the attribute on the root element means CSS variable overrides in `[data-theme="light"]` cascade to the entire document cleanly.
- **Dark mode is the default** — matches the existing aesthetic; the sun icon appears in dark mode as a cue to switch to light.
- **localStorage persistence** — preference survives page reloads without a backend call.
- **CSS variable approach** — swapping variables in one selector block means every component reacts automatically with no per-element light-mode rules.
- **Accessible** — button has `aria-label`, SVGs are `aria-hidden`, focus ring matches the app's existing `--focus-ring` variable, full keyboard navigability.
