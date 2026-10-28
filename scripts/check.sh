#!/usr/bin/env bash
# Detects the project's stack and runs lint/format checks. Skips
# gracefully (with a hint) when the relevant tool isn't installed,
# instead of failing the whole script.
set -uo pipefail

TARGET="${1:-.}"
cd "$TARGET"

ran_something=false
failed=false

run_check() {
  echo "[check.sh] $*"
  if ! "$@"; then
    failed=true
  fi
  ran_something=true
}

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  if command -v ruff >/dev/null 2>&1; then
    run_check ruff check .
  else
    echo "[check.sh] ruff not installed, skipping Python lint (pip install ruff)"
  fi
fi

if [ -f "package.json" ]; then
  if [ -x "node_modules/.bin/eslint" ]; then
    run_check node_modules/.bin/eslint .
  else
    echo "[check.sh] eslint not installed, skipping JS lint (npm i -D eslint)"
  fi
fi

if [ -f "go.mod" ]; then
  run_check go vet ./...
  UNFORMATTED="$(gofmt -l . 2>/dev/null || true)"
  if [ -n "$UNFORMATTED" ]; then
    echo "[check.sh] Files need gofmt:"
    echo "$UNFORMATTED"
    failed=true
  fi
  ran_something=true
fi

if [ "$ran_something" = false ]; then
  echo "[check.sh] Nothing recognized in '$TARGET', or no lint tools installed."
fi

if [ "$failed" = true ]; then
  exit 1
fi
