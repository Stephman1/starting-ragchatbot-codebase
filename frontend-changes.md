# Frontend Changes

## Code Quality Tooling

### New files

- **`frontend/package.json`** — npm project manifest declaring Prettier as a dev dependency with three scripts:
  - `npm run format` — auto-formats all frontend files in place
  - `npm run format:check` — checks formatting without writing (CI-friendly)
  - `npm run quality` — alias for `format:check`

- **`frontend/.prettierrc`** — Prettier configuration enforcing:
  - 4-space indentation, 100-character print width
  - Single quotes, ES5 trailing commas, LF line endings

- **`frontend/quality-check.sh`** — standalone shell script that installs deps if needed and runs `prettier --check`. Run with `./frontend/quality-check.sh` from the repo root.

### Reformatted files

- **`frontend/script.js`** — applied consistent Prettier formatting: removed double blank lines, normalised arrow-function parentheses, consistent trailing commas in object/array literals, and removed stale comments.

- **`frontend/style.css`** — applied consistent Prettier formatting: expanded single-line rules to multi-line blocks (e.g. `h1`, `h2`, `h3` font sizes, `@keyframes bounce` keyframe selectors), normalised selector grouping.

### Usage

```bash
cd frontend
npm install          # first time only
npm run format       # auto-fix formatting
npm run format:check # verify without changing files (use in CI)
# or
./frontend/quality-check.sh
```

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
