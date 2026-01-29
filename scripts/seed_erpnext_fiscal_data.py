import sys
import os
import logging
import requests

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.erpnext_client import ERPNextClient

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_fiscal")

def seed_fiscal_year():
    client = ERPNextClient()
    
    if not client.is_available():
        logger.error("ERPNext is not available")
        return

    year = "2026"
    data = {
        "doctype": "Fiscal Year",
        "year": year,
        "year_start_date": "2026-01-01",
        "year_end_date": "2026-12-31",
        "disabled": 0
    }
    
    # Check if exists
    existing = client.get_list("Fiscal Year", filters={"year": year})
    if existing:
        logger.info(f"Fiscal Year {year} already exists.")
        return

    logger.info(f"Creating Fiscal Year {year}...")
    try:
        resp = client.session.post(
            f"{client.url}/api/resource/Fiscal Year",
            json=data,
            timeout=10
        )
        if resp.status_code == 200:
            logger.info("Successfully created Fiscal Year 2026")
        else:
            logger.error(f"Failed to create Fiscal Year: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Error creating Fiscal Year: {e}")

if __name__ == "__main__":
    seed_fiscal_year()
