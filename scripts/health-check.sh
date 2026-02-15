#!/usr/bin/env bash
set -euo pipefail

check() {
  local name="$1"
  local url="$2"
  if curl -fsS "$url" >/dev/null; then
    echo "[OK] $name"
  else
    echo "[FAIL] $name ($url)"
    return 1
  fi
}

status=0
check "Agent API" "http://localhost:8000/health" || status=1
check "Embeddings" "http://localhost:8081/health" || status=1
check "Qdrant" "http://localhost:6333/healthz" || status=1
check "Prometheus" "http://localhost:9090/-/healthy" || status=1

if [[ $status -eq 0 ]]; then
  echo "All core services are healthy."
else
  echo "One or more services failed health checks."
fi

exit $status
