
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from tools.erp_tools import get_top_vendors

try:
    print("Invoking get_top_vendors tool...")
    result = get_top_vendors.invoke({"limit": 5})
    print("Tool Result:")
    print(result)
except Exception as e:
    print(f"Error: {e}")
