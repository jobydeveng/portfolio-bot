#!/usr/bin/env python3
"""
Test if Google Sheet is publicly accessible without API key
"""

import requests

sheet_id = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"

print(f"Testing public access to sheet: {sheet_id[:20]}...\n")

try:
    # Try WITHOUT API key
    r = requests.get(url, timeout=5)

    if r.status_code == 200:
        data = r.json()
        sheets = data.get('sheets', [])
        print(f"✅ PUBLIC ACCESS WORKS! No API key needed.")
        print(f"   Found {len(sheets)} sheets:")
        for sheet in sheets[:5]:  # Show first 5
            print(f"   - {sheet['properties']['title']}")
    elif r.status_code == 403:
        print(f"❌ Sheet is PRIVATE - API key required")
        print(f"   Get your API key and set it as environment variable:")
        print(f"   $env:SHEETS_API_KEY = 'your-key-here'")
    else:
        print(f"❌ Unexpected status: {r.status_code}")
        print(f"   Response: {r.text[:200]}")

except Exception as e:
    print(f"❌ Connection failed: {e}")

print("\nNext steps:")
print("1. If public access works: The tests will run fine")
print("2. If private: Set SHEETS_API_KEY environment variable")
