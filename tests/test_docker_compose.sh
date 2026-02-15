#!/bin/bash
# Integration tests for compose base + overlays

set -e

TESTS_PASSED=0
TESTS_FAILED=0
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

pass() {
  echo "✅ PASS: $1"
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
  echo "❌ FAIL: $1"
  TESTS_FAILED=$((TESTS_FAILED + 1))
}

if docker compose -f docker-compose.yml config --quiet; then pass "Base compose syntax"; else fail "Base compose syntax"; fi
if docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet; then pass "ROCm overlay syntax"; else fail "ROCm overlay syntax"; fi
if docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet; then pass "CUDA overlay syntax"; else fail "CUDA overlay syntax"; fi

rocm_config="$(docker compose -f docker-compose.yml -f docker-compose.rocm.yml config)"
cuda_config="$(docker compose -f docker-compose.yml -f docker-compose.cuda.yml config)"

echo "$rocm_config" | grep -q "/dev/kfd" && pass "ROCm devices present" || fail "ROCm devices present"
echo "$cuda_config" | grep -q "runtime: nvidia" && pass "CUDA runtime present" || fail "CUDA runtime present"

echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
[ "$TESTS_FAILED" -eq 0 ]
