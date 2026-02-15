# BestBox Demo Data Setup Guide

This guide explains how to set up demo data on a new BestBox device.

## Overview

The BestBox demo data includes:
- **16 Purchase Orders** (general merchandise + robotics components)
- **13 Sales Orders** (B2B sales to various customers)
- **6 Suppliers** (3 general + 3 robotics suppliers)
- **7 Customers** (3 general + 4 robotics companies)
- **18 Items** (10 general SKUs + 8 robotics items)

Total transaction value: ~¥10.3M in sales, ~¥2.5M in purchases

## Demo Data Files

### Primary Files
- `data/demo/demo_data.json` - Current demo data (always use this)
- `data/demo/demo_data.YYYYMMDD.json` - Timestamped backups

### Demo Data Structure

The JSON file contains:
```json
{
  "purchase_orders": [...],
  "vendors": [...],
  "sales_orders": [...],
  "items": [...],
  "customers": [...],
  "invoices": [...]
}
```

## Quick Setup for New Devices

### Method 1: Automatic Seeding (Recommended)

This method seeds the master data (suppliers, customers, items) into ERPNext:

```bash
# 1. Ensure ERPNext is running
docker compose -f ~/MyCode/frappe_docker/pwd.yml ps

# 2. Configure .env with ERPNext credentials
# ERPNEXT_URL=http://localhost:8080
# ERPNEXT_SITE=frontend
# ERPNEXT_API_KEY=your_key
# ERPNEXT_API_SECRET=your_secret

# 3. Test with dry run
python scripts/seed_erpnext_demo_data.py --dry-run

# 4. Run actual seeding
python scripts/seed_erpnext_demo_data.py
```

**What it creates:**
- ✓ Suppliers/Vendors (6)
- ✓ Customers (7)
- ✓ Items (18)
- ⚠️ Purchase Orders (must create manually via UI/API due to ERPNext ID generation)
- ⚠️ Sales Orders (must create manually via UI/API)

### Method 2: Manual ERPNext Setup

For creating purchase/sales orders, use the ERPNext API or UI:

**Option A: Using ERPNext UI**
1. Navigate to Buying → Purchase Order → New
2. Fill in supplier, items, quantities from `demo_data.json`
3. Save and submit

**Option B: Using curl/API**
```bash
# Example: Create a purchase order
curl -X POST "http://localhost:8080/api/resource/Purchase%20Order" \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Host: frontend" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": "MA Inc.",
    "company": "Unergy Robotics",
    "transaction_date": "2026-02-15",
    "items": [
      {
        "item_code": "SKU002",
        "qty": 100,
        "rate": 350,
        "warehouse": "仓库 - UR",
        "schedule_date": "2026-03-01"
      }
    ]
  }'
```

### Method 3: Fallback Mode (No ERPNext)

If ERPNext is unavailable, the agent API automatically uses `data/demo/demo_data.json` as fallback data:

```python
# In tools/erp_tools.py, the fallback logic automatically activates:
if not erpnext_client.is_available():
    return load_fallback_demo_data()
```

No configuration needed - this works out of the box!

## Demo Data Content

### General Merchandise Sector

**Suppliers:**
- Zuckerman Security Ltd.
- MA Inc.
- Summit Traders Ltd.

**Products:**
- Consumer goods (T-shirts, Laptops, Books, Smartphones, etc.)
- Electronics (Headphones, Cameras, Televisions)
- General merchandise (Backpacks, Sneakers, Coffee Mugs)

**Customers:**
- Grant Plastics Ltd.
- West View Software Ltd.
- Palmer Productions Ltd.

### Robotics Sector (新增机器人行业数据)

**Suppliers (中国机器人供应商):**
- 深圳市大疆创新科技有限公司 (DJI Innovation) - Sensors & components
- 苏州绿的谐波传动科技股份有限公司 (Leader Harmonics) - Harmonic drives
- 深圳市越疆科技有限公司 (Dobot Robotics) - Controllers & components

**Products (机器人产品):**

*Components:*
- ROB-ACT-001: 谐波减速器 (Harmonic Drive Reducer)
- ROB-SEN-001: 激光雷达传感器 (LiDAR Sensor)
- ROB-CTRL-001: 运动控制器 (Motion Controller)
- ROB-BAT-001: 锂电池组 (Lithium Battery Pack)
- ROB-PART-001: 机器人底盘 (Robot Chassis)

