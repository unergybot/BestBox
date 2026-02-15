#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT_DIR/config/customer.yaml" ]]; then
  cp "$ROOT_DIR/config/customer.yaml.example" "$ROOT_DIR/config/customer.yaml"
  echo "Created config/customer.yaml from template."
else
  echo "config/customer.yaml already exists."
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  if [[ -f "$ROOT_DIR/.env.example" ]]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    echo "Created .env from .env.example."
  else
    echo "No .env.example found; create .env manually."
  fi
fi

echo "Running basic health checks..."
"$ROOT_DIR/scripts/health-check.sh" || true

echo "Customer setup bootstrap complete."
