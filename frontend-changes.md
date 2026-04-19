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
