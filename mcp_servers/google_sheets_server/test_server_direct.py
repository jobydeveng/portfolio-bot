#!/usr/bin/env python3
"""
Test if server.py can run directly (without MCP client)
"""

import os
import sys
import asyncio

# Set environment variables
os.environ["SHEET_ID"] = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
os.environ["SHEETS_API_KEY"] = os.environ.get("SHEETS_API_KEY", "")

print("Testing if server.py can be imported and run...")
print()

try:
    # Import the server module
    import server
    print("✅ Server module imported")
    print(f"   Server name: {server.server.name}")
    print(f"   SHEET_ID: {server.SHEET_ID}")
    print(f"   API_KEY: {'SET' if server.API_KEY else 'NOT SET'}")
    print()

    # Test the functions directly (without MCP protocol)
    print("Testing server functions directly:")

    print("1. Testing get_sheet_tabs()...")
    tabs = server.get_sheet_tabs()
    print(f"   ✅ Got {len(tabs)} tabs: {tabs}")
    print()

    print("2. Testing fetch_sheet() with first tab...")
    if tabs:
        rows = server.fetch_sheet(tabs[0])
        print(f"   ✅ Got {len(rows)} rows")
        print()

    print("3. Testing parse_categories()...")
    if tabs:
        rows = server.fetch_sheet(tabs[-1])  # Latest tab
        cats = server.parse_categories(rows)
        print(f"   ✅ Parsed categories: {list(cats.keys())}")
        print()

    print("4. Testing parse_total()...")
    total = server.parse_total(rows)
    print(f"   ✅ Total: Rs. {total:,.0f}")
    print()

    print("✅ All server functions work!")
    print()
    print("The server code is fine. Issue is likely with MCP stdio communication.")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
