
import sys
import os
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Mocking LiveKit agent imports if needed, but we mainly want to test graph_wrapper
# Since graph_wrapper calls bestbox_graph, we need to ensure that is working.

from services.livekit_agent import graph_wrapper

async def test_graph_wrapper():
    print("Testing graph_wrapper...")
    
    # Simulate input from LiveKit (a list of LangChain messages or just text converted to messages)
    from langchain_core.messages import HumanMessage
    
    test_input = [HumanMessage(content="Who are our top vendors?")]
    
    try:
        response = await graph_wrapper(test_input)
        print(f"\nResponse: {response}")
        
        if "I'm sorry" in response and "System error" in response:
             print("❌ Graph wrapper returned error.")
        elif response:
             print("✅ Graph wrapper returned a response.")
        else:
             print("❌ Graph wrapper returned empty response.")
             
    except Exception as e:
        print(f"❌ Exception during graph_wrapper test: {e}")

if __name__ == "__main__":
    asyncio.run(test_graph_wrapper())
