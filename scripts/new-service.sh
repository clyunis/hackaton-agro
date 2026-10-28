#!/usr/bin/env bash
# Scaffolds a minimal, testable project skeleton following the team's
# code conventions (see .claude/skills/dev-cycle/SKILL.md): OOP,
# descriptive names, doc-comment per function, snake_case variables.
set -euo pipefail

usage() {
  echo "Usage: $0 <python|node|go|java|cpp> [target-dir]"
  echo "Scaffolds a minimal, testable project skeleton for the hackathon."
  exit 1
}

[ $# -ge 1 ] || usage
LANG_CHOICE="$1"
TARGET="${2:-app}"

if [ -e "$TARGET" ]; then
  echo "Error: '$TARGET' already exists. Pick another target dir or remove it first." >&2
  exit 1
fi

mkdir -p "$TARGET"

case "$LANG_CHOICE" in
  python)
    mkdir -p "$TARGET/tests"
    cat > "$TARGET/requirements.txt" <<'EOF'
fastapi
uvicorn
pytest
httpx
EOF
    cat > "$TARGET/health_service.py" <<'EOF'
class HealthService:
    """Encapsulates the service's health-check logic."""

    def check_status(self) -> dict:
        """Return a status payload indicating the service is reachable."""
        return {"status": "ok"}
EOF
    cat > "$TARGET/main.py" <<'EOF'
from fastapi import FastAPI

from health_service import HealthService

app = FastAPI()
health_service = HealthService()


@app.get("/health")
def get_health() -> dict:
    """Return the current health status of the service."""
    return health_service.check_status()
EOF
    cat > "$TARGET/tests/test_health.py" <<'EOF'
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_health_returns_ok():
    """GET /health should respond with a 200 and an ok status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
EOF
    echo "Python/FastAPI skeleton created in $TARGET/"
    echo "Next: cd $TARGET && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    ;;
  node)
    mkdir -p "$TARGET/test"
    cat > "$TARGET/package.json" <<EOF
{
  "name": "$(basename "$TARGET")",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "start": "node index.js",
    "test": "node --test"
  }
}
EOF
    cat > "$TARGET/index.js" <<'EOF'
import http from "node:http";

/** Encapsulates the service's health-check logic. */
class HealthService {
  /**
   * Returns a status payload indicating the service is reachable.
   * @returns {{status: string}}
   */
  checkStatus() {
    return { status: "ok" };
  }
}

/**
 * Builds the HTTP server, wiring routes to their handlers.
 * @returns {http.Server}
 */
export function createServer() {
  const health_service = new HealthService();
  return http.createServer((req, res) => {
    if (req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(health_service.checkStatus()));
      return;
    }
    res.writeHead(404);
    res.end();
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  createServer().listen(3000, () => console.log("listening on :3000"));
}
EOF
    cat > "$TARGET/test/health.test.js" <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "../index.js";

/** Verifies GET /health responds with 200 and an ok status payload. */
test("GET /health returns ok", async () => {
  const server = createServer().listen(0);
  const { port } = server.address();
  const res = await fetch(`http://localhost:${port}/health`);
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.deepEqual(body, { status: "ok" });
  server.close();
});
EOF
    echo "Node skeleton created in $TARGET/"
    echo "Next: cd $TARGET && npm test"
    ;;
  go)
    MODNAME="$(basename "$TARGET")"
    (cd "$TARGET" && go mod init "$MODNAME" >/dev/null 2>&1 || true)
    cat > "$TARGET/main.go" <<'EOF'
package main

import (
	"encoding/json"
	"log"
	"net/http"
)

// HealthService encapsulates the service's health-check logic.
type HealthService struct{}

// CheckStatus returns a status payload indicating the service is reachable.
func (health_service HealthService) CheckStatus() map[string]string {
	return map[string]string{"status": "ok"}
}

// healthHandler writes the health-check response for GET /health.
func healthHandler(w http.ResponseWriter, r *http.Request) {
	health_service := HealthService{}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health_service.CheckStatus())
}

func main() {
	http.HandleFunc("/health", healthHandler)
	log.Fatal(http.ListenAndServe(":3000", nil))
}
EOF
    cat > "$TARGET/main_test.go" <<'EOF'
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestHealthHandler verifies that GET /health responds with 200 OK.
func TestHealthHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	healthHandler(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}
EOF
    echo "Go skeleton created in $TARGET/"
    echo "Next: cd $TARGET && go test ./..."
    ;;
  java)
    mkdir -p "$TARGET/src/main/java" "$TARGET/src/test/java"
    cat > "$TARGET/src/main/java/HealthService.java" <<'EOF'
/**
 * Encapsulates the service's health-check logic.
 */
public class HealthService {
    /**
     * Returns a status payload indicating the service is reachable.
     */
    public String checkStatus() {
        return "ok";
    }
}
EOF
    cat > "$TARGET/src/main/java/App.java" <<'EOF'
/**
 * Entry point for the service.
 */
public class App {
    public static void main(String[] args) {
        HealthService health_service = new HealthService();
        System.out.println(health_service.checkStatus());
    }
}
EOF
    cat > "$TARGET/src/test/java/AppTest.java" <<'EOF'
/**
 * Verifies HealthService returns the expected status.
 */
public class AppTest {
    public static void main(String[] args) {
        HealthService health_service = new HealthService();
        if (!"ok".equals(health_service.checkStatus())) {
            throw new AssertionError("expected ok");
        }
        System.out.println("AppTest passed");
    }
}
EOF
    echo "Java skeleton created in $TARGET/ (plain javac/java, no build tool wired up)."
    echo "Next: ./scripts/test.sh $TARGET"
    ;;
  cpp)
    mkdir -p "$TARGET/src" "$TARGET/tests"
    cat > "$TARGET/src/health_service.hpp" <<'EOF'
#pragma once
#include <string>

/**
 * Encapsulates the service's health-check logic.
 */
class HealthService {
public:
    /**
     * Returns a status payload indicating the service is reachable.
     */
    std::string check_status() const { return "ok"; }
};
EOF
    cat > "$TARGET/src/main.cpp" <<'EOF'
#include <iostream>
#include "health_service.hpp"

int main() {
    HealthService health_service;
    std::cout << health_service.check_status() << std::endl;
    return 0;
}
EOF
    cat > "$TARGET/tests/test_health.cpp" <<'EOF'
#include <cassert>
#include <iostream>
#include "../src/health_service.hpp"

int main() {
    HealthService health_service;
    assert(health_service.check_status() == "ok");
    std::cout << "test_health passed" << std::endl;
    return 0;
}
EOF
    echo "C++ skeleton created in $TARGET/ (plain g++, no build system wired up)."
    echo "Next: ./scripts/test.sh $TARGET"
    ;;
  *)
    usage
    ;;
esac
