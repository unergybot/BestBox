#!/usr/bin/env python3
"""
Enhanced Agent Demo Test Script

Tests the 4 primary demo scenarios from system_design.md:
1. ERP Procurement Analysis - "Why did Q4 procurement cost increase 30%?"
2. CRM Lead Prioritization - "Which leads should I focus on this week?"
3. IT Ops Fault Diagnosis - "Compressor unit A keeps failing, why?"
4. OA Document Generation - "Draft an approval email for Q4 budget increase"

Usage:
    python scripts/test_demo_scenarios.py [--scenario N] [--verbose]
"""

import sys
import os
import json
import asyncio
from dataclasses import dataclass
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.graph import app
from langchain_core.messages import HumanMessage


@dataclass
class DemoScenario:
    """Definition of a demo scenario with expected behavior."""
    id: int
    name: str
    query: str
    expected_agent: str
    expected_tools: List[str]
    response_must_contain: List[str]
    description: str


# Define the 4 primary demo scenarios
DEMO_SCENARIOS = [
    DemoScenario(
        id=1,
        name="ERP Procurement Analysis",
        query="Why did Q4 procurement cost increase 30%?",
        expected_agent="erp_agent",
        expected_tools=["get_purchase_orders", "get_vendor_price_trends", "get_procurement_summary"],
        response_must_contain=["VND-001", "vendor", "increase", "25%"],
        description="Tests ERP agent's ability to analyze procurement spend and identify vendor price increases"
    ),
    DemoScenario(
        id=2,
        name="CRM Lead Prioritization",
        query="Which leads should I focus on this week?",
        expected_agent="crm_agent",
        expected_tools=["get_leads", "predict_churn"],
        response_must_contain=["score", "Enterprise", "priority"],
        description="Tests CRM agent's ability to prioritize leads based on conversion probability"
    ),
    DemoScenario(
        id=3,
        name="IT Ops Fault Diagnosis",
        query="Compressor unit A keeps failing, why?",
        expected_agent="it_ops_agent",
        expected_tools=["query_maintenance_logs", "get_fault_codes"],
        response_must_contain=["fault", "failure", "recommendation"],
        description="Tests IT Ops agent's ability to diagnose equipment faults from logs"
    ),
    DemoScenario(
        id=4,
        name="OA Document Generation",
        query="Draft an approval email for the Q4 budget increase request",
        expected_agent="oa_agent",
        expected_tools=["generate_document", "draft_email"],
        response_must_contain=["Subject", "budget", "approval"],
        description="Tests OA agent's ability to generate business documents"
    ),
]

# Additional test queries
QUICK_TEST_QUERIES = [
    ("What is our current inventory level?", "erp_agent"),
    ("Which customers are at risk of churning?", "crm_agent"),
    ("The production database is unresponsive.", "it_ops_agent"),
    ("Schedule a meeting with the team.", "oa_agent"),
    ("Hi, how are you?", "fallback"),
]


@dataclass
class ScenarioResult:
    """Result of running a demo scenario."""
    scenario: DemoScenario
    passed: bool
    score: int
    max_score: int
    routing_correct: bool
    tools_used: List[str]
    response_text: str
    errors: List[str]


def evaluate_scenario(scenario: DemoScenario, result: dict) -> ScenarioResult:
    """Evaluate if agent response matches expected behavior."""
    errors = []
    score = 0
    max_score = 100
    
    # Check routing (25 points)
    current_agent = result.get("current_agent", "unknown")
    routing_correct = current_agent == scenario.expected_agent
    if routing_correct:
        score += 25
    else:
        errors.append(f"Routing: expected {scenario.expected_agent}, got {current_agent}")
    
    # Check response content (50 points)
    messages = result.get("messages", [])
    response_text = messages[-1].content if messages else ""
    
    keywords_found = 0
    for keyword in scenario.response_must_contain:
        if keyword.lower() in response_text.lower():
            keywords_found += 1
    
    keyword_score = int((keywords_found / len(scenario.response_must_contain)) * 50)
    score += keyword_score
    
    if keywords_found < len(scenario.response_must_contain):
        missing = [k for k in scenario.response_must_contain if k.lower() not in response_text.lower()]
        errors.append(f"Missing keywords: {missing}")
    
    # Check tool usage (25 points)
    tools_used = []
    for msg in messages:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.append(tc.get("name", "unknown"))
    
    if tools_used:
        score += 15  # Some tools were used
        expected_used = any(t in tools_used for t in scenario.expected_tools)
        if expected_used:
            score += 10
        else:
            errors.append(f"Expected tools {scenario.expected_tools}, used {tools_used}")
    else:
        errors.append("No tools were called")
    
    passed = score >= 70  # 70% threshold to pass
    
    return ScenarioResult(
        scenario=scenario,
        passed=passed,
        score=score,
        max_score=max_score,
        routing_correct=routing_correct,
        tools_used=tools_used,
        response_text=response_text[:500],  # Truncate for display
        errors=errors
    )


