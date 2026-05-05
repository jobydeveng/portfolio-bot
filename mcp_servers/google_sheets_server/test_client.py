#!/usr/bin/env python3
"""
Test client for Google Sheets MCP Server
"""

import os
import sys
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_sheets_server():
    """Test the Google Sheets MCP server"""
    print("🔧 Starting Google Sheets MCP Server...")

    # Set environment variables
    os.environ["SHEET_ID"] = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
    os.environ["SHEETS_API_KEY"] = os.environ.get("SHEETS_API_KEY", "")

    # Server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        env=os.environ.copy()
    )

    print("   Starting subprocess...")
    # Start server using async context manager
    async with stdio_client(server_params) as (read_stream, write_stream):
        print("   Creating client session...")
        session = ClientSession(read_stream, write_stream)

        await session.initialize()
        print("✅ MCP server started\n")

        # Test 1: List tools
        print("📋 Test 1: List available tools")
        tools = await session.list_tools()
        print(f"Available tools: {len(tools.tools)}")
        for tool in tools.tools:
            print(f"  - {tool.name}: {tool.description}")
        print()

        # Test 2: Fetch sheet tabs
        print("📊 Test 2: Fetch sheet tabs")
        result = await session.call_tool("fetch_sheet_tabs", {})
        data = json.loads(result[0].text)
        print(f"Tabs: {data.get('tabs', [])}")
        print()

        # Test 3: Get latest portfolio
        print("💰 Test 3: Get latest portfolio")
        result = await session.call_tool("get_latest_portfolio", {})
        data = json.loads(result[0].text)
        print(f"Month: {data.get('month')}")
        print(f"Total: Rs. {data.get('total', 0):,.0f}")
        print(f"Categories: {list(data.get('categories', {}).keys())}")
        print()

        # Test 4: Get portfolio history (last 3 months)
        print("📈 Test 4: Get portfolio history (last 3 months)")
        result = await session.call_tool("get_portfolio_history", {"limit": 3})
        data = json.loads(result[0].text)
        print(f"History entries: {len(data.get('history', []))}")
        for entry in data.get("history", []):
            print(f"  {entry['month']}: Rs. {entry['total']:,.0f}")
        print()

        # Test 5: Get specific month
        print("🗓️ Test 5: Get specific month (March)")
        result = await session.call_tool("get_month_portfolio", {"month_query": "March"})
        data = json.loads(result[0].text)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Month: {data.get('month')}")
            print(f"Total: Rs. {data.get('total', 0):,.0f}")
        print()

        print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_sheets_server())
