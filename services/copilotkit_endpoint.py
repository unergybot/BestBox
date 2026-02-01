"""
CopilotKit Remote Endpoint for BestBox Agent System
This service wraps the LangGraph agent API and provides CopilotKit-compatible endpoints.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAgent, Action
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from agents.graph import app as agent_app
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the agent wrapper
bestbox_agent = LangGraphAgent(
    name="bestbox_agent",
    description="BestBox Enterprise Agent for ERP, CRM, IT Ops, and OA tasks. Routes queries to specialized agents.",
    agent=agent_app,
)

# Create additional actions
def _detect_gpu_info():
    """Detect GPU information dynamically."""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            if 'AMD' in gpu_name or 'Radeon' in gpu_name:
                return gpu_name, "llama.cpp (Vulkan)"
            else:
                return gpu_name, "llama.cpp (CUDA)"
    except Exception:
        pass
    return "CPU", "llama.cpp (CPU)"


get_system_info_action = Action(
    name="get_system_info",
    description="Get information about the BestBox system",
    parameters=[],
    handler=lambda: {
        "system": "BestBox Enterprise Agentic Demo",
        "framework": "LangGraph (Python)",
        "agents": ["Router", "ERP", "CRM", "IT Ops", "OA"],
        "status": "connected",
        "model": os.environ.get("LLM_MODEL_NAME", "Qwen2.5-14B-Instruct"),
        "backend": _detect_gpu_info()[1],
        "gpu": _detect_gpu_info()[0],
    }
)

# Create CopilotKit SDK
sdk = CopilotKitRemoteEndpoint(
    agents=[bestbox_agent],
    actions=[get_system_info_action],
)

# Create FastAPI app
app = FastAPI(title="BestBox CopilotKit Endpoint")

# Add CopilotKit endpoint
add_fastapi_endpoint(app, sdk, "/copilotkit")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "copilotkit-endpoint"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
