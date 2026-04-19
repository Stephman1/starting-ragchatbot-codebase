#!/usr/bin/env bash
set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v npx &>/dev/null; then
    echo "Error: npx not found. Install Node.js to run quality checks." >&2
    exit 1
fi

cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
    echo "Installing dependencies..."
    npm install
fi

echo "Running Prettier format check..."
npx prettier --check .

echo "All quality checks passed."
