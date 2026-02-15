#!/bin/bash
# BestBox Demo Device Quick Setup Script
# This script automates the setup of demo data on a new BestBox device

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "🚀 BestBox Demo Device Setup"
echo "=========================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ .env file not found!"
    echo "   Please create .env with ERPNext credentials:"
    echo "   cp .env.example .env"
    echo "   # Then edit .env with your settings"
    exit 1
fi

# Load environment
source "$PROJECT_ROOT/.env"

# Check ERPNext credentials
if [ -z "$ERPNEXT_API_KEY" ] || [ -z "$ERPNEXT_API_SECRET" ]; then
    echo "❌ ERPNext credentials not configured in .env"
    echo "   Please set ERPNEXT_API_KEY and ERPNEXT_API_SECRET"
    exit 1
fi

echo "   ✓ .env configured"

# Check if ERPNext is accessible
ERPNEXT_URL="${ERPNEXT_URL:-http://localhost:8080}"
echo "   Checking ERPNext at $ERPNEXT_URL..."

if ! curl -s -f "$ERPNEXT_URL/api/method/ping" > /dev/null 2>&1; then
    echo "   ⚠️  ERPNext not accessible at $ERPNEXT_URL"
    echo "   Continuing anyway (will use fallback mode)..."
else
    echo "   ✓ ERPNext is accessible"
fi

echo ""

# Dry run first
echo "🧪 Running dry run to preview changes..."
echo ""
python3 "$SCRIPT_DIR/seed_erpnext_demo_data.py" --dry-run

echo ""
echo "=========================================="
read -p "Continue with actual seeding? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Actual seeding
echo ""
echo "🌱 Seeding demo data..."
echo ""
python3 "$SCRIPT_DIR/seed_erpnext_demo_data.py"

echo ""
echo "=========================================="
echo "✅ Demo device setup complete!"
echo "=========================================="
echo ""
echo "📚 Next steps:"
echo "   1. Start services: ./start-all-services.sh"
echo "   2. Access ERPNext: $ERPNEXT_URL"
echo "   3. Access frontend: http://localhost:3000"
echo "   4. Check logs: tail -f logs/agent_api.log"
echo ""
echo "📖 Documentation:"
echo "   - Demo data guide: docs/DEMO_DATA_SETUP.md"
echo "   - Project overview: CLAUDE.md"
echo ""
