# ERPNext Integration Design

**Date:** 2026-01-27
**Status:** Design Complete - Ready for Implementation
**Author:** Claude + unergy

## Overview

This design document describes the integration of ERPNext (running locally in Docker) with the BestBox AI agent system. The integration replaces static demo data with live ERPNext data while maintaining automatic fallback for reliability.

## Goals

1. **Full Parity**: All current ERP tools should work with real ERPNext data
2. **Automatic Fallback**: Seamless degradation to demo data if ERPNext unavailable
3. **Local Deployment**: ERPNext runs in docker-compose alongside other services
4. **Gradual Seeding**: Demo data populated incrementally via scripts
5. **Zero Breaking Changes**: Existing agent behavior unchanged when ERPNext unavailable

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Agent Layer                                                 │
│  ┌──────────────┐                                          │
│  │ ERP Agent    │                                          │
│  └──────┬───────┘                                          │
│         │ calls                                            │
│         ▼                                                  │
│  ┌──────────────────────────────────────┐                 │
│  │ ERP Tools (tools/erp_tools.py)       │                 │
│  │  - get_purchase_orders()             │                 │
│  │  - get_inventory_levels()            │                 │
│  │  - get_financial_summary()           │                 │
│  │  - get_vendor_price_trends()         │                 │
│  │  - get_procurement_summary()         │                 │
│  │  - get_top_vendors()                 │                 │
│  └──────┬───────────────────────────────┘                 │
│         │                                                  │
└─────────┼──────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ ERPNext Client Layer (NEW)                                  │
│  ┌──────────────────────────────────────┐                  │
│  │ services/erpnext_client.py           │                  │
│  │                                      │                  │
│  │  class ERPNextClient:                │                  │
│  │    • is_available() → bool           │                  │
│  │    • get_doc(doctype, name)          │                  │
│  │    • get_list(doctype, filters)      │                  │
│  │    • get_value(doctype, field)       │                  │
│  │    • run_query(sql)                  │                  │
│  │    • get_report(report_name)         │                  │
│  └──────┬───────────────────────────────┘                  │
│         │                                                   │
└─────────┼───────────────────────────────────────────────────┘
          │
          ▼ HTTP REST API
┌─────────────────────────────────────────────────────────────┐
│ ERPNext Instance (Docker)                                   │
│  - URL: http://localhost:8002                              │
│  - Site: bestbox.local                                     │
│  - API Key auth                                            │
│                                                             │
│  Doctypes Used:                                            │
│   • Purchase Order                                         │
│   • Supplier (Vendor)                                      │
│   • Item                                                   │
│   • Stock Ledger Entry                                     │
│   • Bin (warehouse stock)                                  │
│   • GL Entry                                               │
│   • Account                                                │
│   • Cost Center                                            │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. ERPNext Client (services/erpnext_client.py)

**Purpose**: Centralized client for all ERPNext API interactions with error handling and caching.

**Key Features**:
- API Key authentication (no user/password)
- Connection pooling via `requests.Session()`
- Availability caching (60-second TTL) to avoid health check overhead
- Automatic timeout handling (2s for health, 5-10s for data queries)
- Graceful error handling (returns None on failure, allows tools to fallback)

**Configuration** (environment variables):
```bash
ERPNEXT_URL=http://localhost:8002  # Default
ERPNEXT_API_KEY=<generated-key>
ERPNEXT_API_SECRET=<generated-secret>
ERPNEXT_SITE=bestbox.local  # Default
```

**Core Methods**:

```python
class ERPNextClient:
    def __init__(self, url, api_key, api_secret, site):
        """Initialize with credentials and setup session."""

    def is_available(self) -> bool:
        """
        Check if ERPNext is reachable.
        Cached for 60s to avoid constant health checks.
        Returns False on timeout/error.
        """

    def get_list(self, doctype, fields=None, filters=None,
                 limit=20, order_by=None) -> List[Dict]:
        """
        Fetch list of documents.
        Maps to: GET /api/resource/{doctype}

        Example:
            client.get_list("Purchase Order",
                          filters={"supplier": "SUP-001"},
                          fields=["name", "grand_total", "status"])
        """

    def get_doc(self, doctype, name) -> Dict:
        """
        Fetch single document with all fields.
        Maps to: GET /api/resource/{doctype}/{name}

        Example:
            client.get_doc("Purchase Order", "PO-2025-001")
        """

    def get_value(self, doctype, filters, fieldname) -> Any:
        """
        Get single field value without fetching full doc.
        Useful for counts, sums, etc.
        """

    def run_query(self, query: str) -> List[Dict]:
        """
        Execute custom SQL query via ERPNext's query API.
        USE SPARINGLY - prefer get_list/get_doc for standard queries.

        Maps to: POST /api/method/frappe.client.get_list
        with custom SQL in filters.
        """

    def get_report(self, report_name: str, filters: Dict = None) -> Dict:
        """
        Run ERPNext Report and return results.
        Useful for complex aggregations (P&L, Balance Sheet, etc.)

        Example:
            client.get_report("Purchase Order Trends",
                            filters={"from_date": "2025-10-01"})
        """
```

