
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from agents.router import router_node
from langchain_core.messages import HumanMessage

def test_router():
    print("Testing router with query: 'what's the proper context size for our application'")
    
    state = {
        "messages": [HumanMessage(content="what's the proper context size for our application")]
    }
    
    result = router_node(state)
    print(f"Result: {result}")

if __name__ == "__main__":
    test_router()
