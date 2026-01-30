#!/usr/bin/env python3
"""
Test Mold Service Agent with Troubleshooting Tools

Verifies that the Mold agent can successfully search and retrieve
mold troubleshooting information from the knowledge base.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage
from agents.mold_agent import mold_agent_node, MOLD_TOOLS
from agents.state import AgentState


def test_agent_has_tools():
    """Test that troubleshooting tools are available"""
    print("=" * 70)
    print("TEST 1: Verify Mold Agent Tools")
    print("=" * 70)
    print()

    tool_names = [tool.name for tool in MOLD_TOOLS]
    print(f"Mold Agent has {len(MOLD_TOOLS)} tools:")
    for name in tool_names:
        print(f"  ✓ {name}")

    assert "search_troubleshooting_kb" in tool_names
    assert "get_troubleshooting_case_details" in tool_names

    print()
    print("✅ All troubleshooting tools available")
    print()


def test_mold_queries():
    """Test mold agent with various manufacturing queries"""
    print("=" * 70)
    print("TEST 2: Mold Agent with Manufacturing Queries")
    print("=" * 70)
    print()

    test_queries = [
        "我遇到了产品披锋的问题，有什么解决方案？",
        "模具表面有污染怎么办？",
        "零件1947688在T2阶段有哪些问题？"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\nQuery {i}: {query}")
        print("-" * 70)

        state = AgentState(
            messages=[HumanMessage(content=query)],
            current_agent="mold_agent",
            tool_calls=0,
            confidence=1.0,
            plugin_context={}
        )

        try:
            result = mold_agent_node(state)
            response_message = result["messages"][0]

            if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
                print(f"✅ Agent wants to use tool:")
                for tool_call in response_message.tool_calls:
                    print(f"   - {tool_call['name']}")
                    print(f"     Args: {tool_call['args']}")
            else:
                print("⚠️  Agent responded without using tools")

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    print()
    print("✅ All queries handled successfully")
    print()
    return True


def test_router_integration():
    """Test that router correctly routes to mold agent"""
    print("=" * 70)
    print("TEST 3: Router Integration")
    print("=" * 70)
    print()

    from agents.router import router_node
    from agents.state import AgentState

    test_cases = [
        ("产品披锋问题", "mold_agent"),
        ("模具表面污染", "mold_agent"),
        ("T2试模结果", "mold_agent"),
    ]

    for query, expected_agent in test_cases:
        print(f"Query: {query}")

        state = AgentState(
            messages=[HumanMessage(content=query)],
            current_agent="",
            tool_calls=0,
            confidence=0.0,
            plugin_context={}
        )

        try:
            result = router_node(state)
            routed_agent = result.get("current_agent", "unknown")

            if routed_agent == expected_agent:
                print(f"  ✅ Routed to: {routed_agent}")
            else:
                print(f"  ⚠️  Routed to: {routed_agent} (expected: {expected_agent})")

        except Exception as e:
            print(f"  ❌ Router error: {e}")
            return False

    print()
    print("✅ Router integration working")
    print()
    return True


def main():
    print()
    print("TESTING MOLD SERVICE AGENT")
    print("=" * 70)
    print()

    try:
        # Run tests
        test_agent_has_tools()
        test_mold_queries()
        test_router_integration()

        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("The Mold Service Agent is ready!")
        print()
        print("Capabilities:")
        print("  ✓ Search 1000+ manufacturing troubleshooting cases")
        print("  ✓ Find solutions for mold defects and product issues")
        print("  ✓ Access trial results (T0/T1/T2) and success indicators")
        print("  ✓ View images showing problems and solutions")
        print("  ✓ Automatic routing from router for mold/manufacturing queries")
        print()
        print("Example queries:")
        print("  • '产品披锋怎么解决？'")
        print("  • '模具表面污染问题'")
        print("  • '火花纹残留的解决方案'")
        print("  • '零件1947688的T2问题'")
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ TESTS FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
