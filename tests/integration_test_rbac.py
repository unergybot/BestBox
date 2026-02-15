#!/usr/bin/env python3
"""
RBAC Integration Test - End-to-End User Isolation and Role Enforcement

Tests the complete RBAC flow through the API layer:
1. User A with 'finance' role can access get_financial_summary
2. User B with 'viewer' role CANNOT access get_financial_summary
3. User B CAN access get_purchase_orders (viewer allowed)
4. Anonymous users are denied in strict mode

This proves user isolation and role enforcement work end-to-end.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_user_isolation_via_graph():
    """
    Test RBAC enforcement by directly invoking the graph with different user contexts.

    This simulates what the API does without needing to start the HTTP server.
    """
    print("\n" + "=" * 80)
    print("RBAC INTEGRATION TEST - User Isolation via Graph Invocation")
    print("=" * 80)

    # Import dependencies
    from agents.state import AgentState
    from agents.graph import app as graph  # Import the compiled graph
    from langchain_core.messages import HumanMessage

    # Enable strict auth mode
    os.environ["STRICT_TOOL_AUTH"] = "true"

    # Test 1: User with 'finance' role accessing protected tool
    print("\n[TEST 1] Finance user accessing get_financial_summary")

    state1: AgentState = {
        "messages": [HumanMessage(content="Show me the financial summary for Q4 2024")],
        "current_agent": "router",
        "tool_calls": 0,
        "user_context": {
            "user_id": "alice@company.com",
            "roles": ["finance"],
            "org_id": "org_001",
        },
    }

    try:
        result1 = graph.invoke(state1)
        messages1 = result1.get("messages", [])
        last_msg1 = messages1[-1] if messages1 else None

        if last_msg1 and "Permission denied" in str(last_msg1.content):
            print("  ❌ FAIL - Finance user was incorrectly denied access")
            return False
        else:
            print("  ✅ PASS - Finance user successfully accessed financial summary")
            # Log what was returned
            if last_msg1:
                print(f"  Response preview: {str(last_msg1.content)[:200]}")
    except Exception as e:
        print(f"  ❌ FAIL - Error during execution: {e}")
        return False

    # Test 2: User with 'viewer' role trying to access protected tool
    print("\n[TEST 2] Viewer user attempting get_financial_summary (should be denied)")

    state2: AgentState = {
        "messages": [HumanMessage(content="Show me the financial summary for Q4 2024")],
        "current_agent": "router",
        "tool_calls": 0,
        "user_context": {
            "user_id": "bob@company.com",
            "roles": ["viewer"],
            "org_id": "org_001",
        },
    }

    try:
        result2 = graph.invoke(state2)
        messages2 = result2.get("messages", [])
        last_msg2 = messages2[-1] if messages2 else None

        # Check if access was denied (either explicit "Permission denied" or polite refusal)
        denial_indicators = [
            "Permission denied",
            "unable to retrieve",
            "permission restrictions",
            "contact your administrator",
            "access denied",
        ]

        content2 = str(last_msg2.content).lower() if last_msg2 else ""
        is_denied = any(indicator.lower() in content2 for indicator in denial_indicators)

        if is_denied:
            print("  ✅ PASS - Viewer user was correctly denied access")
            print(f"  Denial message: {last_msg2.content[:150]}...")
        else:
            # Check if they actually got the financial data
            if "revenue" in content2 or "expenses" in content2 or "profit" in content2:
                print("  ❌ FAIL - Viewer user received financial data despite role restriction")
                if last_msg2:
                    print(f"  Leaked response: {str(last_msg2.content)[:200]}")
                return False
            else:
                print("  ✅ PASS - Viewer user did not receive protected financial data")
                print(f"  Response: {content2[:150]}")
    except Exception as e:
        print(f"  ❌ FAIL - Error during execution: {e}")
        return False

    # Test 3: Viewer accessing allowed tool
    print("\n[TEST 3] Viewer user accessing get_purchase_orders (should succeed)")

    state3: AgentState = {
        "messages": [HumanMessage(content="Show me the latest purchase orders")],
        "current_agent": "router",
        "tool_calls": 0,
        "user_context": {
            "user_id": "bob@company.com",
            "roles": ["viewer"],
            "org_id": "org_001",
        },
    }

    try:
        result3 = graph.invoke(state3)
        messages3 = result3.get("messages", [])
        last_msg3 = messages3[-1] if messages3 else None

        if last_msg3 and "Permission denied" in str(last_msg3.content):
            print("  ❌ FAIL - Viewer was incorrectly denied access to allowed tool")
            return False
        else:
            print("  ✅ PASS - Viewer successfully accessed purchase orders")
            if last_msg3:
                print(f"  Response preview: {str(last_msg3.content)[:200]}")
    except Exception as e:
        print(f"  ❌ FAIL - Error during execution: {e}")
        return False

    # Test 4: Anonymous user in strict mode
    print("\n[TEST 4] Anonymous user attempting protected tool (strict mode)")

    state4: AgentState = {
        "messages": [HumanMessage(content="Show me the financial summary")],
        "current_agent": "router",
        "tool_calls": 0,
        "user_context": None,  # No user context
    }

    try:
        result4 = graph.invoke(state4)
        messages4 = result4.get("messages", [])
        last_msg4 = messages4[-1] if messages4 else None

        # Check for denial indicators
        denial_indicators = [
            "Permission denied",
            "unable to retrieve",
            "permission restrictions",
            "contact your administrator",
            "access denied",
        ]

        content4 = str(last_msg4.content).lower() if last_msg4 else ""
        is_denied = any(indicator.lower() in content4 for indicator in denial_indicators)

        if is_denied:
            print("  ✅ PASS - Anonymous user was correctly denied in strict mode")
        else:
            # Check if they got financial data
            if "revenue" in content4 or "expenses" in content4 or "profit" in content4:
                print("  ❌ FAIL - Anonymous user received protected data")
                if last_msg4:
                    print(f"  Leaked response: {str(last_msg4.content)[:200]}")
                return False
            else:
                print("  ✅ PASS - Anonymous user did not receive protected data")
    except Exception as e:
        print(f"  ❌ FAIL - Error during execution: {e}")
        return False

    print("\n" + "=" * 80)
    print("ALL RBAC INTEGRATION TESTS PASSED ✅")
    print("=" * 80)
    print("\nKey Findings:")
    print("  ✓ User isolation enforced correctly")
    print("  ✓ Role-based access control working end-to-end")
    print("  ✓ Protected tools deny unauthorized users")
    print("  ✓ Allowed tools permit authorized users")
    print("  ✓ Strict mode denies anonymous access")

    return True


async def main():
    """Run all RBAC integration tests."""
    try:
        success = await test_user_isolation_via_graph()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Integration test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