**Error Handling Pattern**:
```python
def get_list(self, doctype, **kwargs):
    try:
        resp = self.session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except (requests.RequestException, ValueError, KeyError):
        # Log error but don't raise - let tools fallback
        logger.warning(f"ERPNext API call failed for {doctype}")
        return None  # Tools check for None and use demo data
```

### 2. Modified ERP Tools (tools/erp_tools.py)

**Pattern**: Each tool function tries ERPNext first, falls back to demo data.

**Example - get_purchase_orders()**:

```python
from services.erpnext_client import ERPNextClient

# Singleton client instance
_erpnext_client = None

def get_erpnext_client() -> ERPNextClient:
    """Lazy-initialized ERPNext client."""
    global _erpnext_client
    if _erpnext_client is None:
        _erpnext_client = ERPNextClient()
    return _erpnext_client


@tool
def get_purchase_orders(
    vendor_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    quarter: Optional[str] = None
):
    """
    Retrieve purchase orders from ERPNext or demo data.

    Args:
        vendor_id: Supplier ID (e.g., "SUP-001" in ERPNext)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        status: PO status (Draft, Submitted, Completed, Cancelled)
        quarter: Financial quarter (Q3-2025, Q4-2025)

    Returns:
        Dict with count, total_amount, currency, orders list
    """
    client = get_erpnext_client()

    # Try ERPNext first
    if client.is_available():
        try:
            return _get_purchase_orders_from_erpnext(
                client, vendor_id, start_date, end_date, status, quarter
            )
        except Exception as e:
            logger.warning(f"ERPNext query failed: {e}, falling back to demo data")

    # Fallback to demo data
    return _get_purchase_orders_from_demo(
        vendor_id, start_date, end_date, status, quarter
    )


def _get_purchase_orders_from_erpnext(client, vendor_id, start_date, end_date, status, quarter):
    """Query ERPNext for Purchase Orders."""
    filters = {}

    if vendor_id:
        filters["supplier"] = vendor_id

    if status:
        filters["status"] = status

    # Handle date filtering
    if quarter:
        # Convert Q4-2025 to date range
        q_num, year = quarter.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        start_date = f"{year}-{q_start_month:02d}-01"
        # End date = last day of quarter (approximate with next quarter start - 1 day)
        if q_num < 4:
            end_date = f"{year}-{q_end_month + 1:02d}-01"
        else:
            end_date = f"{year + 1}-01-01"

    if start_date:
        filters["transaction_date"] = [">=", start_date]
    if end_date:
        if "transaction_date" in filters:
            # Combine with existing filter
            filters["transaction_date"] = [
                [">=", start_date],
                ["<=", end_date]
            ]
        else:
            filters["transaction_date"] = ["<=", end_date]

    # Fetch from ERPNext
    orders = client.get_list(
        "Purchase Order",
        fields=["name", "supplier", "supplier_name", "grand_total",
                "status", "transaction_date", "currency"],
        filters=filters,
        limit=100,
        order_by="transaction_date desc"
    )

    if orders is None:
        raise Exception("ERPNext returned None")

    # Transform to match demo data format
    transformed = []
    for po in orders:
        transformed.append({
            "id": po.get("name"),
            "vendor_id": po.get("supplier"),
            "vendor_name": po.get("supplier_name"),
            "total": po.get("grand_total", 0),
            "status": po.get("status"),
            "date": po.get("transaction_date"),
            "currency": po.get("currency", "CNY")
        })

    total_amount = sum(o["total"] for o in transformed)

    return {
        "count": len(transformed),
        "total_amount": round(total_amount, 2),
        "currency": transformed[0]["currency"] if transformed else "CNY",
        "orders": transformed[:20],  # Limit to 20
        "source": "erpnext"  # NEW: indicates data source
    }


def _get_purchase_orders_from_demo(vendor_id, start_date, end_date, status, quarter):
    """Existing demo data logic - UNCHANGED."""
    data = get_demo_data()
    # ... existing implementation ...
    result = {
        # ... existing return ...
        "source": "demo"  # NEW: indicates fallback
    }
    return result
```

