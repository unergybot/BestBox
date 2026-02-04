# Agentic RAG with ReAct Reasoning — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add visible ReAct reasoning, session logging, and admin UI to BestBox for impressive stakeholder demos.

**Architecture:** Parallel deployment of ReAct graph alongside existing system. New `/chat/react` endpoint with Think→Act→Observe loop. PostgreSQL session storage. Admin UI at `/admin`.

**Tech Stack:** Python 3.10+, LangGraph, FastAPI, PostgreSQL (asyncpg), Next.js 16, React 19, Tailwind CSS 4

---

## Task 1: Add ReasoningStep Type to State

**Files:**
- Modify: `agents/state.py:1-47`
- Test: `tests/test_react_state.py` (new)

**Step 1: Write the failing test**

Create `tests/test_react_state.py`:

```python
"""Tests for ReAct state extensions."""

import pytest
from agents.state import AgentState, ReasoningStep


class TestReasoningStep:
    """Test ReasoningStep type."""

    def test_reasoning_step_think(self):
        """Test think step structure."""
        step: ReasoningStep = {
            "type": "think",
            "content": "I need to check inventory levels",
            "tool_name": None,
            "tool_args": None,
            "timestamp": 1234567890.0
        }
        assert step["type"] == "think"
        assert step["content"] == "I need to check inventory levels"

    def test_reasoning_step_act(self):
        """Test act step structure."""
        step: ReasoningStep = {
            "type": "act",
            "content": "",
            "tool_name": "get_inventory_levels",
            "tool_args": {"warehouse_id": "WH-001"},
            "timestamp": 1234567890.0
        }
        assert step["type"] == "act"
        assert step["tool_name"] == "get_inventory_levels"

    def test_agent_state_has_reasoning_trace(self):
        """Test AgentState includes reasoning_trace field."""
        state: AgentState = {
            "messages": [],
            "current_agent": "router",
            "tool_calls": 0,
            "confidence": 1.0,
            "context": {},
            "plan": [],
            "step": 0,
            "plugin_context": None,
            "reasoning_trace": [],
            "session_id": None
        }
        assert "reasoning_trace" in state
        assert "session_id" in state
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_state.py -v`
Expected: FAIL with "cannot import name 'ReasoningStep' from 'agents.state'"

**Step 3: Write minimal implementation**

Modify `agents/state.py`:

```python
from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ReasoningStep(TypedDict):
    """A single step in the ReAct reasoning trace."""
    type: Literal["think", "act", "observe", "answer"]
    content: str
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    timestamp: float


class PluginContext(TypedDict, total=False):
    """
    Context for plugin system integration.
    """
    # Names of active plugins
    active_plugins: List[str]

    # Results from plugin tool calls
    tool_results: Dict[str, Any]

    # Data stored by hook handlers
    hook_data: Dict[str, Any]


class AgentState(TypedDict):
    """
    Shared state for the BestBox LangGraph agents.
    """
    # Conversation history (appended to by each node)
    messages: Annotated[List[BaseMessage], add_messages]

    # Current active sub-agent (erp, crm, it_ops, oa)
    current_agent: str

    # Counter for SLA monitoring (max 5 tool calls)
    tool_calls: int

    # Confidence score of the last decision (0.0 - 1.0)
    confidence: float

    # Retrieved context from RAG or other agents
    context: Dict[str, Any]

    # Plan for the current task (list of steps)
    plan: List[str]

    # Current step index in the plan
    step: int

    # Plugin system context
    plugin_context: Optional[PluginContext]

    # ReAct reasoning trace (new)
    reasoning_trace: Optional[List[ReasoningStep]]

    # Session ID for persistence (new)
    session_id: Optional[str]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_react_state.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/state.py tests/test_react_state.py
git commit -m "$(cat <<'EOF'
feat(agents): add ReasoningStep type and extend AgentState

Add ReasoningStep TypedDict for ReAct trace tracking.
Extend AgentState with reasoning_trace and session_id fields.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Create ReAct Node Core Logic

**Files:**
- Create: `agents/react_node.py`
- Test: `tests/test_react_node.py` (new)

**Step 1: Write the failing test**

Create `tests/test_react_node.py`:

```python
"""Tests for ReAct node."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agents.react_node import (
    ReActDecision,
    parse_react_response,
    build_react_prompt,
    REACT_MAX_ITERATIONS
)


class TestReActDecision:
    """Test ReActDecision parsing."""

    def test_parse_tool_action(self):
        """Test parsing a tool action response."""
        response = {
            "reasoning": "I need to check inventory",
            "action": "tool",
            "tool": "get_inventory_levels",
            "args": {"warehouse_id": "WH-001"},
            "response": None
        }
        decision = ReActDecision(**response)
        assert decision.action == "tool"
        assert decision.tool == "get_inventory_levels"

    def test_parse_answer_action(self):
        """Test parsing an answer response."""
        response = {
            "reasoning": "I have enough information",
            "action": "answer",
            "tool": None,
            "args": None,
            "response": "The inventory level is 100 units."
        }
        decision = ReActDecision(**response)
        assert decision.action == "answer"
        assert decision.response == "The inventory level is 100 units."


class TestBuildReactPrompt:
    """Test ReAct prompt building."""

    def test_prompt_includes_tools(self):
        """Test that prompt includes available tools."""
        prompt = build_react_prompt(
            question="What is the inventory level?",
            primary_domain="erp",
            secondary_domains=["itops"],
            reasoning_trace=[],
            all_tools=["get_inventory_levels", "search_knowledge_base"]
        )
        assert "get_inventory_levels" in prompt
        assert "erp" in prompt.lower()

    def test_prompt_includes_trace(self):
        """Test that prompt includes previous reasoning."""
        trace = [
            {"type": "think", "content": "First thought", "tool_name": None, "tool_args": None, "timestamp": 0}
        ]
        prompt = build_react_prompt(
            question="Follow up",
            primary_domain="erp",
            secondary_domains=[],
            reasoning_trace=trace,
            all_tools=[]
        )
        assert "First thought" in prompt


class TestParseReactResponse:
    """Test response parsing."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        text = '{"reasoning": "test", "action": "answer", "response": "done"}'
        decision = parse_react_response(text)
        assert decision.action == "answer"

    def test_parse_json_in_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        text = '```json\n{"reasoning": "test", "action": "answer", "response": "done"}\n```'
        decision = parse_react_response(text)
        assert decision.action == "answer"

    def test_parse_invalid_returns_answer(self):
        """Test that invalid JSON returns an answer action with the text."""
        text = "This is not JSON, just a plain answer."
        decision = parse_react_response(text)
        assert decision.action == "answer"
        assert "plain answer" in decision.response


class TestReActConfig:
    """Test ReAct configuration."""

    def test_max_iterations_default(self):
        """Test default max iterations."""
        assert REACT_MAX_ITERATIONS == 5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_node.py -v`
Expected: FAIL with "cannot import name 'ReActDecision' from 'agents.react_node'"

**Step 3: Write minimal implementation**

Create `agents/react_node.py`:

```python
"""
ReAct Node for BestBox Agents

Implements the Think → Act → Observe loop for reasoning-based agent behavior.
"""

