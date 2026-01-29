import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.erpnext_client import ERPNextClient
import logging
logging.basicConfig(level=logging.INFO)

def fix_cny():
    client = ERPNextClient()
    print("Updating CNY Currency fraction...")
    try:
        resp = client.session.put(
            f"{client.url}/api/resource/Currency/CNY", 
            json={"fraction": "Fen"}
        )
        if resp.status_code == 200:
            print("✅ Successfully updated CNY fraction to 'Fen'.")
        else:
            print(f"❌ Failed to update CNY: {resp.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_cny()
