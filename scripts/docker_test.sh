#!/usr/bin/env bash
set -eo pipefail

# PAYFLOW AI - Docker Stack Verification & Test Runner
# Verifies container health, API routing, MongoDB integration, test suites, and smoke test.

echo "=========================================================="
echo "  PAYFLOW AI - Docker End-to-End Test Suite"
echo "=========================================================="

PASSED=0
FAILED=0

record_result() {
  local name="$1"
  local status="$2"
  if [ "$status" -eq 0 ]; then
    echo "  [PASS] $name"
    PASSED=$((PASSED + 1))
  else
    echo "  [FAIL] $name"
    FAILED=$((FAILED + 1))
  fi
}

# 1. Wait for containers to be healthy
echo ""
echo "Phase 1: Verifying Container Health..."
for service in mongodb backend frontend; do
  echo "  Checking health of $service..."
  RETRIES=30
  until [ "$RETRIES" -le 0 ]; do
    HEALTH=$(docker compose ps "$service" --format "{{.Health}}" 2>/dev/null || echo "")
    if [[ "$HEALTH" == *"healthy"* ]]; then
      echo "  -> $service is healthy"
      break
    fi
    sleep 2
    RETRIES=$((RETRIES - 1))
  done
  if [ "$RETRIES" -le 0 ]; then
    echo "  -> Timeout waiting for $service to become healthy"
    record_result "Container health ($service)" 1
  else
    record_result "Container health ($service)" 0
  fi
done

# 2. Test direct backend HTTP healthcheck
echo ""
echo "Phase 2: Direct Backend Healthcheck (port 8000)..."
BACKEND_HEALTH=$(curl -s http://localhost:8000/health || echo "{}")
if echo "$BACKEND_HEALTH" | grep -q '"status":"healthy"'; then
  record_result "Direct Backend Health (http://localhost:8000/health)" 0
else
  echo "  Response: $BACKEND_HEALTH"
  record_result "Direct Backend Health (http://localhost:8000/health)" 1
fi

# 3. Test frontend HTTP server
echo ""
echo "Phase 3: Frontend Web Server (port 3000)..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ || echo "000")
if [ "$FRONTEND_STATUS" -eq 200 ]; then
  record_result "Frontend HTTP 200 (http://localhost:3000/)" 0
else
  echo "  HTTP status code: $FRONTEND_STATUS"
  record_result "Frontend HTTP 200 (http://localhost:3000/)" 1
fi

# 4. Test frontend Nginx reverse-proxy to backend
echo ""
echo "Phase 4: Frontend Nginx API Proxy (/health via port 3000)..."
PROXIED_HEALTH=$(curl -s http://localhost:3000/health || echo "{}")
if echo "$PROXIED_HEALTH" | grep -q '"status":"healthy"'; then
  record_result "Nginx Reverse Proxy (http://localhost:3000/health)" 0
else
  echo "  Response: $PROXIED_HEALTH"
  record_result "Nginx Reverse Proxy (http://localhost:3000/health)" 1
fi

# 5. Run full pytest suite inside backend container
echo ""
echo "Phase 5: Executing Pytest Test Suite inside Backend Container..."
if docker compose exec -T backend pytest tests/ -q; then
  record_result "Pytest Suite (156 tests inside Docker)" 0
else
  record_result "Pytest Suite inside Docker" 1
fi

# 6. Run demo data seeding inside backend container
echo ""
echo "Phase 6: Executing Demo Seed Script against Containerized MongoDB..."
if docker compose exec -T backend python scripts/seed_demo_data.py; then
  record_result "MongoDB Demo Seeding inside Docker" 0
else
  record_result "MongoDB Demo Seeding inside Docker" 1
fi

# 7. Run automated 10-phase smoke test against running container stack
echo ""
echo "Phase 7: Executing Automated 10-Phase Production Smoke Test..."
if docker compose exec -T -e BASE_URL="http://localhost:8000" backend python -u scripts/smoke_test.py; then
  record_result "10-Phase Smoke Test inside Docker" 0
else
  record_result "10-Phase Smoke Test inside Docker" 1
fi

echo ""
echo "=========================================================="
echo "  Docker Test Summary: $PASSED passed, $FAILED failed"
echo "=========================================================="

if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
exit 0
