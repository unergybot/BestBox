#!/bin/bash
# Unit tests for scripts/detect-gpu.sh

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

source scripts/detect-gpu.sh

test_env_var_priority() {
  export BESTBOX_GPU_BACKEND=cuda
  result="$(detect_gpu)"
  unset BESTBOX_GPU_BACKEND
  [ "$result" = "cuda" ] && pass "Env var priority" || fail "Env var priority"
}

test_config_file_priority() {
  unset BESTBOX_GPU_BACKEND
  mkdir -p .bestbox
  echo "gpu_backend=rocm" > .bestbox/config
  result="$(detect_gpu)"
  rm -f .bestbox/config
  [ "$result" = "rocm" ] && pass "Config file priority" || fail "Config file priority"
}

test_config_spaces() {
  unset BESTBOX_GPU_BACKEND
  mkdir -p .bestbox
  echo "gpu_backend = cuda  # comment" > .bestbox/config
  result="$(detect_gpu)"
  rm -f .bestbox/config
  [ "$result" = "cuda" ] && pass "Config parser with spaces" || fail "Config parser with spaces"
}

test_auto_detect() {
  unset BESTBOX_GPU_BACKEND
  rm -f .bestbox/config
  result="$(detect_gpu)"
  [[ "$result" =~ ^(cuda|rocm|cpu)$ ]] && pass "Auto-detect valid backend" || fail "Auto-detect valid backend"
}

test_invalid_validation() {
  if validate_backend invalid >/dev/null 2>&1; then
    fail "Invalid backend rejected"
  else
    pass "Invalid backend rejected"
  fi
}

test_env_var_priority
test_config_file_priority
test_config_spaces
test_auto_detect
test_invalid_validation

echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
[ "$TESTS_FAILED" -eq 0 ]
