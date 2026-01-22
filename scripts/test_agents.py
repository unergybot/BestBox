import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.graph import app
from langchain_core.messages import HumanMessage
import asyncio

async def run_test(query: str):
    print(f"\nQUERY: {query}")
    print("-" * 40)
    
    inputs = {"messages": [HumanMessage(content=query)]}
    
    try:
        # Use ainvoke for async execution
        result = await app.ainvoke(inputs)
        
        last_message = result['messages'][-1]
        agent = result.get('current_agent', 'unknown')
        
        print(f"ROUTED TO: {agent}")
        if len(result['messages']) > 2:
            print("Trace:")
            for msg in result['messages'][1:]: # Skip user message at 0
                print(f"  [{msg.type}]: {msg.content[:100]}...")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"    Tool Calls: {msg.tool_calls}")
        
        print(f"RESPONSE: {last_message.content}")
    except Exception as e:
        print(f"ERROR: {e}")

async def main():
    queries = [
        "What is our current inventory level?",
        "Which leads are likely to churn?",
        "The production database is unresponsive.",
        "Draft an email to the team about the meeting.",
        "Hi, how are you?"
    ]
    
    for query in queries:
        await run_test(query)

if __name__ == "__main__":
    asyncio.run(main())
