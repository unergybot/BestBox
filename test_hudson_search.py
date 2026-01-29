
from tools.rag_tools import search_knowledge_base

# The tool takes a dict input or positional args matching the schema.
# Since it's a StructuredTool, specific invocation might differ slightly depending on version,
# but likely .invoke({"query": "...", "domain": "..."}) works.
try:
    print("Test 1: Domain='hudson'")
    print(search_knowledge_base.invoke({"query": "When was Hudson Group founded?", "domain": "hudson"}))
except Exception as e:
    print(f"Test 1 Failed: {e}")

print("\n" + "-" * 20 + "\n")

try:
    print("Test 2: Domain=None")
    print(search_knowledge_base.invoke({"query": "What is Hudson Group?", "domain": None}))
except Exception as e:
    print(f"Test 2 Failed: {e}")
