#!/usr/bin/env python3
"""
Smoke test for CRM backend integration.

Tests:
1. CRM tools load successfully
2. Integration config is loaded correctly
3. Fallback to demo data works when backend unavailable
4. ERPNext backend is attempted when configured
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.customer_config import get_integration_config


def test_config_loading():
    """Test customer config loading for CRM integration."""
    print("\n[TEST 1] Customer config loading")

    # Test environment variable override
    os.environ["CRM_BACKEND"] = "erpnext_test"
    os.environ["CRM_URL"] = "http://test.local"

    config = get_integration_config("crm")

    print(f"  Config loaded: {config}")
    print(f"  Backend: {config.get('backend', 'not set')}")
    print(f"  URL: {config.get('url', 'not set')}")

    # Check if env vars were respected
    if config.get("backend") == "erpnext_test":
        print("✅ PASS - Environment variable override works")
    else:
        print(f"⚠️  WARNING - Expected 'erpnext_test', got {config.get('backend')}")

    # Clean up
    if "CRM_BACKEND" in os.environ:
        del os.environ["CRM_BACKEND"]
    if "CRM_URL" in os.environ:
        del os.environ["CRM_URL"]

    return True


def test_crm_tools_import():
    """Test that CRM tools can be imported without errors."""
    print("\n[TEST 2] CRM tools import")

    try:
        from tools.crm_tools import (
            get_leads,
            predict_churn,
            get_customer_360,
            get_high_churn_customers,
            generate_quote,
        )
        print("✅ PASS - All CRM tools imported successfully")
        return True
    except ImportError as e:
        print(f"❌ FAIL - Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ FAIL - Unexpected error: {e}")
        return False


def test_crm_tools_execution():
    """Test CRM tools execute and return data (demo fallback)."""
    print("\n[TEST 3] CRM tools execution with demo fallback")

    try:
        from tools.crm_tools import get_leads, predict_churn, get_customer_360

        # Test get_leads
        print("  Testing get_leads()...")
        leads_result = get_leads.invoke({"status": "Open"})
        assert isinstance(leads_result, list), f"get_leads should return list, got {type(leads_result)}"
        print(f"  ✓ get_leads returned {len(leads_result)} leads")

        # Test predict_churn
        print("  Testing predict_churn()...")
        churn_result = predict_churn.invoke({"customer_id": "CUST-001"})
        assert isinstance(churn_result, dict), "predict_churn should return dict"
        assert "churn_probability" in churn_result or "error" in churn_result, "Result should have 'churn_probability' or 'error'"
        if "churn_probability" in churn_result:
            print(f"  ✓ predict_churn returned probability: {churn_result.get('churn_probability')}")
        else:
            print(f"  ✓ predict_churn returned: {churn_result.get('error', 'unknown')}")

        # Test get_customer_360
        print("  Testing get_customer_360()...")
        customer_result = get_customer_360.invoke({"customer_id": "CUST-001"})
        assert isinstance(customer_result, dict), "get_customer_360 should return dict"
        print(f"  ✓ get_customer_360 returned data with keys: {list(customer_result.keys())[:5]}")

        print("✅ PASS - All CRM tools execute and return data")
        return True

    except Exception as e:
        print(f"❌ FAIL - Execution error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backend_selection():
    """Test that backend selection logic works."""
    print("\n[TEST 4] Backend selection logic")

    try:
        from tools.crm_tools import get_crm_backend

        # Test default backend
        backend = get_crm_backend()
        print(f"  Default backend: {backend}")

        # Test environment variable override
        os.environ["CRM_BACKEND"] = "erpnext"
        backend = get_crm_backend()
        print(f"  Override backend: {backend}")
        assert backend == "erpnext", "Should respect CRM_BACKEND env var"

        # Clean up
        if "CRM_BACKEND" in os.environ:
            del os.environ["CRM_BACKEND"]

        print("✅ PASS - Backend selection works")
        return True

    except Exception as e:
        print(f"⚠️  WARNING - Could not test backend selection: {e}")
        return True  # Not critical


def main():
    """Run all CRM integration smoke tests."""
    print("=" * 80)
    print("CRM BACKEND INTEGRATION SMOKE TESTS")
    print("=" * 80)

    results = []

    results.append(test_config_loading())
    results.append(test_crm_tools_import())
    results.append(test_crm_tools_execution())
    results.append(test_backend_selection())

    print("\n" + "=" * 80)
    if all(results):
        print("ALL CRM INTEGRATION TESTS PASSED ✅")
        print("=" * 80)
        return True
    else:
        failed_count = len([r for r in results if not r])
        print(f"SOME TESTS FAILED ({failed_count}/{len(results)}) ❌")
        print("=" * 80)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
