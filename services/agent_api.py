import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union, cast
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agents.graph import app as agent_app
from agents.state import AgentState
import uvicorn
import logging
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BestBox Agent API")

class ChatMessage(BaseModel):
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None  # Support both string and array format, optional
    tool_calls: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None

class ChatRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None  # OpenAI format
    input: Optional[List[Dict[str, Any]]] = None  # CopilotKit format
    model: Optional[str] = None
    thread_id: Optional[str] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None

class ChatResponse(BaseModel):
    response: str
    agent: str
    trace: List[Dict[str, Any]] = []

@app.get("/health")
async def health():
    return {"status": "ok", "service": "langgraph-agent"}

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "object": "list",
        "data": [
            {
                "id": "bestbox-agent",
                "object": "model",
                "created": 1234567890,
                "owned_by": "bestbox"
            }
        ]
    }

@app.post("/v1/responses")
async def create_response(request: ChatRequest):
    """
    CopilotKit-specific streaming responses endpoint.
    Supports both streaming and non-streaming responses.
    """
    if request.stream:
        return await chat_completion_stream(request)
    else:
        return await chat_completion(request)

async def chat_completion_stream(request: ChatRequest):
    """Stream the response using SSE format"""
    async def generate():
        try:
            # Process the request
            messages_to_process = []
            
            if request.messages:
                messages_to_process = request.messages
            elif request.input:
                for item in request.input:
                    if isinstance(item, dict) and "role" in item:
                        content = item.get("content", "")
                        msg = ChatMessage(role=item["role"], content=content)
                        if "tool_calls" in item:
                            msg.tool_calls = item["tool_calls"]
                        messages_to_process.append(msg)
            
            if not messages_to_process:
                yield f"data: {json.dumps({'error': 'No messages provided'})}\n\n"
                return
            
            # Convert to LangChain messages
            lc_messages = []
            for msg in messages_to_process:
                content_text = parse_message_content(msg.content) if msg.content is not None else ""
                
                if msg.role == "user":
                    lc_messages.append(HumanMessage(content=content_text))
                elif msg.role == "assistant":
                    tool_calls = msg.tool_calls or []
                    lc_messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
                elif msg.role == "system":
                    lc_messages.append(SystemMessage(content=content_text))
            
            inputs: AgentState = {
                "messages": lc_messages,
                "current_agent": "router",
                "tool_calls": 0,
                "confidence": 1.0,
                "context": {},
                "plan": [],
                "step": 0
            }
            
            # Get response from agent
            result = await agent_app.ainvoke(cast(AgentState, inputs))
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            
            # Ensure content is never undefined - always a string
            if content is None:
                content = ""
            
            # Stream the content as chunks
            chunk_id = f"chatcmpl-{int(time.time())}"
            
            # Send the content in one chunk (can be split for true streaming)
            chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model or "bestbox-agent",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": content  # Always a string now
                    },
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            
            # Send finish chunk
            finish_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model or "bestbox-agent",
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(finish_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            # Return an error message as content so frontend doesn't crash
            error_chunk = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model or "bestbox-agent",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"Error: {str(e)}"
                    },
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


def parse_message_content(content: Union[str, List[Dict[str, Any]]]) -> str:
    """Parse message content from either string or array format"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Extract text from array format like [{"type": "input_text", "text": "hello"}]
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "input_text" and "text" in item:
                    text_parts.append(item["text"])
                elif "text" in item:
                    text_parts.append(item["text"])
        return " ".join(text_parts) if text_parts else str(content)
    else:
        return str(content)

@app.post("/v1/chat/completions")
async def chat_completion_endpoint(request: ChatRequest):
    """
    OpenAI-compatible endpoint supporting both standard and CopilotKit formats.
    Handles both 'messages' (OpenAI) and 'input' (CopilotKit) fields.
    Supports both streaming and non-streaming responses.
    """
    # If streaming is requested, use the streaming handler
    if request.stream:
        return await chat_completion_stream(request)
    
    # Debug logging
    try:
        logger.info(f"Incoming Request: {request.model_dump_json(exclude={'input'})}")
    except:
        pass

    # Normalize input to messages format
    messages_to_process = []
    
    if request.messages:
        # Standard OpenAI format
        messages_to_process = request.messages
    elif request.input:
        # CopilotKit format - convert input array to messages
        for item in request.input:
            if isinstance(item, dict) and "role" in item:
                content = item.get("content", "")
                msg = ChatMessage(role=item["role"], content=content)
                if "tool_calls" in item:
                    msg.tool_calls = item["tool_calls"]
                messages_to_process.append(msg)
    else:
        raise HTTPException(status_code=422, detail="Either 'messages' or 'input' field is required")
    
    # Convert to LangChain messages
    lc_messages = []
    for msg in messages_to_process:
        content_text = parse_message_content(msg.content) if msg.content is not None else ""
        
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content_text))
        elif msg.role == "assistant":
            # Handle tool calls in history
            tool_calls = msg.tool_calls or []
            lc_messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=content_text))
        elif msg.role == "tool":
            # Handle tool outputs if needed, but for now we skip complex reconstruction
            pass
            
    if not lc_messages:
        raise HTTPException(status_code=422, detail="No valid messages to process")
    
    inputs: AgentState = {
        "messages": lc_messages,
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0
    }
    
    logger.info(f"Processing request with {len(lc_messages)} messages")
    
    try:
        result = await agent_app.ainvoke(cast(AgentState, inputs))
        
        last_msg = result["messages"][-1]
        current_agent = result.get("current_agent", "unknown")
        
        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        tool_calls = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') else None
        
        # Build message dict
        message_dict = {
            "role": "assistant",
            "content": content or ""  # Ensure empty string if None, unless tool_calls
        }
        
        if tool_calls:
            message_dict["tool_calls"] = tool_calls
            if not content:
                message_dict["content"] = None
        
        # Return OpenAI-compatible response format
        import time
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model or "bestbox-agent",
            "choices": [
                {
                    "index": 0,
                    "message": message_dict,
                    "finish_reason": "tool_calls" if tool_calls else "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "agent": current_agent
        }
        
        logger.info(f"Returning response from agent: {current_agent}")
        return response
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        # Return a polite error message instead of 500 crashes
        import time
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model or "bestbox-agent", 
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant", 
                    "content": f"I encountered an error processing your request: {str(e)}",
                },
                "finish_reason": "stop"
            }]
        }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
