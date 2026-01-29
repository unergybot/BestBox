import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.erpnext_client import ERPNextClient

client = ERPNextClient()

if client.is_available():
    fys = client.get_list("Fiscal Year", fields=["name", "year_start_date", "year_end_date"])
    print("Current Fiscal Years:")
    if fys:
        for fy in fys:
            print(f"- {fy['name']}: {fy['year_start_date']} to {fy['year_end_date']}")
    else:
        print("No fiscal years found.")
else:
    print("ERPNext unavailable.")
