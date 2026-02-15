#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="${1:-$ROOT_DIR/data/customer_docs}"

if [[ ! -d "$DOCS_DIR" ]]; then
  echo "Customer docs directory not found: $DOCS_DIR"
  echo "Usage: scripts/seed-customer-kb.sh [docs_dir]"
  exit 1
fi

echo "Seeding knowledge base from: $DOCS_DIR"
BESTBOX_DOCS_PATH="$DOCS_DIR" python "$ROOT_DIR/scripts/seed_knowledge_base.py"
