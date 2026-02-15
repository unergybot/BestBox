#!/usr/bin/env python3
"""
Smoke test for RBAC enforcement in agent system.

Tests:
1. Protected tools deny users without roles
2. Protected tools allow users with proper roles
3. Protected tools correctly check role intersections
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage

# Import RBAC functions from graph.py
from agents.graph import (
    _unauthorized_tools,
    _get_user_roles,
    PROTECTED_TOOL_ROLES,
)
from agents.state import AgentState


def create_test_state(
    user_roles: list[str] | None,
    tool_call_names: list[str],
) -> AgentState:
    """Create a test AgentState with user context and tool calls."""
    # Create AIMessage with tool calls
    tool_calls = [
        {"name": name, "args": {}, "id": f"call_{i}"}
        for i, name in enumerate(tool_call_names)
    ]

    ai_message = AIMessage(
        content="",
        tool_calls=tool_calls,
    )

    # Create user context
    user_context = None
    if user_roles is not None:
        user_context = {
            "user_id": "test_user",
            "roles": user_roles,
            "org_id": "test_org",
        }

    state: AgentState = {
        "messages": [HumanMessage(content="test"), ai_message],
        "current_agent": "test",
        "tool_calls": 0,
        "user_context": user_context,
    }

    return state


def test_rbac_enforcement():
    """Run RBAC enforcement smoke tests."""
    print("=" * 80)
    print("RBAC ENFORCEMENT SMOKE TESTS")
    print("=" * 80)

    # Save original STRICT_TOOL_AUTH setting
    original_strict = os.getenv("STRICT_TOOL_AUTH")

    try:
        # Enable strict mode for testing
        os.environ["STRICT_TOOL_AUTH"] = "true"

        # Test 1: User with no roles should be denied all protected tools
        print("\n[TEST 1] User with no roles attempting protected tool call")
        state = create_test_state(
            user_roles=[],
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" in denied, "Should deny user with no roles"
        print("✅ PASS - User with no roles correctly denied")

        # Test 2: User with no user_context should be denied in strict mode
        print("\n[TEST 2] User with no user_context in strict mode")
        state = create_test_state(
            user_roles=None,
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" in denied, "Should deny user with no context in strict mode"
        print("✅ PASS - User with no context correctly denied in strict mode")

        # Test 3: User with correct role should be allowed
        print("\n[TEST 3] User with 'finance' role attempting get_financial_summary")
        state = create_test_state(
            user_roles=["finance"],
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" not in denied, "Should allow user with finance role"
        print("✅ PASS - User with correct role allowed")

        # Test 4: User with 'admin' role should be allowed (admin in allowed set)
        print("\n[TEST 4] User with 'admin' role attempting get_financial_summary")
        state = create_test_state(
            user_roles=["admin"],
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" not in denied, "Should allow user with admin role"
        print("✅ PASS - Admin role correctly allowed")

        # Test 5: User with wrong role should be denied
        print("\n[TEST 5] User with 'viewer' role attempting get_financial_summary")
        state = create_test_state(
            user_roles=["viewer"],
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" in denied, "Should deny user with viewer role"
        print("✅ PASS - User with wrong role correctly denied")

        # Test 6: Multiple tools, mixed permissions
        print("\n[TEST 6] User with 'viewer' role attempting mixed tool calls")
        state = create_test_state(
            user_roles=["viewer"],
            tool_call_names=[
                "get_purchase_orders",  # viewer allowed
                "get_financial_summary",  # viewer NOT allowed
                "get_leads",  # unprotected tool
            ],
        )
        denied = _unauthorized_tools(state)
        assert "get_purchase_orders" not in denied, "Should allow get_purchase_orders for viewer"
        assert "get_financial_summary" in denied, "Should deny get_financial_summary for viewer"
        assert "get_leads" not in denied, "Should allow unprotected tool"
        print("✅ PASS - Mixed tool permissions correctly enforced")

        # Test 7: Case insensitivity
        print("\n[TEST 7] Role case insensitivity")
        state = create_test_state(
            user_roles=["Finance", "ADMIN"],  # Mixed case
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" not in denied, "Should handle case-insensitive roles"
        print("✅ PASS - Role case insensitivity works")

        # Test 8: Non-strict mode allows missing user_context
        print("\n[TEST 8] Non-strict mode behavior")
        os.environ["STRICT_TOOL_AUTH"] = "false"
        state = create_test_state(
            user_roles=None,
            tool_call_names=["get_financial_summary"],
        )
        denied = _unauthorized_tools(state)
        assert "get_financial_summary" not in denied, "Should allow in non-strict mode"
        print("✅ PASS - Non-strict mode allows missing context")

        print("\n" + "=" * 80)
        print("ALL RBAC TESTS PASSED ✅")
        print("=" * 80)

        # Print current protected tools
        print("\n📋 Current Protected Tools Configuration:")
        for tool, roles in PROTECTED_TOOL_ROLES.items():
            print(f"  • {tool}: {', '.join(sorted(roles))}")

        return True

    except AssertionError as e:
        print(f"\n❌ FAIL - {e}")
        return False

    finally:
        # Restore original setting
        if original_strict is not None:
            os.environ["STRICT_TOOL_AUTH"] = original_strict
        elif "STRICT_TOOL_AUTH" in os.environ:
            del os.environ["STRICT_TOOL_AUTH"]


if __name__ == "__main__":
    success = test_rbac_enforcement()
    sys.exit(0 if success else 1)
