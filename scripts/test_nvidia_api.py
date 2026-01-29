
import os
import sys
from livekit.plugins import openai as lk_openai
import asyncio

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nvidia_test")

async def test_nvidia():
    logger.info("🧪 Testing Nvidia Minimax API...")
    
    NVIDIA_API_KEY = "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"
    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL = "minimaxai/minimax-m2"

    try:
        llm = lk_openai.LLM(
            base_url=NVIDIA_BASE_URL,
            model=NVIDIA_MODEL,
            api_key=NVIDIA_API_KEY
        )
        
        logger.info(f"Initialized LLM: {NVIDIA_MODEL}")
        logger.info("Sending chat completion request...")
        
        # Create a simple chat context
        from livekit.agents.llm import ChatContext, ChatMessage, ChatRole
        ctx = ChatContext()
        ctx.add_message(role="user", content="Say 'Nvidia API is working' and nothing else.")
        
        stream = llm.chat(chat_ctx=ctx)
        
        full_text = ""
        async for chunk in stream:
            # Debug: print raw chunk structure
            # print(f"DEBUG CHUNK: {chunk}", flush=True) 
            
            content = None
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
            elif hasattr(chunk, 'delta') and chunk.delta:
                content = chunk.delta.content
            
            if content:
                full_text += content
                print(content, end="", flush=True)
        
        print("\n")
        logger.info(f"✅ Received response: {full_text}")
        
        if "Nvidia API is working" in full_text:
            logger.info("🎉 SUCCESS: Nvidia API verified!")
            return True
        else:
            logger.warning("⚠️ Partial success: Received text but not exact phrase.")
            return True

    except Exception as e:
        logger.error(f"❌ FAILED: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_nvidia())
    sys.exit(0 if success else 1)
