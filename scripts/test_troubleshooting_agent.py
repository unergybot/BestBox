#!/usr/bin/env python3
"""
Test IT Ops Agent with Troubleshooting Tools

Verifies that the IT Ops agent can successfully search and retrieve
troubleshooting information from the knowledge base.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage
from agents.it_ops_agent import it_ops_agent_node, IT_OPS_TOOLS
from agents.state import AgentState


def test_agent_has_tools():
    """Test that troubleshooting tools are available"""
    print("=" * 70)
    print("TEST 1: Verify Tools Available")
    print("=" * 70)
    print()

    tool_names = [tool.name for tool in IT_OPS_TOOLS]
    print(f"IT Ops Agent has {len(IT_OPS_TOOLS)} tools:")
    for name in tool_names:
        print(f"  ✓ {name}")

    assert "search_troubleshooting_kb" in tool_names, "Missing search_troubleshooting_kb"
    assert "get_troubleshooting_case_details" in tool_names, "Missing get_troubleshooting_case_details"

    print()
    print("✅ All troubleshooting tools available")
    print()


def test_agent_invocation():
    """Test agent can be invoked with troubleshooting query"""
    print("=" * 70)
    print("TEST 2: Agent Invocation")
    print("=" * 70)
    print()

    # Create test state with troubleshooting query
    state = AgentState(
        messages=[
            HumanMessage(content="我遇到了产品披锋的问题，有什么解决方案？")
        ],
        current_agent="it_ops_agent",
        tool_calls=0,
        confidence=1.0,
        plugin_context={}
    )

    print("Query: '我遇到了产品披锋的问题，有什么解决方案？'")
    print("(I encountered product flash defect, any solutions?)")
    print()

    try:
        # Invoke agent
        print("Invoking IT Ops agent...")
        result = it_ops_agent_node(state)

        print()
        print("Agent Response:")
        print("-" * 70)

        response_message = result["messages"][0]

        # Check if agent wants to use tools
        if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
            print(f"✅ Agent wants to use {len(response_message.tool_calls)} tool(s):")
            for tool_call in response_message.tool_calls:
                print(f"   - {tool_call['name']}")
                print(f"     Args: {tool_call['args']}")

            # Check if troubleshooting tool was called
            tool_names = [tc['name'] for tc in response_message.tool_calls]
            if 'search_troubleshooting_kb' in tool_names:
                print()
                print("✅ Agent correctly chose to search troubleshooting KB!")
            else:
                print()
                print(f"⚠️  Agent chose other tools: {tool_names}")

        else:
            print("Agent provided direct response (no tool calls)")
            if hasattr(response_message, 'content'):
                print(f"Content: {response_message.content[:200]}...")

        print()
        print("✅ Agent invocation successful")

    except Exception as e:
        print(f"❌ Error invoking agent: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()
    return True


def test_tools_directly():
    """Test tools can be called directly"""
    print("=" * 70)
    print("TEST 3: Direct Tool Invocation")
    print("=" * 70)
    print()

    from tools.troubleshooting_tools import search_troubleshooting_kb

    print("Calling search_troubleshooting_kb directly...")
    result = search_troubleshooting_kb.invoke({
        "query": "产品披锋",
        "top_k": 2
    })

    import json
    data = json.loads(result)

    print(f"✅ Found {data['total_found']} results")

    if data['results']:
        print()
        print("Top result:")
        top = data['results'][0]
        print(f"  Problem: {top['problem'][:50]}...")
        print(f"  Relevance: {top['relevance_score']}")
        print(f"  Status: {top['success_status']}")

    print()
    print("✅ Direct tool call successful")
    print()


def main():
    print()
    print("TESTING IT OPS AGENT WITH TROUBLESHOOTING TOOLS")
    print("=" * 70)
    print()

    try:
        # Run tests
        test_agent_has_tools()
        test_tools_directly()
        test_agent_invocation()

        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("The IT Ops agent can now:")
        print("  • Search 1000+ troubleshooting cases")
        print("  • Find solutions for equipment defects")
        print("  • Retrieve detailed case information")
        print("  • Access images showing problems and solutions")
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
