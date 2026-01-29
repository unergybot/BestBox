import pytest
from unittest.mock import Mock, patch, MagicMock
from tools.erp_tools import get_purchase_orders, get_inventory_levels, get_top_vendors

@pytest.fixture
def mock_erp_client():
    with patch("tools.erp_tools.get_erpnext_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client

def test_get_purchase_orders_upgrade_to_erpnext(mock_erp_client):
    """Test standard flow when ERPNext is available."""
    mock_erp_client.is_available.return_value = True
    
    # Mock get_list return
    mock_erp_client.get_list.return_value = [
        {
            "name": "PO-TEST-1", 
            "supplier": "SUP-1", 
            "supplier_name": "Test Supplier",
            "grand_total": 1000.0,
            "status": "Draft",
            "transaction_date": "2025-10-01",
            "currency": "EUR"
        }
    ]
    
    result = get_purchase_orders.func()
    assert result["source"] == "erpnext"
    assert result["count"] == 1
    assert result["orders"][0]["id"] == "PO-TEST-1"
    
def test_get_purchase_orders_fallback(mock_erp_client):
    """Test fallback when ERPNext is unavailable."""
    mock_erp_client.is_available.return_value = False
    
    result = get_purchase_orders.func()
    assert result["source"] == "demo"
    assert result["count"] > 0
    
def test_get_purchase_orders_fallback_on_error(mock_erp_client):
    """Test fallback when ERPNext raises exception."""
    mock_erp_client.is_available.return_value = True
    mock_erp_client.get_list.side_effect = Exception("API Error")
    
    result = get_purchase_orders.func()
    assert result["source"] == "demo"
    assert result["count"] > 0 # Should return demo data

def test_get_inventory_levels_erpnext(mock_erp_client):
    mock_erp_client.is_available.return_value = True
    
    # Mock bins query
    mock_erp_client.get_list.side_effect = [
        # First call for Bin
        [{"item_code": "ITEM-1", "actual_qty": 50, "warehouse": "Main Warehouse"}],
        # Second call for Item details
        [{"item_code": "ITEM-1", "item_name": "Test Item", "item_group": "G1", "reorder_level": 10}]
    ]
    
    result = get_inventory_levels.func("WH-001")
    assert result["source"] == "erpnext"
    assert len(result["items"]) == 1
    assert result["items"][0]["quantity"] == 50

def test_get_top_vendors_erpnext(mock_erp_client):
    mock_erp_client.is_available.return_value = True
    
    # Mock POs for aggregation
    mock_erp_client.get_list.return_value = [
        {"supplier": "V1", "supplier_name": "Vendor 1", "grand_total": 500},
        {"supplier": "V1", "supplier_name": "Vendor 1", "grand_total": 500},
        {"supplier": "V2", "supplier_name": "Vendor 2", "grand_total": 200},
    ]
    
    result = get_top_vendors.func(limit=2)
    assert result["source"] == "erpnext"
    assert len(result["top_vendors"]) == 2
    assert result["top_vendors"][0]["vendor_id"] == "V1"
    assert result["top_vendors"][0]["total_spend"] == 1000
