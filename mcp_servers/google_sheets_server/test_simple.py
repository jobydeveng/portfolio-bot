#!/usr/bin/env python3
"""
Simple diagnostic test for Google Sheets MCP Server
"""

import os
import sys

print("=== Environment Check ===")
print(f"Python: {sys.executable}")
print(f"SHEET_ID: {os.environ.get('SHEET_ID', 'NOT SET')}")
print(f"SHEETS_API_KEY: {'SET' if os.environ.get('SHEETS_API_KEY') else 'NOT SET'}")
print()

# Try importing dependencies
print("=== Import Check ===")
try:
    import mcp
    print(f"✅ mcp: {mcp.__version__ if hasattr(mcp, '__version__') else 'imported'}")
except ImportError as e:
    print(f"❌ mcp: {e}")

try:
    import requests
    print(f"✅ requests: {requests.__version__}")
except ImportError as e:
    print(f"❌ requests: {e}")

print()

# Try running the server directly
print("=== Server Module Check ===")
try:
    import server
    print(f"✅ server.py imported successfully")
    print(f"   SHEET_ID in server: {server.SHEET_ID}")
    print(f"   API_KEY in server: {'SET' if server.API_KEY else 'NOT SET'}")
except Exception as e:
    print(f"❌ server.py import failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Try a direct Google Sheets API call
print("=== Google Sheets API Test ===")
if os.environ.get('SHEETS_API_KEY'):
    import requests
    sheet_id = os.environ.get('SHEET_ID', '1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE')
    api_key = os.environ.get('SHEETS_API_KEY')

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    params = {"key": api_key}

    try:
        print(f"Testing connection to sheet: {sheet_id[:20]}...")
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            sheets = data.get('sheets', [])
            print(f"✅ API connection successful!")
            print(f"   Found {len(sheets)} sheets")
            if sheets:
                print(f"   Example: {sheets[0]['properties']['title']}")
        else:
            print(f"❌ API returned status {r.status_code}")
            print(f"   Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ API call failed: {e}")
else:
    print("⚠️  SHEETS_API_KEY not set, skipping API test")

print("\n=== Diagnostic Complete ===")
