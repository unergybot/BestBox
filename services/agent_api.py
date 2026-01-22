import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agents.graph import app as agent_app
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BestBox Agent API")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    agent: str
    trace: List[Dict[str, Any]] = []

@app.get("/health")
async def health():
    return {"status": "ok", "service": "langgraph-agent"}

@app.post("/v1/chat/completions")
async def chat_completion(request: ChatRequest):
    """
    OpenAI-like endpoint but simplified for our agent.
    """
    # Convert messages to LangChain format
    lc_messages = []
    for msg in request.messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=msg.content))
            
    inputs = {"messages": lc_messages}
    
    logger.info(f"Processing request with {len(lc_messages)} messages")
    
    try:
        # Run the graph
        # For stateful conversations, we'd pass config={"configurable": {"thread_id": request.thread_id}}
        # For now, we are treating it as stateless per request + history
        result = await agent_app.ainvoke(inputs)
        
        last_msg = result["messages"][-1]
        current_agent = result.get("current_agent", "unknown")
        
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": last_msg.content
                    },
                    "finish_reason": "stop"
                }
            ],
            "agent": current_agent
        }
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