**Key Changes to All Tools**:
1. Add `get_erpnext_client()` lazy singleton
2. Split each tool into three functions:
   - Main tool function (tries ERPNext, falls back)
   - `_get_X_from_erpnext()` - ERPNext implementation
   - `_get_X_from_demo()` - Existing demo logic (refactored but unchanged)
3. Add `"source": "erpnext"|"demo"` field to all responses (useful for debugging)

### 3. Tool-to-Doctype Mapping

| Tool Function | ERPNext Doctype(s) | Key Fields |
|---------------|-------------------|------------|
| `get_purchase_orders()` | Purchase Order | name, supplier, grand_total, status, transaction_date, items |
| `get_inventory_levels()` | Bin, Item | item_code, warehouse, actual_qty, item_name, item_group, reorder_level |
| `get_financial_summary()` | GL Entry, Account | account, debit, credit, posting_date, cost_center |
| `get_vendor_price_trends()` | Purchase Order Item | item_code, supplier, rate, transaction_date |
| `get_procurement_summary()` | Purchase Order | supplier, grand_total, transaction_date |
| `get_top_vendors()` | Purchase Order | supplier, supplier_name, grand_total |

### 4. Demo Data Seeding Scripts

**scripts/seed_erpnext_basic.py** - Master data (run first):
```python
"""
Seed basic master data into ERPNext.
Creates: Suppliers, Items, Warehouses, Accounts, Cost Centers
"""
import requests
from typing import Dict

ERPNEXT_URL = "http://localhost:8002"
API_KEY = os.getenv("ERPNEXT_API_KEY")
API_SECRET = os.getenv("ERPNEXT_API_SECRET")

def create_doc(doctype: str, data: Dict):
    """Create document in ERPNext."""
    resp = requests.post(
        f"{ERPNEXT_URL}/api/resource/{doctype}",
        json=data,
        headers={"Authorization": f"token {API_KEY}:{API_SECRET}"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["data"]

# Suppliers (from demo_data.json vendors)
suppliers = [
    {"supplier_name": "Shanghai Steel Co.", "supplier_group": "Raw Material",
     "supplier_type": "Company", "country": "China"},
    {"supplier_name": "Guangzhou Parts Ltd.", "supplier_group": "Components",
     "supplier_type": "Company", "country": "China"},
    # ... more from demo data
]

for supplier in suppliers:
    try:
        create_doc("Supplier", supplier)
        print(f"Created supplier: {supplier['supplier_name']}")
    except requests.HTTPError as e:
        if "already exists" in str(e):
            print(f"Supplier exists: {supplier['supplier_name']}")
        else:
            raise

# Items (from demo_data.json items)
items = [
    {"item_code": "RM-001", "item_name": "Steel Sheet 4mm",
     "item_group": "Raw Material", "stock_uom": "Kg",
     "is_stock_item": 1, "valuation_rate": 15.50},
    # ... more from demo data
]

for item in items:
    try:
        create_doc("Item", item)
        print(f"Created item: {item['item_code']}")
    except requests.HTTPError as e:
        if "already exists" in str(e):
            print(f"Item exists: {item['item_code']}")
        else:
            raise
```

**scripts/seed_erpnext_transactions.py** - Transactional data (run second):
```python
"""
Seed transaction data: Purchase Orders, Stock Entries
Requires: seed_erpnext_basic.py completed
"""
# Purchase Orders (from demo_data.json purchase_orders)
purchase_orders = [
    {
        "supplier": "SUP-001",  # Maps to Supplier.name
        "transaction_date": "2025-10-15",
        "items": [
            {"item_code": "RM-001", "qty": 100, "rate": 15.50},
            {"item_code": "RM-002", "qty": 50, "rate": 8.20}
        ],
        "status": "Draft"
    },
    # ... more from demo data
]

for po_data in purchase_orders:
    try:
        po = create_doc("Purchase Order", po_data)
        print(f"Created PO: {po['name']}")
    except Exception as e:
        print(f"Failed to create PO: {e}")
```

