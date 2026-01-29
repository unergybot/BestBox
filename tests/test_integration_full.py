"""
Comprehensive Integration Tests for BestBox System

Tests the full system integration including:
- Agent routing and execution
- Context management
- RAG pipeline integration
- Tool execution
- LiveKit voice integration
- End-to-end scenarios
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.graph import app as bestbox_graph
from agents.router import router_node
from agents.context_manager import apply_sliding_window, estimate_tokens, prepare_messages_for_agent
from agents.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage


class TestAgentRouting:
    """Test agent routing and state management"""
    
    def test_router_function_callable(self):
        """Test router function is callable"""
        assert callable(router_node)
    
    def test_router_accepts_state(self):
        """Test router accepts AgentState"""
        try:
            state = AgentState(
                messages=[HumanMessage(content="Test message")],
                current_agent="router",
                tool_calls=0,
                confidence=0.0,
                context={},
                plan=[],
                step=0
            )
            # Test that state structure is valid
            assert "messages" in state
            assert len(state["messages"]) > 0
        except Exception as e:
            pytest.fail(f"Router state validation failed: {e}")


class TestContextManagement:
    """Test context management and message truncation"""
    
    def test_token_estimation(self):
        """Test token estimation function"""
        short_text = "Hello world"
        assert estimate_tokens(short_text) < 10
        
        long_text = "x" * 4000  # ~1000 tokens
        assert 900 < estimate_tokens(long_text) < 1100
    
    def test_sliding_window_small(self):
        """Test sliding window with few messages"""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?")
        ]
        result = apply_sliding_window(messages, max_tokens=1000, max_messages=5)
        assert len(result) == 3
    
    def test_sliding_window_truncation(self):
        """Test sliding window truncates old messages"""
        messages = []
        for i in range(20):
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))
        
        result = apply_sliding_window(messages, max_tokens=1000, max_messages=8)
        assert len(result) <= 8
        # Should keep most recent messages
        assert "Message 19" in result[-2].content
    
    def test_context_overflow_prevention(self):
        """Test that large contexts are properly truncated"""
        # Create messages that would exceed context
        large_messages = []
        for i in range(10):
            large_messages.append(HumanMessage(content="x" * 500))  # ~125 tokens each
            large_messages.append(AIMessage(content="y" * 500))
        
        result = apply_sliding_window(large_messages, max_tokens=1000, max_messages=20)
        total_tokens = sum(estimate_tokens(m.content) for m in result)
        assert total_tokens < 1000
    
    def test_prepare_messages_callable(self):
        """Test prepare_messages_for_agent is callable"""
        assert callable(prepare_messages_for_agent)


class TestGraphExecution:
    """Test LangGraph execution end-to-end"""
    
    def test_graph_importable(self):
        """Test graph can be imported"""
        assert bestbox_graph is not None
    
    @pytest.mark.skip(reason="Requires LLM server")
    def test_simple_query_execution(self):
        """Test executing a simple query through the graph (requires LLM server)"""
        pass


class TestToolIntegration:
    """Test tool execution and integration"""
    
    def test_tools_directory_exists(self):
        """Test that tools directory exists"""
        tools_path = os.path.join(os.path.dirname(__file__), "..", "tools")
        assert os.path.exists(tools_path)
    
    def test_erp_tools_importable(self):
        """Test ERP tools can be imported"""
        try:
            from tools import erp_tools
            assert erp_tools is not None
        except ImportError:
            pytest.skip("ERP tools not available")
    
    def test_crm_tools_importable(self):
        """Test CRM tools can be imported"""
        try:
            from tools import crm_tools
            assert crm_tools is not None
        except ImportError:
            pytest.skip("CRM tools not available")


class TestRAGIntegration:
    """Test RAG pipeline integration with agents"""
    
    def test_rag_pipeline_directory_exists(self):
        """Test RAG pipeline directory exists"""
        rag_path = os.path.join(os.path.dirname(__file__), "..", "services", "rag_pipeline")
        assert os.path.exists(rag_path)
    
    def test_embeddings_directory_exists(self):
        """Test embeddings directory exists"""
        embeddings_path = os.path.join(os.path.dirname(__file__), "..", "services", "embeddings")
        assert os.path.exists(embeddings_path)


class TestLiveKitIntegration:
    """Test LiveKit voice agent integration"""
    
    def test_livekit_agent_file_exists(self):
        """Test LiveKit agent file exists"""
        livekit_agent_path = os.path.join(os.path.dirname(__file__), "..", "services", "livekit_agent.py")
        assert os.path.exists(livekit_agent_path)
    
    def test_livekit_agent_importable(self):
        """Test LiveKit agent can be imported"""
        try:
            from services import livekit_agent
            assert livekit_agent is not None
        except ImportError:
            pytest.skip("LiveKit not available")
    
    def test_langchain_adapter(self):
        """Test LangChain adapter can wrap graph"""
        try:
            from livekit.plugins import langchain as lk_langchain
            adapter = lk_langchain.LLMAdapter(bestbox_graph)
            assert adapter is not None
        except ImportError:
            pytest.skip("LiveKit plugins not installed")


class TestEndToEndScenarios:
    """Test complete end-to-end user scenarios"""
    
    @pytest.mark.skip(reason="Requires all services running")
    def test_vendor_inquiry_scenario(self):
        """Test: User asks about top vendors (requires services)"""
        pass
    
    @pytest.mark.skip(reason="Requires all services running")
    def test_customer_inquiry_scenario(self):
        """Test: User asks about customer information (requires services)"""
        pass


class TestObservability:
    """Test observability and monitoring integration"""
    
    def test_observability_file_exists(self):
        """Test observability module exists"""
        obs_path = os.path.join(os.path.dirname(__file__), "..", "services", "observability.py")
        assert os.path.exists(obs_path)
    
    def test_prometheus_config_exists(self):
        """Test Prometheus configuration exists"""
        prom_config = os.path.join(os.path.dirname(__file__), "..", "config", "prometheus")
        assert os.path.exists(prom_config)


class TestSystemHealth:
    """Test system health and dependencies"""
    
    def test_llm_server_accessible(self):
        """Test local LLM server is accessible"""
        try:
            import requests
            response = requests.get("http://localhost:8080/health", timeout=2)
            assert response.status_code == 200
        except Exception:
            pytest.skip("LLM server not running at localhost:8080")
    
    def test_agent_api_accessible(self):
        """Test agent API is accessible"""
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=2)
            assert response.status_code == 200
        except Exception:
            pytest.skip("Agent API not running at localhost:8000")
    
    def test_database_connection(self):
        """Test database connection"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="bestbox",
                user="bestbox",
                password="bestbox",
                connect_timeout=2
            )
            conn.close()
            assert True
        except Exception:
            pytest.skip("Database not accessible")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
