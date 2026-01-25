#!/bin/bash
# BestBox Observability Stack Deployment Script
# Automates the deployment of OpenTelemetry, Prometheus, Jaeger, and Grafana

set -e

echo "🔧 BestBox Observability Stack Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}⚠️  PostgreSQL client not found. Install with: sudo apt install postgresql-client${NC}"
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"
echo ""

# Step 2: Generate secure credentials
echo "🔐 Step 2: Generating secure credentials..."

if [ ! -f .env.observability ]; then
    GRAFANA_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

    cat > .env.observability << EOF
# Grafana Admin Credentials
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASS}

# PostgreSQL Credentials (should match your existing setup)
POSTGRES_USER=bestbox
POSTGRES_PASSWORD=bestbox

# Admin Panel Password
ADMIN_PANEL_PASSWORD=${GRAFANA_PASS}

# Retention Policies
PROMETHEUS_RETENTION_DAYS=30
JAEGER_RETENTION_DAYS=7

# Optional: Alert notification endpoints
ALERT_EMAIL=
ALERT_SLACK_WEBHOOK=
EOF

    echo -e "${GREEN}✅ Generated .env.observability with secure passwords${NC}"
    echo -e "${YELLOW}⚠️  SAVE THIS PASSWORD: ${GRAFANA_PASS}${NC}"
else
    echo -e "${YELLOW}⚠️  .env.observability already exists, skipping generation${NC}"
    source .env.observability
fi
echo ""

# Step 3: Database migration
echo "🗄️  Step 3: Running database migrations..."

if [ -f migrations/003_observability_tables.sql ]; then
    source .env.observability

    PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -U ${POSTGRES_USER} -d bestbox \
        -f migrations/003_observability_tables.sql \
        2>/dev/null && echo -e "${GREEN}✅ Database schema updated${NC}" || \
        echo -e "${YELLOW}⚠️  Migration may have already run (this is OK)${NC}"
else
    echo -e "${RED}❌ migrations/003_observability_tables.sql not found${NC}"
    exit 1
fi
echo ""

# Step 4: Install Python dependencies
echo "🐍 Step 4: Installing Python observability libraries..."

if [ -f ~/BestBox/venv/bin/activate ]; then
    source ~/BestBox/venv/bin/activate

    pip install -q opentelemetry-api \
                   opentelemetry-sdk \
                   opentelemetry-exporter-otlp-proto-grpc \
                   openinference-instrumentation-langchain \
                   prometheus-client \
                   asyncpg

    echo -e "${GREEN}✅ Python dependencies installed${NC}"
else
    echo -e "${RED}❌ Virtual environment not found at ~/BestBox/venv${NC}"
    exit 1
fi
echo ""

# Step 5: Start observability services
echo "🚀 Step 5: Starting observability stack..."

docker compose up -d otel-collector jaeger prometheus grafana

echo -e "${GREEN}✅ Services started${NC}"
echo ""

# Step 6: Wait for services to be ready
echo "⏳ Step 6: Waiting for services to initialize (30 seconds)..."
sleep 30

# Step 7: Verify services
echo "🔍 Step 7: Verifying service health..."

services=(
  "http://localhost:4318|OpenTelemetry Collector"
  "http://localhost:16686|Jaeger UI"
  "http://localhost:9090|Prometheus"
  "http://localhost:3001|Grafana"
)

all_healthy=true
for service in "${services[@]}"; do
  IFS='|' read -r url name <<< "$service"

  if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -qE "200|302|401"; then
    echo -e "  ${GREEN}✅ $name is up${NC}"
  else
    echo -e "  ${RED}❌ $name failed to start${NC}"
    all_healthy=false
  fi
done
echo ""

# Step 8: Display summary
if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}║     🎉 Observability Stack Successfully Deployed! 🎉     ║${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "📊 Access URLs:"
    echo "  • Grafana Dashboard:  http://localhost:3001"
    echo "    Username: admin"
    echo "    Password: ${GRAFANA_ADMIN_PASSWORD}"
    echo ""
    echo "  • Jaeger Traces:      http://localhost:16686"
    echo "  • Prometheus:         http://localhost:9090"
    echo "  • Admin Panel:        http://localhost:3000/admin"
    echo ""
    echo "⚠️  IMPORTANT: Save your Grafana password securely!"
    echo ""
    echo "📝 Next Steps:"
    echo "  1. Restart Agent API to enable instrumentation:"
    echo "     ./scripts/start-agent-api.sh"
    echo ""
    echo "  2. Test the system:"
    echo "     - Visit http://localhost:3000 and send a message"
    echo "     - Click thumbs up/down to test feedback"
    echo "     - View metrics at http://localhost:3001"
    echo ""
    echo "  3. Review the Observability Playbook:"
    echo "     docs/observability_playbook.md"
    echo ""
else
    echo -e "${RED}❌ Some services failed to start. Check logs with:${NC}"
    echo "   docker compose logs otel-collector"
    echo "   docker compose logs grafana"
    echo "   docker compose logs prometheus"
    echo "   docker compose logs jaeger"
    exit 1
fi
