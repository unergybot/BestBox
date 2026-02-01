"""
Check if ERPNext has been seeded with basic data.
Returns exit code 0 if data exists, 1 if data does NOT exist or error.
"""
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.erpnext_client import ERPNextClient

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("check_data")

def check_data():
    client = ERPNextClient()
    
    if not client.is_available():
        # If API not available, we can't confirm data exists.
        # But for the purpose of "should we seed?", if it's down, we can't seed anyway.
        # But the shell script logic is: if check fails, run seed. 
        # So we should return 0 (pretend verified) if down? 
        # No, if down, the seed script will also fail immediately.
        # Let's simple return 1, and let seed script handle availability check.
        # BUT: startup script waits for ERPNext port first.
        return False

    try:
        # Check for Suppliers
        suppliers = client.get_list("Supplier", limit=1)
        if suppliers and len(suppliers) > 0:
            return True
        
        # Check for Items as backup
        items = client.get_list("Item", limit=1)
        if items and len(items) > 0:
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking data: {e}")
        return False

if __name__ == "__main__":
    if check_data():
        print("Data exists")
        sys.exit(0)
    else:
        print("No data found")
        sys.exit(1)