*Finished Robots:*
- ROB-FIN-001: 四足机器人 (Quadruped Robot)
- ROB-FIN-002: 人形机器人 (Humanoid Robot)
- ROB-FIN-003: 工业机械臂 (Industrial Robot Arm)

**Customers (中国机器人公司):**
- 杭州宇树科技有限公司 (Unitree Robotics)
- 深圳市智元机器人技术有限公司 (AGIbot Technology)
- 北京优必选科技股份有限公司 (UBTECH Robotics)
- 上海傅利叶智能科技有限公司 (Fourier Intelligence)

## Updating Demo Data

### Adding New Data

1. **Add to ERPNext** (if available):
   ```bash
   # Use ERPNext UI or API to create new records
   ```

2. **Extract from ERPNext to JSON**:
   ```bash
   # Fetch data via API and format as JSON
   curl -s "http://localhost:8080/api/resource/Purchase%20Order?limit_page_length=999" \
     -H "Authorization: token KEY:SECRET" \
     -H "Host: frontend" | jq '.data' > new_po_data.json
   ```

3. **Merge into demo_data.json**:
   - Edit `data/demo/demo_data.json`
   - Add new records to appropriate arrays
   - Validate JSON: `jq . data/demo/demo_data.json`

4. **Create backup**:
   ```bash
   cp data/demo/demo_data.json data/demo/demo_data.$(date +%Y%m%d).json
   ```

### Data Consistency

Always maintain consistency between:
- ✓ ERPNext live data (source of truth when available)
- ✓ `data/demo/demo_data.json` (fallback + setup reference)
- ✓ Vendor/Customer/Item references in orders

## Troubleshooting

### Issue: Warehouse errors when creating orders

**Error:** "仓库仓库 - UR不属于公司Unergy Robotics (Demo)"

**Solution:** Ensure warehouse and company match:
```json
{
  "company": "Unergy Robotics",  // Must match warehouse company
  "items": [{
    "warehouse": "仓库 - UR"      // Belongs to "Unergy Robotics"
  }]
}
```

### Issue: Item not found

**Error:** "找不到物料号: ROB-XXX"

**Solution:** Create items first before orders:
```bash
python scripts/seed_erpnext_demo_data.py  # Creates items
# Then create orders
```

### Issue: API authentication fails

**Error:** 401 Unauthorized

**Solution:** Check `.env` credentials:
```bash
# Verify in ERPNext UI: User → Administrator → API Access
grep ERPNEXT .env
```

## Production Deployment Checklist

When setting up a new BestBox demo device:

- [ ] Clone BestBox repository
- [ ] Set up ERPNext (frappe_docker or custom)
- [ ] Configure `.env` with ERPNext credentials
- [ ] Run `python scripts/seed_erpnext_demo_data.py --dry-run`
- [ ] Run `python scripts/seed_erpnext_demo_data.py`
- [ ] Verify data in ERPNext UI
- [ ] Test agent API: `curl http://localhost:8000/health`
- [ ] Test ERP queries via frontend

## Backup and Recovery

### Backup Demo Data
```bash
# JSON backup
cp data/demo/demo_data.json data/demo/demo_data.$(date +%Y%m%d).json

# ERPNext backup (via bench)
docker exec frappe_docker-backend-1 bench --site frontend backup
```

### Restore Demo Data
```bash
# Restore JSON (automatic fallback)
# Just ensure data/demo/demo_data.json exists

# Restore ERPNext backup
docker exec frappe_docker-backend-1 bench --site frontend restore backup_file.sql.gz
```

## Related Documentation

- `/docs/system_design.md` - System architecture
- `/CLAUDE.md` - Project overview and commands
- `/scripts/seed_knowledge_base.py` - RAG knowledge base seeding

## Support

For issues or questions about demo data setup, check:
1. ERPNext logs: `docker logs frappe_docker-backend-1`
2. Agent API logs: `~/BestBox/logs/agent_api.log`
3. GitHub issues: https://github.com/yourusername/BestBox/issues
