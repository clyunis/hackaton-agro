#!/usr/bin/env bash
# Detects the project's stack and runs its test suite. No stack-specific
# knowledge required from the caller.
set -euo pipefail

TARGET="${1:-.}"
cd "$TARGET"

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  echo "[test.sh] Detected Python project, running pytest"
  exec python -m pytest
elif [ -f "package.json" ]; then
  echo "[test.sh] Detected Node project, running npm test"
  exec npm test
elif [ -f "go.mod" ]; then
  echo "[test.sh] Detected Go project, running go test"
  exec go test ./...
elif [ -d "src/test/java" ] && ls src/test/java/*.java >/dev/null 2>&1; then
  echo "[test.sh] Detected plain Java project, compiling and running AppTest"
  BUILD_DIR=".harness-build"
  mkdir -p "$BUILD_DIR"
  javac -d "$BUILD_DIR" $(find src -name "*.java")
  exec java -cp "$BUILD_DIR" AppTest
elif [ -d "tests" ] && ls tests/*.cpp >/dev/null 2>&1; then
  echo "[test.sh] Detected plain C++ project, compiling and running tests"
  BUILD_DIR=".harness-build"
  mkdir -p "$BUILD_DIR"
  status=0
  for f in tests/*.cpp; do
    name="$(basename "$f" .cpp)"
    g++ -std=c++17 "$f" -o "$BUILD_DIR/${name}"
    "$BUILD_DIR/${name}" || status=1
  done
  exit "$status"
else
  echo "[test.sh] No recognized project found in '$TARGET'."
  echo "Run scripts/new-service.sh first, or cd into your project dir."
  exit 1
fi
