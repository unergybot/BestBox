
import asyncio
import logging
import sys
import os
from langchain_core.messages import HumanMessage

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graph_debug")

async def test_graph():
    print("--- Testing Graph Wrapper ---")
    try:
        from services.livekit_agent import graph_wrapper, bestbox_graph
        print(f"Graph imported: {bestbox_graph is not None}")
        
        input_msg = [HumanMessage(content="Hello, can you hear me?")]
        print(f"Input: {input_msg}")
        
        result = await graph_wrapper(input_msg)
        print(f"Result: {result}")
        
    except ImportError as e:
        print(f"Import Error: {e}")
    except Exception as e:
        print(f"Execution Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_graph())
