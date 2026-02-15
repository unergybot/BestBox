#!/usr/bin/env python3
"""
Fast RBAC Integration Test - Direct Authorization Logic Testing

Tests RBAC enforcement without requiring LLM inference.
Verifies the authorization layer works correctly for user isolation.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rbac_authorization_logic():
    """Test RBAC authorization logic directly without LLM calls."""
    print("\n" + "=" * 80)
    print("FAST RBAC INTEGRATION TEST - Authorization Logic")
    print("=" * 80)

    # Import authorization functions
    from agents.graph import _unauthorized_tools, _get_user_roles, PROTECTED_TOOL_ROLES
    from agents.state import AgentState
    from langchain_core.messages import AIMessage, HumanMessage

    # Enable strict mode
    os.environ["STRICT_TOOL_AUTH"] = "true"

    # Test 1: Finance user can access get_financial_summary
    print("\n[TEST 1] Finance user accessing get_financial_summary")

    tool_call = {
        "name": "get_financial_summary",
        "args": {"period": "Q4"},
        "id": "call_1"
    }

    state1: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": {
            "user_id": "alice@company.com",
            "roles": ["finance"],
            "org_id": "org_001",
        },
    }

    denied1 = _unauthorized_tools(state1)
    if "get_financial_summary" in denied1:
        print(f"  ❌ FAIL - Finance user incorrectly denied: {denied1}")
        return False
    else:
        print("  ✅ PASS - Finance user authorized for get_financial_summary")

    # Test 2: Viewer user CANNOT access get_financial_summary
    print("\n[TEST 2] Viewer user attempting get_financial_summary")

    state2: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": {
            "user_id": "bob@company.com",
            "roles": ["viewer"],
            "org_id": "org_001",
        },
    }

    denied2 = _unauthorized_tools(state2)
    if "get_financial_summary" in denied2:
        print(f"  ✅ PASS - Viewer user correctly denied: {denied2}")
    else:
        print("  ❌ FAIL - Viewer user should be denied get_financial_summary")
        return False

    # Test 3: Viewer CAN access get_purchase_orders
    print("\n[TEST 3] Viewer user accessing get_purchase_orders")

    tool_call3 = {
        "name": "get_purchase_orders",
        "args": {"status": "pending"},
        "id": "call_3"
    }

    state3: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call3])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": {
            "user_id": "bob@company.com",
            "roles": ["viewer"],
            "org_id": "org_001",
        },
    }

    denied3 = _unauthorized_tools(state3)
    if "get_purchase_orders" in denied3:
        print(f"  ❌ FAIL - Viewer should be allowed get_purchase_orders but was denied: {denied3}")
        return False
    else:
        print("  ✅ PASS - Viewer authorized for get_purchase_orders")

    # Test 4: Anonymous user denied in strict mode
    print("\n[TEST 4] Anonymous user in strict mode")

    state4: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": None,  # No user context
    }

    denied4 = _unauthorized_tools(state4)
    if "get_financial_summary" in denied4:
        print(f"  ✅ PASS - Anonymous user correctly denied in strict mode: {denied4}")
    else:
        print("  ❌ FAIL - Anonymous user should be denied in strict mode")
        return False

    # Test 5: Admin user has universal access
    print("\n[TEST 5] Admin user accessing get_financial_summary")

    state5: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": {
            "user_id": "admin@company.com",
            "roles": ["admin"],
            "org_id": "org_001",
        },
    }

    denied5 = _unauthorized_tools(state5)
    if "get_financial_summary" in denied5:
        print(f"  ❌ FAIL - Admin user incorrectly denied: {denied5}")
        return False
    else:
        print("  ✅ PASS - Admin user authorized for all protected tools")

    # Test 6: Multiple roles (procurement + viewer)
    print("\n[TEST 6] User with multiple roles (procurement, viewer)")

    state6: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": {
            "user_id": "charlie@company.com",
            "roles": ["procurement", "viewer"],
            "org_id": "org_001",
        },
    }

    denied6 = _unauthorized_tools(state6)
    # Procurement is NOT in the allowed roles for get_financial_summary (only admin, finance)
    if "get_financial_summary" in denied6:
        print(f"  ✅ PASS - Procurement user correctly denied (not in allowed roles)")
    else:
        print(f"  ❌ FAIL - Procurement should not access financial summary")
        return False

    # Test 7: Case insensitivity
    print("\n[TEST 7] Role case insensitivity (FINANCE vs finance)")

    state7: AgentState = {
        "messages": [
            HumanMessage(content="test"),
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "current_agent": "erp",
        "tool_calls": 0,
        "user_context": {
            "user_id": "dave@company.com",
            "roles": ["FINANCE", "Admin"],  # Mixed case
            "org_id": "org_001",
        },
    }

    denied7 = _unauthorized_tools(state7)
    if "get_financial_summary" in denied7:
        print(f"  ❌ FAIL - Case-insensitive role matching failed: {denied7}")
        return False
    else:
        print("  ✅ PASS - Case-insensitive role matching works")

    print("\n" + "=" * 80)
    print("ALL FAST RBAC TESTS PASSED ✅")
    print("=" * 80)
    print("\nRBAC System Verified:")
    print("  ✓ User roles correctly extracted and normalized")
    print("  ✓ Protected tools enforce role requirements")
    print("  ✓ Viewers have limited access")
    print("  ✓ Finance users access financial tools")
    print("  ✓ Admin users have universal access")
    print("  ✓ Anonymous users denied in strict mode")
    print("  ✓ Multiple roles handled correctly")
    print("  ✓ Case-insensitive role matching")
    print(f"\nProtected Tools: {len(PROTECTED_TOOL_ROLES)} configured")
    for tool, roles in PROTECTED_TOOL_ROLES.items():
        print(f"  • {tool}: {', '.join(sorted(roles))}")

    return True


if __name__ == "__main__":
    success = test_rbac_authorization_logic()
    sys.exit(0 if success else 1)