import json
import re
import time
import logging
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from agents.state import AgentState, ReasoningStep

logger = logging.getLogger(__name__)

# Configuration
REACT_MAX_ITERATIONS = 5


class ReActDecision(BaseModel):
    """Structured output for ReAct reasoning step."""
    reasoning: str = Field(..., description="The agent's reasoning about what to do next")
    action: Literal["tool", "answer"] = Field(..., description="Whether to use a tool or provide final answer")
    tool: Optional[str] = Field(None, description="Tool name if action=tool")
    args: Optional[Dict[str, Any]] = Field(None, description="Tool arguments if action=tool")
    response: Optional[str] = Field(None, description="Final answer if action=answer")


REACT_SYSTEM_PROMPT = """You are an assistant that thinks step-by-step to answer questions.

Router analysis:
- Primary domain: {primary_domain}
- Secondary domains: {secondary_domains}
- This means you should prioritize {primary_domain} tools but can use others if needed.

Available tools (by relevance):

## {primary_domain} Tools (recommended)
{primary_tools}

## Other Tools (available if needed)
{other_tools}

Previous reasoning steps:
{reasoning_trace}

User question: {question}

Think through this step by step:
1. What information do I need?
2. Which tool can provide it?
3. Or do I have enough to answer?

Respond in JSON format:
{{
  "reasoning": "What I'm thinking and why...",
  "action": "tool" or "answer",
  "tool": "tool_name (if action=tool, else null)",
  "args": {{ ... }} (if action=tool, else null),
  "response": "final answer (if action=answer, else null)"
}}
"""