**scripts/seed_erpnext_financial.py** - Financial data (run third):
```python
"""
Seed financial data: GL Entries, Accounts
Requires: seed_erpnext_transactions.py completed
"""
# Create GL Entries for submitted Purchase Orders
# This is more complex - may require ERPNext's accounting APIs
# or submitting POs to auto-create GL entries
```

**Seeding Order**:
1. `python scripts/seed_erpnext_basic.py` - Master data
2. `python scripts/seed_erpnext_transactions.py` - POs, stock movements
3. `python scripts/seed_erpnext_financial.py` - GL entries (optional, complex)

**Idempotency**: All scripts check if data exists before creating (try/except on "already exists" error).

### 5. Startup Integration

**Updated docker-compose.yml** (already has ERPNext):
```yaml
services:
  erpnext:
    image: frappe/erpnext:v16
    # ... existing config ...
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/method/ping || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s  # ERPNext takes time to start
```

**Updated scripts/start-all-services.sh**:
```bash
#!/bin/bash
set -e

echo "=== Starting BestBox Infrastructure ==="

# 1. Start Docker services
docker compose up -d

# 2. Wait for ERPNext to be healthy
echo "Waiting for ERPNext..."
timeout 180 bash -c 'until curl -f http://localhost:8002/api/method/ping 2>/dev/null; do sleep 2; done'

# 3. Initialize ERPNext site (if needed)
if ! docker compose exec erpnext ls /home/frappe/frappe-bench/sites/bestbox.local/site_config.json >/dev/null 2>&1; then
    echo "Initializing ERPNext site..."
    ./scripts/init-erpnext.sh
fi

# 4. Check if demo data seeded
if ! docker compose exec erpnext bash -c 'mysql -h mariadb -u root -padmin erpnext -e "SELECT COUNT(*) FROM tabSupplier" | grep -v COUNT | grep -q [1-9]'; then
    echo "Seeding ERPNext demo data..."
    python scripts/seed_erpnext_basic.py
    python scripts/seed_erpnext_transactions.py
fi

# 5. Start LLM and agent services
./scripts/start-llm.sh &
sleep 5
./scripts/start-agent-api.sh &

# 6. Start frontend
cd frontend/copilot-demo && npm run dev &

echo "=== BestBox Ready ==="
echo "Frontend: http://localhost:3000"
echo "Agent API: http://localhost:8000"
echo "ERPNext: http://localhost:8002 (admin/admin)"
```

### 6. Environment Configuration

**New .env variables**:
```bash
# ERPNext Configuration
ERPNEXT_URL=http://localhost:8002
ERPNEXT_SITE=bestbox.local
ERPNEXT_API_KEY=<generate-in-ui>
ERPNEXT_API_SECRET=<generate-in-ui>

# Fallback behavior
ERPNEXT_TIMEOUT=5  # seconds
ERPNEXT_CACHE_TTL=60  # seconds
```

**Generating API Keys**:
1. Login to ERPNext: http://localhost:8002
2. Go to User → Administrator → API Access
3. Click "Generate Keys"
4. Copy API Key and Secret to `.env`

### 7. Testing Strategy

**Unit Tests** (`tests/test_erpnext_client.py`):
```python
import pytest
from services.erpnext_client import ERPNextClient

def test_client_availability_when_running(mock_erpnext_server):
    """Test is_available() returns True when ERPNext up."""
    client = ERPNextClient(url=mock_erpnext_server)
    assert client.is_available() is True

def test_client_availability_when_down():
    """Test is_available() returns False when ERPNext down."""
    client = ERPNextClient(url="http://localhost:9999")  # non-existent
    assert client.is_available() is False

def test_get_list_purchase_orders(mock_erpnext_server):
    """Test fetching purchase orders."""
    client = ERPNextClient(url=mock_erpnext_server)
    pos = client.get_list("Purchase Order", limit=10)
    assert isinstance(pos, list)
    assert len(pos) <= 10
```

**Integration Tests** (`tests/test_erp_tools_integration.py`):
```python
import pytest
from tools.erp_tools import get_purchase_orders

@pytest.mark.integration
def test_get_purchase_orders_from_erpnext(erpnext_running):
    """Test tool uses ERPNext when available."""
    result = get_purchase_orders()
    assert result["source"] == "erpnext"
    assert result["count"] >= 0

@pytest.mark.integration
def test_get_purchase_orders_fallback(erpnext_stopped):
    """Test tool falls back to demo data when ERPNext down."""
    result = get_purchase_orders()
    assert result["source"] == "demo"
    assert result["count"] > 0  # Demo data always has data
```

