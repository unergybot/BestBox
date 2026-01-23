#!/bin/bash
# ERPNext Initialization Script
# Wraps commands to run inside the Docker container via docker compose exec

set -e

SITE_NAME="${SITE_NAME:-bestbox.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
SERVICE_NAME="erpnext"

echo "=== ERPNext Site Initialization ==="
echo "Target Service: $SERVICE_NAME"
echo ""

# Check if service is up
if ! docker compose ps --services --filter "status=running" | grep -q "^$SERVICE_NAME$"; then
    echo "ERROR: Service '$SERVICE_NAME' is not running."
    echo "Please run: docker compose up -d"
    exit 1
fi

echo "[1/4] Checking Database Connectivity (from inside container)..."
# Check DB connection from INSIDE the container where 'mariadb' hostname exists
docker compose exec -u frappe $SERVICE_NAME bash -c "
    for i in {1..30}; do
        if mysqladmin ping -h mariadb -u root -padmin --silent; then
            echo '  MariaDB is ready!'
            exit 0
        fi
        echo '  Waiting for MariaDB...'
        sleep 2
    done
    echo 'ERROR: MariaDB not reachable'
    exit 1
"

echo "[2/4] Creating ERPNext site (this may take a minute)..."
docker compose exec -u frappe $SERVICE_NAME bash -c "
    cd /home/frappe/frappe-bench
    
    # Configure Redis to use the docker service 'redis' instead of localhost
    echo '  Configuring Redis connection...'
    bench set-config -g redis_cache redis://redis:6379
    bench set-config -g redis_queue redis://redis:6379
    bench set-config -g redis_socketio redis://redis:6379

    if [ ! -f sites/$SITE_NAME/site_config.json ]; then
        echo '  Creating new site $SITE_NAME...'
        bench new-site $SITE_NAME \
            --force \
            --mariadb-root-password admin \
            --admin-password $ADMIN_PASSWORD \
            --db-host mariadb \
            --mariadb-user-host-login-scope '%'
        
        echo '  Installing ERPNext app...'
        bench --site $SITE_NAME install-app erpnext
        echo '  Site created successfully!'
    else
        echo '  Site $SITE_NAME already exists.'
    fi
"

echo "[3/4] Configuring Site..."
docker compose exec -u frappe $SERVICE_NAME bash -c "
    cd /home/frappe/frappe-bench
    bench use $SITE_NAME
    bench --site $SITE_NAME set-config developer_mode 1
    bench --site $SITE_NAME set-config allow_cors '*'
    # Clean up any ready-made setup wizard
    bench --site $SITE_NAME set-config naming_series_prefix 'bestbox-' || true
"

echo "[4/4] Restarting ERPNext..."
docker compose restart $SERVICE_NAME

echo ""
echo "=== ERPNext Ready ==="
echo "URL: http://localhost:8002"
echo "Username: Administrator"
echo "Password: $ADMIN_PASSWORD"
echo ""
echo "To seed demo data, run: python scripts/seed_demo_data.py"