def build_react_prompt(
    question: str,
    primary_domain: str,
    secondary_domains: List[str],
    reasoning_trace: List[ReasoningStep],
    all_tools: List[str],
    tool_descriptions: Optional[Dict[str, str]] = None
) -> str:
    """
    Build the ReAct prompt with domain hints and tool listings.

    Args:
        question: User's question
        primary_domain: Primary domain from router
        secondary_domains: Secondary domains from router
        reasoning_trace: Previous reasoning steps
        all_tools: List of all available tool names
        tool_descriptions: Optional dict of tool name -> description

    Returns:
        Formatted prompt string
    """
    tool_descriptions = tool_descriptions or {}

    # Categorize tools by domain
    domain_tool_mapping = {
        "erp": ["get_purchase_orders", "get_inventory_levels", "get_financial_summary",
                "get_vendor_price_trends", "get_procurement_summary", "get_top_vendors"],
        "crm": ["get_leads", "get_customers", "get_deals", "get_sales_pipeline"],
        "itops": ["get_server_status", "get_alerts", "search_logs"],
        "oa": ["get_calendar", "get_emails", "schedule_meeting"],
        "general": ["search_knowledge_base"]
    }

    primary_tools = []
    other_tools = []

    for tool in all_tools:
        tool_line = f"- {tool}"
        if tool in tool_descriptions:
            tool_line += f": {tool_descriptions[tool]}"

        # Check if tool belongs to primary domain
        if tool in domain_tool_mapping.get(primary_domain, []):
            primary_tools.append(tool_line)
        elif tool == "search_knowledge_base":
            # Knowledge base is always available
            primary_tools.append(f"- search_knowledge_base(query, domain=\"{primary_domain}\")")
        else:
            other_tools.append(tool_line)

    # Format reasoning trace
    trace_text = "None yet." if not reasoning_trace else ""
    for step in reasoning_trace:
        if step["type"] == "think":
            trace_text += f"\n🤔 Think: {step['content']}"
        elif step["type"] == "act":
            trace_text += f"\n🔧 Act: {step['tool_name']}({step['tool_args']})"
        elif step["type"] == "observe":
            # Truncate long observations
            content = step["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            trace_text += f"\n📊 Observe: {content}"

    return REACT_SYSTEM_PROMPT.format(
        primary_domain=primary_domain,
        secondary_domains=", ".join(secondary_domains) if secondary_domains else "none",
        primary_tools="\n".join(primary_tools) if primary_tools else "None available",
        other_tools="\n".join(other_tools) if other_tools else "None",
        reasoning_trace=trace_text,
        question=question
    )


def parse_react_response(text: str) -> ReActDecision:
    """
    Parse LLM response into ReActDecision.
    Handles JSON in various formats (raw, markdown code blocks).
    Falls back to treating text as an answer if parsing fails.

    Args:
        text: Raw LLM response text

    Returns:
        ReActDecision object
    """
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # Try to find JSON object in text
    json_obj_match = re.search(r'\{[^{}]*"action"[^{}]*\}', text, re.DOTALL)
    if json_obj_match:
        text = json_obj_match.group(0)

    try:
        data = json.loads(text)
        return ReActDecision(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to parse ReAct response as JSON: {e}")
        # Fallback: treat the whole text as an answer
        return ReActDecision(
            reasoning="Response was not in expected JSON format",
            action="answer",
            tool=None,
            args=None,
            response=text.strip()
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_react_node.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/react_node.py tests/test_react_node.py
git commit -m "$(cat <<'EOF'
feat(agents): add ReAct node core types and prompt building

Add ReActDecision model for structured reasoning output.
Add build_react_prompt for constructing ReAct prompts with domain hints.
Add parse_react_response for robust JSON parsing with fallback.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Implement ReAct Execution Loop

**Files:**
- Modify: `agents/react_node.py`
- Test: `tests/test_react_node.py` (extend)

**Step 1: Write the failing test**

Add to `tests/test_react_node.py`:

```python
from agents.state import AgentState
from langchain_core.messages import HumanMessage


class TestReActExecution:
    """Test ReAct execution loop."""

    @patch('agents.react_node.get_llm')
    @patch('agents.react_node.execute_tool')
    def test_single_tool_then_answer(self, mock_execute_tool, mock_get_llm):
        """Test ReAct loop with one tool call then answer."""
        from agents.react_node import react_loop

        # Mock LLM responses
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            # First call: decide to use tool
            MagicMock(content='{"reasoning": "Need inventory", "action": "tool", "tool": "get_inventory_levels", "args": {"warehouse_id": "WH-001"}}'),
            # Second call: provide answer
            MagicMock(content='{"reasoning": "Got data", "action": "answer", "response": "Inventory is 100 units."}')
        ]
        mock_get_llm.return_value = mock_llm

        # Mock tool execution
        mock_execute_tool.return_value = '{"items": [{"sku": "A1", "quantity": 100}]}'

        state: AgentState = {
            "messages": [HumanMessage(content="What's the inventory?")],
            "current_agent": "react",
            "tool_calls": 0,
            "confidence": 1.0,
            "context": {"primary_domain": "erp", "secondary_domains": []},
            "plan": [],
            "step": 0,
            "plugin_context": None,
            "reasoning_trace": [],
            "session_id": "test-123"
        }

        result = react_loop(state, available_tools=["get_inventory_levels"])

        # Should have trace entries
        assert len(result["reasoning_trace"]) >= 3  # think, act, observe, think, answer
        assert result["reasoning_trace"][-1]["type"] == "answer"

    @patch('agents.react_node.get_llm')
    def test_max_iterations_reached(self, mock_get_llm):
        """Test that loop stops at max iterations."""
        from agents.react_node import react_loop, REACT_MAX_ITERATIONS

        mock_llm = MagicMock()
        # Always return tool action (never answer)
        mock_llm.invoke.return_value = MagicMock(
            content='{"reasoning": "Need more", "action": "tool", "tool": "search", "args": {}}'
        )
        mock_get_llm.return_value = mock_llm

        state: AgentState = {
            "messages": [HumanMessage(content="Test")],
            "current_agent": "react",
            "tool_calls": 0,
            "confidence": 1.0,
            "context": {"primary_domain": "general", "secondary_domains": []},
            "plan": [],
            "step": 0,
            "plugin_context": None,
            "reasoning_trace": [],
            "session_id": None
        }

        with patch('agents.react_node.execute_tool', return_value="result"):
            result = react_loop(state, available_tools=["search"])

        # Should not exceed max iterations (each iteration = think + act + observe)
        # Plus one final think that hits limit
        assert mock_llm.invoke.call_count <= REACT_MAX_ITERATIONS + 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_node.py::TestReActExecution -v`
Expected: FAIL with "cannot import name 'react_loop' from 'agents.react_node'"

**Step 3: Write minimal implementation**

Add to `agents/react_node.py`:

```python
from agents.utils import get_llm
from langchain_core.messages import HumanMessage, AIMessage


def execute_tool(tool_name: str, tool_args: Dict[str, Any], available_tools: Dict[str, Any]) -> str:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool
        available_tools: Dict mapping tool names to tool objects

    Returns:
        Tool execution result as string
    """
    if tool_name not in available_tools:
        return f"Error: Tool '{tool_name}' not found"

    tool = available_tools[tool_name]
    try:
        result = tool.invoke(tool_args)
        return str(result) if result is not None else "No result"
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return f"Error executing {tool_name}: {str(e)}"


def react_loop(
    state: AgentState,
    available_tools: List[str],
    tool_objects: Optional[Dict[str, Any]] = None
) -> AgentState:
    """
    Execute the ReAct reasoning loop.

    Think → Act → Observe → repeat until answer or max iterations.

    Args:
        state: Current agent state
        available_tools: List of available tool names
        tool_objects: Optional dict of tool name -> tool object for execution

    Returns:
        Updated state with reasoning_trace populated
    """
    tool_objects = tool_objects or {}

    # Extract question from messages
    question = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            question = msg.content
            break

    # Get domain hints from context
    context = state.get("context", {})
    primary_domain = context.get("primary_domain", "general")
    secondary_domains = context.get("secondary_domains", [])

    reasoning_trace: List[ReasoningStep] = list(state.get("reasoning_trace") or [])
    llm = get_llm(temperature=0.3)  # Lower temp for more consistent reasoning

    for iteration in range(REACT_MAX_ITERATIONS):
        # Build prompt with current trace
        prompt = build_react_prompt(
            question=question,
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            reasoning_trace=reasoning_trace,
            all_tools=available_tools
        )

        # Get LLM decision
        response = llm.invoke([("system", prompt), ("user", question)])
        decision = parse_react_response(response.content)

        # Record thinking
        reasoning_trace.append({
            "type": "think",
            "content": decision.reasoning,
            "tool_name": None,
            "tool_args": None,
            "timestamp": time.time()
        })

        if decision.action == "answer":
            # Final answer
            reasoning_trace.append({
                "type": "answer",
                "content": decision.response or "",
                "tool_name": None,
                "tool_args": None,
                "timestamp": time.time()
            })
            break

        elif decision.action == "tool" and decision.tool:
            # Record action
            reasoning_trace.append({
                "type": "act",
                "content": "",
                "tool_name": decision.tool,
                "tool_args": decision.args or {},
                "timestamp": time.time()
            })

            # Execute tool
            result = execute_tool(decision.tool, decision.args or {}, tool_objects)

            # Record observation
            reasoning_trace.append({
                "type": "observe",
                "content": result,
                "tool_name": None,
                "tool_args": None,
                "timestamp": time.time()
            })

    else:
        # Max iterations reached without answer
        reasoning_trace.append({
            "type": "answer",
            "content": "I've gathered information but reached my reasoning limit. Based on what I found: " +
                       (reasoning_trace[-1]["content"] if reasoning_trace else "No information gathered."),
            "tool_name": None,
            "tool_args": None,
            "timestamp": time.time()
        })

    return {
        **state,
        "reasoning_trace": reasoning_trace
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_react_node.py::TestReActExecution -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/react_node.py tests/test_react_node.py
git commit -m "$(cat <<'EOF'
feat(agents): implement ReAct execution loop

Add react_loop function with Think→Act→Observe cycle.
Add execute_tool helper for running tools by name.
Handles max iterations and graceful fallback.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update Router for Secondary Domains

**Files:**
- Modify: `agents/router.py:10-17`
- Test: `tests/test_router_hybrid.py` (new)

**Step 1: Write the failing test**

Create `tests/test_router_hybrid.py`:

```python
"""Tests for hybrid router with secondary domains."""

import pytest
from unittest.mock import patch, MagicMock
from agents.router import RouteDecision


class TestRouteDecisionHybrid:
    """Test extended RouteDecision with secondary domains."""

    def test_route_decision_has_secondary_domains(self):
        """Test that RouteDecision includes secondary_domains."""
        decision = RouteDecision(
            destination="erp_agent",
            reasoning="User asks about procurement",
            secondary_domains=["itops"]
        )
        assert decision.secondary_domains == ["itops"]

    def test_route_decision_empty_secondary(self):
        """Test RouteDecision with no secondary domains."""
        decision = RouteDecision(
            destination="crm_agent",
            reasoning="Pure CRM query"
        )
        assert decision.secondary_domains == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_hybrid.py -v`
Expected: FAIL (secondary_domains not in RouteDecision)

**Step 3: Write minimal implementation**

Modify `agents/router.py`:

```python
from typing import Literal, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.state import AgentState
from agents.utils import get_llm
from agents.context_manager import apply_sliding_window


class RouteDecision(BaseModel):
    """Decision on which agent to route the request to."""
    destination: Literal["erp_agent", "crm_agent", "it_ops_agent", "oa_agent", "mold_agent", "general_agent", "fallback"] = Field(
        ...,
        description="The target agent to handle the user request."
    )
    reasoning: str = Field(..., description="The reasoning behind the routing decision.")
    secondary_domains: List[str] = Field(
        default_factory=list,
        description="Secondary domains that might be needed (e.g., ['itops'] if user asks about policy)"
    )


ROUTER_SYSTEM_PROMPT = """You are the BestBox Router. Route user requests to the correct agent.

Agents:
- erp_agent: Finance, procurement, inventory, invoices, vendors, suppliers, costs, P&L
- crm_agent: Sales, leads, customers, deals, opportunities, revenue, churn
- it_ops_agent: Servers, errors, logs, alerts, IT system issues, maintenance
- oa_agent: Emails, scheduling, meetings, calendar, documents, leave requests
- mold_agent: Mold troubleshooting, manufacturing defects, product quality issues (披锋/flash, 拉白/whitening, 火花纹/spark marks, 模具/mold problems, 表面污染/contamination, trial results T0/T1/T2)
- general_agent: Greetings, help requests, cross-domain, policies, AI system questions

Rules:
- Vendors/suppliers → erp_agent
- Greetings/help/Hudson Group → general_agent
- Manufacturing/mold/product defects → mold_agent
- Only use fallback for completely unrelated requests

For secondary_domains: If the question might need information from multiple domains, list the secondary ones.
Example: "What's our procurement policy?" → destination=erp_agent, secondary_domains=["itops"] (policy docs)
"""


def router_node(state: AgentState):
    """
    Analyzes the latest message and decides the next agent.
    Uses context management to prevent context overflow.
    """
    llm = get_llm(temperature=0.1)
    structured_llm = llm.with_structured_output(RouteDecision)

    messages = apply_sliding_window(
        state["messages"],
        max_tokens=1500,
        max_messages=3,
        keep_system=False
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])

    chain = prompt | structured_llm

    try:
        decision: RouteDecision = chain.invoke({"messages": messages})
        return {
            "current_agent": decision.destination,
            "confidence": 1.0,
            "context": {
                "primary_domain": decision.destination.replace("_agent", ""),
                "secondary_domains": decision.secondary_domains,
                "router_reasoning": decision.reasoning
            }
        }
    except Exception as e:
        print(f"Router failed: {e}")
        return {
            "current_agent": "general_agent",
            "confidence": 0.0,
            "context": {
                "primary_domain": "general",
                "secondary_domains": [],
                "router_reasoning": "Fallback due to routing error"
            }
        }


def route_decision(state: AgentState) -> str:
    """Conditional edge function to determine the next node."""
    return state["current_agent"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router_hybrid.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/router.py tests/test_router_hybrid.py
git commit -m "$(cat <<'EOF'
feat(router): add secondary_domains for cross-domain queries

Extend RouteDecision with secondary_domains field.
Update router to populate context with domain hints.
Enables ReAct node to access cross-domain tools.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Create Session Store

**Files:**
- Create: `services/session_store.py`
- Test: `tests/test_session_store.py` (new)

**Step 1: Write the failing test**

Create `tests/test_session_store.py`:

```python
"""Tests for session storage."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestSessionStore:
    """Test SessionStore interface."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation."""
        from services.session_store import SessionStore

        with patch('services.session_store.asyncpg') as mock_pg:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value="session-uuid-123")
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()

            store = SessionStore(pool=mock_pool)
            session_id = await store.create_session(user_id="user1", channel="web")

            assert session_id == "session-uuid-123"

    @pytest.mark.asyncio
    async def test_add_message(self):
        """Test adding message to session."""
        from services.session_store import SessionStore

        with patch('services.session_store.asyncpg') as mock_pg:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()

            store = SessionStore(pool=mock_pool)
            await store.add_message(
                session_id="session-123",
                role="user",
                content="Hello",
                reasoning_trace=None,
                metrics={"latency_ms": 100}
            )

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing sessions."""
        from services.session_store import SessionStore

        with patch('services.session_store.asyncpg') as mock_pg:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[
                {"id": "s1", "user_id": "u1", "status": "active"},
                {"id": "s2", "user_id": "u2", "status": "completed"}
            ])
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()

            store = SessionStore(pool=mock_pool)
            sessions = await store.list_sessions(limit=10)

            assert len(sessions) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_store.py -v`
Expected: FAIL with "cannot import name 'SessionStore' from 'services.session_store'"

**Step 3: Write minimal implementation**

Create `services/session_store.py`:

```python
"""
Session Store for BestBox Agent Conversations

Persists conversation sessions with reasoning traces to PostgreSQL.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionStore:
    """
    PostgreSQL-backed session storage for agent conversations.
    """

    def __init__(self, pool):
        """
        Initialize with asyncpg connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self.pool = pool

    async def create_session(
        self,
        user_id: str,
        channel: str = "web",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new conversation session.

        Args:
            user_id: User identifier
            channel: Channel (web, api, etc.)
            metadata: Optional metadata dict

        Returns:
            Session ID (UUID string)
        """
        async with self.pool.acquire() as conn:
            session_id = await conn.fetchval("""
                INSERT INTO sessions (user_id, channel, metadata)
                VALUES ($1, $2, $3)
                RETURNING id::text
            """, user_id, channel, json.dumps(metadata or {}))
            return session_id

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        reasoning_trace: Optional[List[Dict]] = None,
        tool_calls: Optional[List[Dict]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """
        Add a message to a session.

        Args:
            session_id: Session UUID
            role: Message role (user, assistant, tool)
            content: Message content
            reasoning_trace: ReAct reasoning steps (for assistant messages)
            tool_calls: Tool calls made
            metrics: Performance metrics (latency_ms, tokens, etc.)
        """
        metrics = metrics or {}

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO session_messages (
                    session_id, role, content, reasoning_trace, tool_calls,
                    tokens_prompt, tokens_completion, latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                session_id,
                role,
                content,
                json.dumps(reasoning_trace) if reasoning_trace else None,
                json.dumps(tool_calls) if tool_calls else None,
                metrics.get("tokens_prompt"),
                metrics.get("tokens_completion"),
                metrics.get("latency_ms")
            )

            # Update session message count
            await conn.execute("""
                UPDATE sessions
                SET message_count = message_count + 1
                WHERE id = $1
            """, session_id)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a session with all its messages.

        Args:
            session_id: Session UUID

        Returns:
            Session dict with messages, or None if not found
        """
        async with self.pool.acquire() as conn:
            session = await conn.fetchrow("""
                SELECT id::text, user_id, channel, started_at, ended_at,
                       message_count, status, rating, rating_note, metadata
                FROM sessions WHERE id = $1
            """, session_id)

            if not session:
                return None

            messages = await conn.fetch("""
                SELECT id::text, role, content, reasoning_trace, tool_calls,
                       tokens_prompt, tokens_completion, latency_ms, created_at
                FROM session_messages
                WHERE session_id = $1
                ORDER BY created_at
            """, session_id)

            return {
                **dict(session),
                "messages": [dict(m) for m in messages]
            }

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List sessions with optional filters.

        Args:
            limit: Max results
            offset: Pagination offset
            user_id: Filter by user
            status: Filter by status

        Returns:
            List of session summaries
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT id::text, user_id, channel, started_at,
                       message_count, status, rating
                FROM sessions
                WHERE 1=1
            """
            params = []

            if user_id:
                params.append(user_id)
                query += f" AND user_id = ${len(params)}"

            if status:
                params.append(status)
                query += f" AND status = ${len(params)}"

            query += " ORDER BY started_at DESC"

            params.extend([limit, offset])
            query += f" LIMIT ${len(params)-1} OFFSET ${len(params)}"

            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def update_session_status(self, session_id: str, status: str):
        """Update session status."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE sessions SET status = $1, ended_at = NOW()
                WHERE id = $2
            """, status, session_id)

    async def add_rating(
        self,
        session_id: str,
        rating: str,
        note: Optional[str] = None
    ):
        """Add admin rating to session."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE sessions SET rating = $1, rating_note = $2
                WHERE id = $3
            """, rating, note, session_id)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_session_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/session_store.py tests/test_session_store.py
git commit -m "$(cat <<'EOF'
feat(services): add PostgreSQL session store

Add SessionStore class for persisting conversation sessions.
Supports create, add_message, get, list, and rating operations.
Stores ReAct reasoning traces as JSONB.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Create Database Migration

**Files:**
- Create: `migrations/001_add_sessions.sql`

**Step 1: Write the migration file**

Create `migrations/001_add_sessions.sql`:

```sql
-- Session Storage for ReAct Agent Conversations
-- Run: psql -h localhost -U bestbox -d bestbox -f migrations/001_add_sessions.sql

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    channel VARCHAR(50) DEFAULT 'web',
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    message_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    rating VARCHAR(10),
    rating_note TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Session messages table
CREATE TABLE IF NOT EXISTS session_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    reasoning_trace JSONB,
    tool_calls JSONB,
    tokens_prompt INT,
    tokens_completion INT,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id);

-- Comment
COMMENT ON TABLE sessions IS 'ReAct agent conversation sessions';
COMMENT ON TABLE session_messages IS 'Individual messages within sessions, including reasoning traces';
```

**Step 2: Commit**

```bash
mkdir -p migrations
git add migrations/001_add_sessions.sql
git commit -m "$(cat <<'EOF'
feat(db): add session storage migration

Create sessions and session_messages tables.
Supports ReAct reasoning traces as JSONB.
Includes indexes for user, status, and date queries.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Add ReAct Graph to LangGraph

**Files:**
- Modify: `agents/graph.py`
- Test: `tests/test_react_graph.py` (new)

**Step 1: Write the failing test**

Create `tests/test_react_graph.py`:

```python
"""Tests for ReAct graph integration."""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage


class TestReActGraph:
    """Test ReAct graph exists and is compilable."""

    def test_react_app_exists(self):
        """Test that react_app is exported from graph module."""
        from agents.graph import react_app
        assert react_app is not None

    def test_react_app_is_compiled(self):
        """Test that react_app is a compiled graph."""
        from agents.graph import react_app
        # Compiled graphs have an invoke method
        assert hasattr(react_app, 'invoke') or hasattr(react_app, 'ainvoke')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_graph.py -v`
Expected: FAIL with "cannot import name 'react_app' from 'agents.graph'"

**Step 3: Write minimal implementation**

Add to `agents/graph.py` (after existing code):

```python
# ============================================================
# ReAct Graph (Parallel Path)
# ============================================================

from agents.react_node import react_loop, REACT_MAX_ITERATIONS

def react_node_wrapper(state: AgentState):
    """
    Wrapper that runs ReAct loop with all available tools.
    """
    # Collect all tool names and objects
    tool_names = [t.name for t in UNIQUE_TOOLS]
    tool_objects = {t.name: t for t in UNIQUE_TOOLS}

    # Run ReAct loop
    result = react_loop(state, available_tools=tool_names, tool_objects=tool_objects)

    # Extract final answer from reasoning trace
    reasoning_trace = result.get("reasoning_trace", [])
    final_answer = ""
    for step in reversed(reasoning_trace):
        if step["type"] == "answer":
            final_answer = step["content"]
            break

    # Add assistant message with final answer
    return {
        **result,
        "messages": [AIMessage(content=final_answer)],
        "current_agent": "react"
    }


# Build ReAct graph
react_workflow = StateGraph(AgentState)

# Add nodes
react_workflow.add_node("router", router_node_with_hooks)
react_workflow.add_node("react", react_node_wrapper)
react_workflow.add_node("fallback", fallback_node)

# Set entry point
react_workflow.set_entry_point("router")

# Router -> ReAct or Fallback
def route_to_react_or_fallback(state: AgentState) -> str:
    """Route to ReAct node unless fallback is needed."""
    current = state.get("current_agent", "")
    if current == "fallback":
        return "fallback"
    return "react"

react_workflow.add_conditional_edges(
    "router",
    route_to_react_or_fallback,
    {
        "react": "react",
        "fallback": "fallback"
    }
)

react_workflow.add_edge("react", END)
react_workflow.add_edge("fallback", END)

# Compile ReAct graph
react_app = react_workflow.compile()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_react_graph.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/graph.py tests/test_react_graph.py
git commit -m "$(cat <<'EOF'
feat(agents): add parallel ReAct graph

Create react_app as separate compiled graph.
Routes through router then to ReAct node.
Wraps react_loop with tool objects from ALL_TOOLS.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Add /chat/react API Endpoint

**Files:**
- Modify: `services/agent_api.py`
- Test: `tests/test_api_react.py` (new)

**Step 1: Write the failing test**

Create `tests/test_api_react.py`:

```python
"""Tests for ReAct API endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


class TestReActEndpoint:
    """Test /chat/react endpoint."""

    @patch('services.agent_api.react_app')
    def test_react_endpoint_exists(self, mock_react):
        """Test that /chat/react endpoint exists."""
        from services.agent_api import app
        client = TestClient(app)

        mock_react.ainvoke = AsyncMock(return_value={
            "messages": [MagicMock(content="Test response")],
            "current_agent": "react",
            "reasoning_trace": [
                {"type": "think", "content": "Thinking...", "timestamp": 0},
                {"type": "answer", "content": "Test response", "timestamp": 1}
            ]
        })

        response = client.post(
            "/chat/react",
            json={"messages": [{"role": "user", "content": "Hello"}]}
        )

        assert response.status_code == 200
        data = response.json()
        assert "reasoning_trace" in data

    @patch('services.agent_api.react_app')
    def test_react_streams_reasoning(self, mock_react):
        """Test that streaming includes reasoning steps."""
        from services.agent_api import app
        client = TestClient(app)

        mock_react.ainvoke = AsyncMock(return_value={
            "messages": [MagicMock(content="Answer")],
            "current_agent": "react",
            "reasoning_trace": [
                {"type": "think", "content": "Let me check", "timestamp": 0},
                {"type": "act", "content": "", "tool_name": "search", "tool_args": {}, "timestamp": 1},
                {"type": "observe", "content": "Found data", "timestamp": 2},
                {"type": "answer", "content": "Answer", "timestamp": 3}
            ]
        })

        response = client.post(
            "/chat/react",
            json={"messages": [{"role": "user", "content": "Test"}], "stream": True}
        )

        assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_react.py -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Write minimal implementation**

Add to `services/agent_api.py` (after existing imports):

```python
from agents.graph import react_app
```

Add new endpoint (before `if __name__ == "__main__":`):

```python
@app.post("/chat/react")
async def chat_react_endpoint(
    request: ChatRequest,
    user_id: str = Header(default="anonymous", alias="x-user-id")
):
    """
    ReAct endpoint with visible reasoning trace.

    Returns reasoning steps (think, act, observe, answer) alongside the response.
    """
    start_time = time.time()

    # Handle streaming
    if request.stream:
        return await chat_react_stream(request, user_id)

    # Parse messages
    messages_to_process = []
    if request.messages:
        messages_to_process = request.messages
    elif request.input:
        for item in request.input:
            if isinstance(item, dict) and "role" in item:
                content = item.get("content", "")
                msg = ChatMessage(role=item["role"], content=content)
                messages_to_process.append(msg)

    if not messages_to_process:
        raise HTTPException(status_code=422, detail="No messages provided")

    # Convert to LangChain messages
    lc_messages = []
    for msg in messages_to_process:
        content_text = parse_message_content(msg.content) if msg.content else ""
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content_text))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=content_text))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=content_text))

    # Build initial state
    inputs: AgentState = {
        "messages": lc_messages,
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0,
        "plugin_context": None,
        "reasoning_trace": [],
        "session_id": request.thread_id or str(uuid.uuid4())
    }

    try:
        # Run ReAct graph
        result = await react_app.ainvoke(cast(AgentState, inputs))

        last_msg = result["messages"][-1]
        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        reasoning_trace = result.get("reasoning_trace", [])

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "id": f"react-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "bestbox-react",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content or ""
                },
                "finish_reason": "stop"
            }],
            "reasoning_trace": reasoning_trace,
            "latency_ms": latency_ms,
            "session_id": inputs["session_id"]
        }

    except Exception as e:
        logger.error(f"ReAct execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def chat_react_stream(request: ChatRequest, user_id: str):
    """Stream ReAct response with reasoning steps."""
    async def generate():
        # Similar setup as non-streaming...
        messages_to_process = request.messages or []
        lc_messages = []
        for msg in messages_to_process:
            content_text = parse_message_content(msg.content) if msg.content else ""
            if msg.role == "user":
                lc_messages.append(HumanMessage(content=content_text))

        inputs: AgentState = {
            "messages": lc_messages,
            "current_agent": "router",
            "tool_calls": 0,
            "confidence": 1.0,
            "context": {},
            "plan": [],
            "step": 0,
            "plugin_context": None,
            "reasoning_trace": [],
            "session_id": request.thread_id or str(uuid.uuid4())
        }

        try:
            result = await react_app.ainvoke(cast(AgentState, inputs))
            reasoning_trace = result.get("reasoning_trace", [])

            # Stream reasoning steps
            for step in reasoning_trace:
                event = {
                    "type": "reasoning_step",
                    "step": step
                }
                yield f"data: {json.dumps(event)}\n\n"

            # Final response
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, 'content') else ""

            final = {
                "type": "response.completed",
                "content": content,
                "reasoning_trace": reasoning_trace
            }
            yield f"data: {json.dumps(final)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            error = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_react.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/agent_api.py tests/test_api_react.py
git commit -m "$(cat <<'EOF'
feat(api): add /chat/react endpoint with reasoning trace

Add ReAct endpoint that returns visible reasoning steps.
Supports both streaming and non-streaming responses.
Streams reasoning_step events for real-time trace display.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Add Admin API Endpoints

**Files:**
- Modify: `services/agent_api.py`
- Test: `tests/test_api_admin.py` (new)

**Step 1: Write the failing test**

Create `tests/test_api_admin.py`:

```python
"""Tests for admin API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


class TestAdminEndpoints:
    """Test /admin/* endpoints."""

    @patch('services.agent_api.session_store')
    def test_list_sessions(self, mock_store):
        """Test GET /admin/sessions."""
        from services.agent_api import app
        client = TestClient(app)

        mock_store.list_sessions = AsyncMock(return_value=[
            {"id": "s1", "user_id": "u1", "status": "active"}
        ])

        response = client.get(
            "/admin/sessions",
            headers={"admin-token": "test-token"}
        )

        assert response.status_code == 200

    @patch('services.agent_api.session_store')
    def test_get_session_detail(self, mock_store):
        """Test GET /admin/sessions/{id}."""
        from services.agent_api import app
        client = TestClient(app)

        mock_store.get_session = AsyncMock(return_value={
            "id": "s1",
            "messages": [{"role": "user", "content": "Hello"}],
            "reasoning_trace": []
        })

        response = client.get(
            "/admin/sessions/s1",
            headers={"admin-token": "test-token"}
        )

        assert response.status_code == 200

    @patch('services.agent_api.session_store')
    def test_rate_session(self, mock_store):
        """Test POST /admin/sessions/{id}/rating."""
        from services.agent_api import app
        client = TestClient(app)

        mock_store.add_rating = AsyncMock()

        response = client.post(
            "/admin/sessions/s1/rating",
            json={"rating": "good", "note": "Great response"},
            headers={"admin-token": "test-token"}
        )

        assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_admin.py -v`
Expected: FAIL with 404

**Step 3: Write minimal implementation**

Add to `services/agent_api.py`:

```python
from services.session_store import SessionStore

# Global session store instance (initialized at startup)
session_store: Optional[SessionStore] = None

# Update startup event
@app.on_event("startup")
async def startup():
    global db_pool, session_store
    # ... existing code ...

    # Initialize session store
    if db_pool:
        session_store = SessionStore(pool=db_pool)
        logger.info("✅ Session store initialized")


def verify_admin_token(token: str):
    """Verify admin token."""
    expected = os.getenv("ADMIN_TOKEN", "dev-admin-token")
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


class SessionRatingRequest(BaseModel):
    rating: str
    note: Optional[str] = None


@app.get("/admin/sessions")
async def admin_list_sessions(
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    admin_token: str = Header(...)
):
    """List sessions for admin review."""
    verify_admin_token(admin_token)

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not available")

    return await session_store.list_sessions(limit, offset, user_id, status)


@app.get("/admin/sessions/{session_id}")
async def admin_get_session(
    session_id: str,
    admin_token: str = Header(...)
):
    """Get full session with messages and reasoning traces."""
    verify_admin_token(admin_token)

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not available")

    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@app.post("/admin/sessions/{session_id}/rating")
async def admin_rate_session(
    session_id: str,
    request: SessionRatingRequest,
    admin_token: str = Header(...)
):
    """Admin rates a session for quality tracking."""
    verify_admin_token(admin_token)

    if request.rating not in ["good", "bad"]:
        raise HTTPException(status_code=400, detail="Rating must be 'good' or 'bad'")

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not available")

    await session_store.add_rating(session_id, request.rating, request.note)
    return {"status": "ok", "session_id": session_id, "rating": request.rating}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_admin.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/agent_api.py tests/test_api_admin.py
git commit -m "$(cat <<'EOF'
feat(api): add admin endpoints for session review

Add GET /admin/sessions for listing sessions.
Add GET /admin/sessions/{id} for session detail with traces.
Add POST /admin/sessions/{id}/rating for quality rating.
Requires admin-token header for authentication.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Create ReasoningTrace Frontend Component

**Files:**
- Create: `frontend/copilot-demo/components/ReasoningTrace.tsx`

**Step 1: Create component**

```tsx
"use client";

import React from "react";

interface ReasoningStep {
  type: "think" | "act" | "observe" | "answer";
  content: string;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  timestamp: number;
}

interface ReasoningTraceProps {
  steps: ReasoningStep[];
  isStreaming?: boolean;
}

function formatArgs(args?: Record<string, unknown>): string {
  if (!args || Object.keys(args).length === 0) return "";
  return JSON.stringify(args, null, 0).slice(0, 100);
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function ReasoningTrace({ steps, isStreaming = false }: ReasoningTraceProps) {
  if (!steps || steps.length === 0) {
    return null;
  }

  return (
    <div className="reasoning-trace border-l-2 border-blue-300 pl-4 my-4 space-y-2 text-sm">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
        Reasoning Trace {isStreaming && <span className="animate-pulse">●</span>}
      </div>
      {steps.map((step, i) => (
        <div
          key={i}
          className={`step step-${step.type} flex items-start gap-2 py-1`}
        >
          {step.type === "think" && (
            <>
              <span className="icon text-yellow-500">🤔</span>
              <span className="text-gray-700">
                <strong>Thinking:</strong> {step.content}
              </span>
            </>
          )}
          {step.type === "act" && (
            <>
              <span className="icon text-blue-500">🔧</span>
              <span className="text-gray-700">
                <strong>Action:</strong>{" "}
                <code className="bg-gray-100 px-1 rounded">
                  {step.tool_name}({formatArgs(step.tool_args)})
                </code>
              </span>
            </>
          )}
          {step.type === "observe" && (
            <>
              <span className="icon text-green-500">📊</span>
              <span className="text-gray-700">
                <strong>Observation:</strong> {truncate(step.content, 200)}
              </span>
            </>
          )}
          {step.type === "answer" && (
            <>
              <span className="icon text-purple-500">💡</span>
              <span className="text-gray-700">
                <strong>Answer:</strong> {step.content}
              </span>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

export default ReasoningTrace;
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/ReasoningTrace.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add ReasoningTrace component

Display ReAct reasoning steps with icons.
Supports streaming indicator.
Truncates long observations.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Create Admin Page

**Files:**
- Create: `frontend/copilot-demo/app/admin/page.tsx`

**Step 1: Create admin page**

```tsx
"use client";

import React, { useEffect, useState } from "react";
import { ReasoningTrace } from "@/components/ReasoningTrace";

interface Session {
  id: string;
  user_id: string;
  channel: string;
  started_at: string;
  message_count: number;
  status: string;
  rating?: string;
}

interface SessionDetail extends Session {
  messages: Array<{
    role: string;
    content: string;
    reasoning_trace?: Array<{
      type: "think" | "act" | "observe" | "answer";
      content: string;
      tool_name?: string;
      tool_args?: Record<string, unknown>;
      timestamp: number;
    }>;
    latency_ms?: number;
    created_at: string;
  }>;
}

export default function AdminPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const adminToken = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "dev-admin-token";
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchSessions();
  }, []);

  async function fetchSessions() {
    try {
      const res = await fetch(`${apiBase}/admin/sessions?limit=50`, {
        headers: { "admin-token": adminToken },
      });
      if (!res.ok) throw new Error("Failed to fetch sessions");
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function fetchSessionDetail(sessionId: string) {
    try {
      const res = await fetch(`${apiBase}/admin/sessions/${sessionId}`, {
        headers: { "admin-token": adminToken },
      });
      if (!res.ok) throw new Error("Failed to fetch session");
      const data = await res.json();
      setSelectedSession(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  async function rateSession(sessionId: string, rating: "good" | "bad") {
    try {
      await fetch(`${apiBase}/admin/sessions/${sessionId}/rating`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "admin-token": adminToken,
        },
        body: JSON.stringify({ rating }),
      });
      fetchSessions(); // Refresh list
      if (selectedSession?.id === sessionId) {
        fetchSessionDetail(sessionId); // Refresh detail
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (error) {
    return <div className="p-8 text-red-500">Error: {error}</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-xl font-semibold">BestBox Admin - Session Monitor</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Session List */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="font-medium mb-4">Sessions ({sessions.length})</h2>
            <div className="space-y-2 max-h-[600px] overflow-auto">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => fetchSessionDetail(session.id)}
                  className={`p-3 border rounded cursor-pointer hover:bg-gray-50 ${
                    selectedSession?.id === session.id ? "border-blue-500 bg-blue-50" : ""
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-sm text-gray-500">
                        {new Date(session.started_at).toLocaleString()}
                      </span>
                      <div className="text-sm">User: {session.user_id}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          session.status === "active"
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {session.status}
                      </span>
                      {session.rating && (
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            session.rating === "good"
                              ? "bg-green-100 text-green-700"
                              : "bg-red-100 text-red-700"
                          }`}
                        >
                          {session.rating === "good" ? "👍" : "👎"}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {session.message_count} messages
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Session Detail */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="font-medium mb-4">Session Detail</h2>
            {selectedSession ? (
              <div>
                <div className="flex gap-2 mb-4">
                  <button
                    onClick={() => rateSession(selectedSession.id, "good")}
                    className="px-3 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
                  >
                    👍 Good
                  </button>
                  <button
                    onClick={() => rateSession(selectedSession.id, "bad")}
                    className="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                  >
                    👎 Bad
                  </button>
                </div>

                <div className="space-y-4 max-h-[500px] overflow-auto">
                  {selectedSession.messages.map((msg, i) => (
                    <div key={i} className="border-b pb-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            msg.role === "user"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-purple-100 text-purple-700"
                          }`}
                        >
                          {msg.role}
                        </span>
                        {msg.latency_ms && (
                          <span className="text-xs text-gray-400">
                            {msg.latency_ms}ms
                          </span>
                        )}
                      </div>
                      <div className="text-sm">{msg.content}</div>
                      {msg.reasoning_trace && msg.reasoning_trace.length > 0 && (
                        <ReasoningTrace steps={msg.reasoning_trace} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-gray-500">Select a session to view details</div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/app/admin/page.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add admin session review page

Add /admin page for reviewing conversation sessions.
Shows session list with status and rating.
Displays full message history with reasoning traces.
Supports good/bad rating buttons.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Add Context Compression

**Files:**
- Modify: `agents/context_manager.py`
- Test: `tests/test_context_compression.py` (new)

**Step 1: Write the failing test**

Create `tests/test_context_compression.py`:

```python
"""Tests for context compression."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage


class TestContextCompression:
    """Test context compression functionality."""

    @pytest.mark.asyncio
    async def test_no_compression_when_under_budget(self):
        """Test that messages are not compressed when under token budget."""
        from agents.context_manager import compress_if_needed

        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]

        result = await compress_if_needed(messages, token_budget=6000)

        assert len(result) == 2  # No compression

    @pytest.mark.asyncio
    @patch('agents.context_manager.get_llm')
    async def test_compression_when_over_budget(self, mock_get_llm):
        """Test that old messages are summarized when over budget."""
        from agents.context_manager import compress_if_needed

        # Mock LLM for summarization
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Summary of conversation"))
        mock_get_llm.return_value = mock_llm

        # Create many messages to exceed budget
        messages = [
            HumanMessage(content="Message " + "x" * 500)
            for _ in range(20)
        ]

        result = await compress_if_needed(messages, token_budget=1000, keep_recent=4)

        # Should have summary + recent messages
        assert len(result) <= 5  # 1 summary + 4 recent
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compression.py -v`
Expected: FAIL with "cannot import name 'compress_if_needed'"

**Step 3: Write minimal implementation**

Add to `agents/context_manager.py`:

```python
from agents.utils import get_llm

COMPRESSION_PROMPT = """Summarize this conversation history concisely.
Preserve key facts, decisions, and context needed to continue the conversation.

Conversation:
{messages}

Summary (be concise, focus on key points):"""


def format_messages_for_summary(messages: List[BaseMessage]) -> str:
    """Format messages for summarization prompt."""
    lines = []
    for msg in messages:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        content = msg.content[:500] if len(msg.content) > 500 else msg.content
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def compress_if_needed(
    messages: List[BaseMessage],
    token_budget: int = 6000,
    keep_recent: int = 4
) -> List[BaseMessage]:
    """
    Compress conversation history if it exceeds token budget.

    Strategy:
    - Keep last `keep_recent` messages intact
    - Summarize older messages into a single system message

    Args:
        messages: Full conversation history
        token_budget: Maximum tokens to allow
        keep_recent: Number of recent messages to preserve

    Returns:
        Compressed message list
    """
    # Estimate current token usage
    current_tokens = sum(estimate_message_tokens(m) for m in messages)

    if current_tokens <= token_budget:
        return messages  # No compression needed

    if len(messages) <= keep_recent:
        return messages  # Can't compress further

    # Split messages
    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # Summarize old messages
    llm = get_llm(temperature=0.3)
    prompt = COMPRESSION_PROMPT.format(
        messages=format_messages_for_summary(old_messages)
    )

    try:
        response = await llm.ainvoke([("system", prompt)])
        summary = response.content
    except Exception as e:
        logger.warning(f"Compression failed: {e}, using truncation instead")
        summary = f"[Earlier conversation with {len(old_messages)} messages]"

    # Return summary + recent
    return [
        SystemMessage(content=f"Previous conversation summary:\n{summary}"),
        *recent_messages
    ]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compression.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/context_manager.py tests/test_context_compression.py
git commit -m "$(cat <<'EOF'
feat(agents): add context compression for long conversations

Add compress_if_needed async function.
Summarizes old messages when token budget exceeded.
Preserves recent messages for context continuity.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Integration Test

**Files:**
- Create: `tests/test_react_integration.py`

**Step 1: Write integration test**

```python
"""Integration tests for ReAct system."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import HumanMessage


class TestReActIntegration:
    """End-to-end tests for ReAct flow."""

    @pytest.mark.asyncio
    @patch('agents.react_node.get_llm')
    async def test_full_react_flow(self, mock_get_llm):
        """Test complete ReAct flow from router to answer."""
        from agents.graph import react_app
        from agents.state import AgentState

        # Mock LLM responses
        mock_llm = MagicMock()
        call_count = [0]

        def mock_invoke(messages):
            call_count[0] += 1
            if call_count[0] == 1:
                # Router response
                return MagicMock(destination="erp_agent", reasoning="ERP query", secondary_domains=[])
            elif call_count[0] == 2:
                # ReAct think + tool
                return MagicMock(content='{"reasoning": "Check inventory", "action": "tool", "tool": "get_inventory_levels", "args": {"warehouse_id": "WH-001"}}')
            else:
                # ReAct answer
                return MagicMock(content='{"reasoning": "Got data", "action": "answer", "response": "Inventory is 100 units."}')

        mock_llm.invoke = mock_invoke
        mock_llm.with_structured_output = MagicMock(return_value=mock_llm)
        mock_get_llm.return_value = mock_llm

        # Mock tool execution
        with patch('agents.react_node.execute_tool', return_value='{"items": [{"quantity": 100}]}'):
            state: AgentState = {
                "messages": [HumanMessage(content="What's the inventory level?")],
                "current_agent": "router",
                "tool_calls": 0,
                "confidence": 1.0,
                "context": {},
                "plan": [],
                "step": 0,
                "plugin_context": None,
                "reasoning_trace": [],
                "session_id": "test-123"
            }

            result = await react_app.ainvoke(state)

            # Verify result
            assert "reasoning_trace" in result
            assert len(result["reasoning_trace"]) > 0
            assert result["messages"][-1].content  # Has final answer

    def test_reasoning_trace_structure(self):
        """Test that reasoning trace has correct structure."""
        from agents.state import ReasoningStep

        step: ReasoningStep = {
            "type": "think",
            "content": "Analyzing the question",
            "tool_name": None,
            "tool_args": None,
            "timestamp": 1234567890.0
        }

        assert step["type"] in ["think", "act", "observe", "answer"]
        assert isinstance(step["content"], str)
        assert isinstance(step["timestamp"], float)
```

**Step 2: Run integration test**

Run: `pytest tests/test_react_integration.py -v`

**Step 3: Commit**

```bash
git add tests/test_react_integration.py
git commit -m "$(cat <<'EOF'
test: add ReAct integration tests

Test full flow from router through ReAct to answer.
Verify reasoning trace structure.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Update Environment Configuration

**Files:**
- Modify: `.env.example`

**Step 1: Add configuration**

Add to `.env.example`:

```bash
# ReAct Configuration
REACT_MAX_ITERATIONS=5
REACT_ENABLED=true

# Session Storage
SESSION_STORE_ENABLED=true

# Context Compression
CONTEXT_TOKEN_BUDGET=6000
CONTEXT_KEEP_RECENT=4

# Hybrid Search Weights
RAG_DENSE_WEIGHT=0.7
RAG_SPARSE_WEIGHT=0.3

# Admin
ADMIN_TOKEN=change-this-in-production
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "$(cat <<'EOF'
docs: add ReAct configuration to .env.example

Add environment variables for:
- ReAct max iterations and toggle
- Session storage toggle
- Context compression settings
- Hybrid search weights
- Admin token

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Final Verification

**Step 1: Run all tests**

```bash
pytest tests/test_react_*.py tests/test_router_hybrid.py tests/test_session_store.py tests/test_api_react.py tests/test_api_admin.py tests/test_context_compression.py -v
```

Expected: All PASS

**Step 2: Run database migration**

```bash
psql -h localhost -U bestbox -d bestbox -f migrations/001_add_sessions.sql
```

**Step 3: Test API manually**

```bash
# Test ReAct endpoint
curl -X POST http://localhost:8000/chat/react \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the inventory level for WH-001?"}]}'

# Test admin endpoint
curl http://localhost:8000/admin/sessions \
  -H "admin-token: dev-admin-token"
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: complete ReAct reasoning system implementation

Adds:
- ReAct reasoning trace with Think→Act→Observe loop
- Hybrid router with secondary domain hints
- PostgreSQL session storage
- Admin API for session review
- Context compression for long conversations
- Frontend components for trace display and admin

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

This plan implements the ReAct reasoning system in 15 tasks:

1. **Tasks 1-3**: Core ReAct node (state, types, loop)
2. **Task 4**: Hybrid router with secondary domains
3. **Tasks 5-6**: Session storage (store + migration)
4. **Tasks 7-9**: Graph and API integration
5. **Tasks 10-11**: Frontend components
6. **Task 12**: Context compression
7. **Tasks 13-15**: Testing and verification

Each task follows TDD: write failing test → implement → verify → commit.