**Manual Testing Checklist**:
- [ ] Start ERPNext with `docker compose up -d`
- [ ] Run `scripts/init-erpnext.sh` successfully
- [ ] Seed demo data with `python scripts/seed_erpnext_basic.py`
- [ ] Generate API keys in ERPNext UI
- [ ] Set API keys in `.env`
- [ ] Start agent API: `./scripts/start-agent-api.sh`
- [ ] Query agent: "Show me purchase orders"
- [ ] Verify response includes `"source": "erpnext"`
- [ ] Stop ERPNext: `docker compose stop erpnext`
- [ ] Query agent again: "Show me purchase orders"
- [ ] Verify response includes `"source": "demo"` (fallback worked)

## Data Model Mapping

### Purchase Orders

| Demo Data Field | ERPNext Field | Notes |
|----------------|---------------|-------|
| `id` | `name` | Auto-generated (PO-2025-001) |
| `vendor_id` | `supplier` | Supplier.name reference |
| `vendor_name` | `supplier_name` | Fetched from Supplier doctype |
| `total` | `grand_total` | Includes taxes |
| `status` | `status` | Draft, Submitted, Completed, Cancelled |
| `date` | `transaction_date` | YYYY-MM-DD format |
| `items` | `items` (child table) | Purchase Order Item doctype |

### Inventory (Bins)

| Demo Data Field | ERPNext Field | Notes |
|----------------|---------------|-------|
| `sku` | `item_code` | Item.name reference |
| `name` | Item.`item_name` | Join from Item doctype |
| `group` | Item.`item_group` | Join from Item doctype |
| `quantity` | Bin.`actual_qty` | Current stock in warehouse |
| `reorder_point` | Item.`reorder_level` | From Item master |
| `warehouse` | Bin.`warehouse` | Warehouse.name reference |
| `alert` | computed | LOW_STOCK if actual_qty < reorder_level |

### Financials (GL Entries)

| Demo Data Field | ERPNext Field | Notes |
|----------------|---------------|-------|
| `revenue` | SUM(GL Entry.credit) WHERE account LIKE "Income%" | Aggregate query |
| `expenses` | SUM(GL Entry.debit) WHERE account LIKE "Expense%" | Aggregate query |
| `net_profit` | revenue - expenses | Computed |
| `period` | Filter on `posting_date` | Use Reports API for P&L |

**Note**: Financial data is complex in ERPNext. Prefer using built-in Reports (`get_report("Profit and Loss")`) over raw GL Entry queries.

## Error Handling & Edge Cases

### 1. ERPNext Not Running
- **Detection**: `is_available()` returns False (connection refused)
- **Behavior**: Tools immediately use demo data
- **User Experience**: No error message, seamless fallback

### 2. ERPNext Running But Not Initialized
- **Detection**: API returns 404 for site
- **Behavior**: Tools catch HTTP 404, fallback to demo
- **Admin Action**: Run `scripts/init-erpnext.sh`

### 3. API Key Invalid/Expired
- **Detection**: API returns 401/403
- **Behavior**: Log warning, fallback to demo data
- **Admin Action**: Regenerate keys in ERPNext UI, update `.env`

### 4. Slow ERPNext Response
- **Detection**: Request timeout (5-10s)
- **Behavior**: Catch timeout exception, fallback to demo
- **Mitigation**: Increase `ERPNEXT_TIMEOUT` in `.env` if network is slow

### 5. Empty ERPNext (No Data)
- **Detection**: API returns empty list `[]`
- **Behavior**: Return empty result (not fallback - this is valid)
- **Admin Action**: Run seeding scripts

### 6. Schema Mismatch (ERPNext Upgrade)
- **Detection**: KeyError when accessing expected fields
- **Behavior**: Catch KeyError, log warning, fallback
- **Mitigation**: Update field mappings in client code

## Performance Considerations

### 1. Availability Caching
- **Problem**: Checking `is_available()` on every tool call is expensive (network roundtrip)
- **Solution**: Cache availability for 60 seconds
- **Trade-off**: Takes up to 60s to detect ERPNext coming online/offline