async def run_scenario(scenario: DemoScenario, verbose: bool = False) -> ScenarioResult:
    """Run a single demo scenario and evaluate results."""
    print(f"\n{'='*60}")
    print(f"Scenario {scenario.id}: {scenario.name}")
    print(f"{'='*60}")
    print(f"Query: {scenario.query}")
    print(f"Expected Agent: {scenario.expected_agent}")
    print("-" * 40)
    
    inputs = {"messages": [HumanMessage(content=scenario.query)]}
    
    try:
        result = await app.ainvoke(inputs)
        eval_result = evaluate_scenario(scenario, result)
        
        # Print results
        status = "✅ PASS" if eval_result.passed else "❌ FAIL"
        print(f"Result: {status} ({eval_result.score}/{eval_result.max_score})")
        print(f"Routing: {'✓' if eval_result.routing_correct else '✗'} → {result.get('current_agent', 'unknown')}")
        print(f"Tools Used: {eval_result.tools_used or 'None'}")
        
        if eval_result.errors:
            print(f"Issues: {', '.join(eval_result.errors)}")
        
        if verbose:
            print(f"\nResponse Preview:\n{eval_result.response_text[:300]}...")
        
        return eval_result
        
    except Exception as e:
        print(f"ERROR: {e}")
        return ScenarioResult(
            scenario=scenario,
            passed=False,
            score=0,
            max_score=100,
            routing_correct=False,
            tools_used=[],
            response_text=str(e),
            errors=[str(e)]
        )


async def run_quick_tests(verbose: bool = False):
    """Run quick routing tests."""
    print("\n" + "="*60)
    print("Quick Routing Tests")
    print("="*60)
    
    passed = 0
    total = len(QUICK_TEST_QUERIES)
    
    for query, expected_agent in QUICK_TEST_QUERIES:
        inputs = {"messages": [HumanMessage(content=query)]}
        try:
            result = await app.ainvoke(inputs)
            actual_agent = result.get("current_agent", "unknown")
            is_correct = actual_agent == expected_agent
            
            status = "✓" if is_correct else "✗"
            print(f"{status} \"{query[:40]}...\" → {actual_agent} (expected: {expected_agent})")
            
            if is_correct:
                passed += 1
        except Exception as e:
            print(f"✗ \"{query[:40]}...\" → ERROR: {e}")
    
    print(f"\nQuick Tests: {passed}/{total} passed")
    return passed, total


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test BestBox AI Agent Demo Scenarios")
    parser.add_argument("--scenario", type=int, help="Run specific scenario (1-4)")
    parser.add_argument("--quick", action="store_true", help="Run quick routing tests only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    print("="*60)
    print("BestBox AI Agent - Demo Scenario Tests")
    print("="*60)
    
    if args.quick:
        await run_quick_tests(args.verbose)
        return
    
    # Run scenarios
    if args.scenario:
        scenarios = [s for s in DEMO_SCENARIOS if s.id == args.scenario]
        if not scenarios:
            print(f"Error: Scenario {args.scenario} not found")
            return
    else:
        scenarios = DEMO_SCENARIOS
    
    results = []
    for scenario in scenarios:
        result = await run_scenario(scenario, args.verbose)
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for r in results if r.passed)
    total_score = sum(r.score for r in results)
    max_score = sum(r.max_score for r in results)
    
    for r in results:
        status = "✅" if r.passed else "❌"
        print(f"{status} Scenario {r.scenario.id}: {r.scenario.name} - {r.score}/{r.max_score}")
    
    print("-" * 40)
    print(f"Total: {passed_count}/{len(results)} scenarios passed")
    print(f"Score: {total_score}/{max_score} ({total_score/max_score*100:.0f}%)")
    
    if args.json:
        output = {
            "passed": passed_count,
            "total": len(results),
            "score": total_score,
            "max_score": max_score,
            "scenarios": [
                {
                    "id": r.scenario.id,
                    "name": r.scenario.name,
                    "passed": r.passed,
                    "score": r.score,
                    "routing_correct": r.routing_correct,
                    "tools_used": r.tools_used,
                    "errors": r.errors
                }
                for r in results
            ]
        }
        print("\n" + json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
