import sys
import os
import logging
from time import sleep

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.erpnext_client import ERPNextClient

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_erpnext")

def verify():
    print("=== Verifying ERPNext Connection ===")
    
    # Initialize client (will pick up params from env or default)
    # Default URL is http://localhost:8002 per docker-compose
    client = ERPNextClient()
    
    print(f"URL: {client.url}")
    print("Checking availability...")
    
    is_up = client.is_available()
    
    if is_up:
        print("✅ ERPNext is AVAILABLE")
        
        # Try to fetch something simple
        print("Fetching Supplier list (limit 1)...")
        try:
            suppliers = client.get_list("Supplier", limit=1)
            if suppliers is not None:
                print(f"✅ Successfully fetched suppliers: {len(suppliers)} found")
                if suppliers:
                    print(f"Sample: {suppliers[0]}")
            else:
                print("❌ Failed to fetch suppliers (returned None)")
        except Exception as e:
             print(f"❌ Exception fetching suppliers: {e}")
             
    else:
        print("❌ ERPNext is UNAVAILABLE (Health check failed)")
        print("Make sure the container is running: docker compose ps")

if __name__ == "__main__":
    verify()