### 2. Connection Pooling
- **Problem**: Creating new HTTP connection per API call is slow
- **Solution**: Use `requests.Session()` for connection reuse
- **Benefit**: ~50ms latency reduction per call after first request

### 3. Query Optimization
- **Problem**: Fetching full documents when only summary needed
- **Solution**: Use `fields` parameter to fetch only required fields
- **Example**: `get_list("Purchase Order", fields=["name", "grand_total"])` instead of `["*"]`

### 4. Pagination
- **Problem**: Large result sets (1000+ POs) slow down response
- **Solution**: Always use `limit` parameter (default 20, max 100)
- **Trade-off**: May not show all data, but agent can call multiple times if needed

### 5. Report API vs Raw Queries
- **Problem**: Building P&L from GL Entries requires complex joins
- **Solution**: Use ERPNext's built-in Reports when available
- **Benefit**: Optimized queries, consistent with ERPNext UI

## Security Considerations

### 1. API Key Storage
- **Risk**: API keys in plaintext `.env` file
- **Mitigation**: `.env` in `.gitignore`, never commit keys
- **Future**: Use environment secrets (Kubernetes Secrets, Docker Secrets)

### 2. Network Exposure
- **Risk**: ERPNext exposed on localhost:8002
- **Mitigation**: Bind to 127.0.0.1 only in docker-compose for local demo
- **Production**: Use reverse proxy with HTTPS, IP whitelisting

### 3. SQL Injection (run_query)
- **Risk**: If LLM generates SQL queries, injection possible
- **Mitigation**: DO NOT expose `run_query()` to agent tools directly
- **Safe Pattern**: Only use `get_list()` with parameterized filters

### 4. Permission Bypass
- **Risk**: API key has full admin access
- **Mitigation**: Create dedicated "AI Agent" user in ERPNext with limited permissions
- **Permissions**: Read-only access to Purchase Order, Item, Supplier, GL Entry

## Migration Path

### Phase 1: Infrastructure (Week 1)
- [x] ERPNext in docker-compose (DONE)
- [ ] Implement `ERPNextClient` in `services/erpnext_client.py`
- [ ] Write unit tests for client
- [ ] Update `scripts/start-all-services.sh` for automated startup

### Phase 2: Basic Tools (Week 2)
- [ ] Refactor `get_purchase_orders()` with ERPNext integration
- [ ] Refactor `get_inventory_levels()` with Bin/Item queries
- [ ] Refactor `get_top_vendors()` with aggregation
- [ ] Create `scripts/seed_erpnext_basic.py`
- [ ] Create `scripts/seed_erpnext_transactions.py`
- [ ] Integration testing with real ERPNext

### Phase 3: Advanced Tools (Week 3)
- [ ] Refactor `get_financial_summary()` using Reports API
- [ ] Refactor `get_vendor_price_trends()` with Purchase Order Item
- [ ] Refactor `get_procurement_summary()` with grouping
- [ ] Performance optimization (caching, query tuning)

### Phase 4: Documentation & Polish (Week 4)
- [ ] Update CLAUDE.md with ERPNext setup instructions
- [ ] Create troubleshooting guide for common issues
- [ ] Record demo video showing ERPNext integration
- [ ] Add monitoring for ERPNext availability (observability dashboard)

## Open Questions

1. **ERPNext Version**: Stick with v16 (current) or upgrade to v17? (v16 is stable, v17 has newer APIs)
2. **Custom Doctypes**: Should we create custom "AI Agent Log" doctype to track agent queries in ERPNext?
3. **Webhook Integration**: Should ERPNext send webhooks to agent on new PO creation? (proactive notifications)
4. **Multi-tenancy**: Support multiple ERPNext sites? (probably YAGNI for demo kit)

## References

- ERPNext REST API Docs: https://frappeframework.com/docs/user/en/api/rest
- ERPNext v16 Release Notes: https://github.com/frappe/erpnext/releases/tag/v16.0.0
- Frappe Framework Docs: https://frappeframework.com/docs
- BestBox System Design: `docs/system_design.md`

## Success Criteria

Integration is complete when:
- [ ] All 6 ERP tools work with live ERPNext data
- [ ] Fallback to demo data works when ERPNext unavailable
- [ ] Startup script auto-initializes and seeds ERPNext
- [ ] Response time < 2 seconds for typical queries
- [ ] Zero breaking changes to existing demo data mode
- [ ] Documentation updated with setup instructions
- [ ] Tests pass for both ERPNext and fallback modes
