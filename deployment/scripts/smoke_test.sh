#!/usr/bin/env bash
# Smoke test suite — runs against a live stack.
# Usage: BASE_URL=http://localhost:8000 ./smoke_test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local url="$2"
  local expected_status="${3:-200}"

  actual=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [[ "$actual" == "$expected_status" ]]; then
    echo "  PASS  $desc ($actual)"
    ((PASS++))
  else
    echo "  FAIL  $desc — expected $expected_status, got $actual"
    ((FAIL++))
  fi
}

echo "Smoke tests → $BASE_URL"
echo ""

check "Health live"            "$BASE_URL/health/live"
check "Health ready"           "$BASE_URL/health/ready"
check "OpenAPI schema"         "$BASE_URL/openapi.json"
check "Tickets list (no auth)" "$BASE_URL/api/v1/tickets" "401"
check "Knowledge list (no auth)" "$BASE_URL/api/v1/knowledge" "401"

echo ""
if [[ "$FAIL" -gt 0 ]]; then
  echo "SMOKE FAILED: $PASS passed, $FAIL failed"
  exit 1
else
  echo "SMOKE PASSED: $PASS checks"
fi
