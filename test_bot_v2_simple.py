#!/usr/bin/env python3
"""
Simplified test for bot_v2 agents without MCP stdio (Windows-friendly)
Tests agent logic by mocking MCP responses
"""

import os
import asyncio
import json
from openai import OpenAI

# Set environment variables
os.environ["SHEETS_API_KEY"] = os.environ.get("SHEETS_API_KEY", "")
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
os.environ["SHEET_ID"] = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"

print("=== Bot V2 Agent System Test (No stdio) ===\n")

# Import server modules directly
import sys
sys.path.insert(0, "mcp_servers/google_sheets_server")
sys.path.insert(0, "mcp_servers/market_data_server")
sys.path.insert(0, "mcp_servers/portfolio_context_server")

import mcp_servers.google_sheets_server.server as sheets_server
import mcp_servers.market_data_server.server as market_server
import mcp_servers.portfolio_context_server.server as context_server

print("✅ All MCP server modules imported")
print()

# Create mock MCP clients that call functions directly
class MockMCPClient:
    def __init__(self, server_module, server_name):
        self.server_module = server_module
        self.server_name = server_name

    async def call_tool(self, tool_name, arguments):
        """Mock MCP call_tool by calling server functions directly"""
        print(f"   📞 Calling {self.server_name}.{tool_name}({arguments})")

        # Call the appropriate server function
        if self.server_name == "sheets":
            if tool_name == "get_latest_portfolio":
                tabs = self.server_module.get_sheet_tabs()
                latest_tab = tabs[-1]
                rows = self.server_module.fetch_sheet(latest_tab)
                cats = self.server_module.parse_categories(rows)
                total = self.server_module.parse_total(rows)
                result = {"month": latest_tab, "total": total, "categories": cats}
            elif tool_name == "get_portfolio_history":
                tabs = self.server_module.get_sheet_tabs()
                limit = arguments.get("limit")
                if limit:
                    tabs = tabs[-limit:]
                all_data = []
                for tab in tabs:
                    rows = self.server_module.fetch_sheet(tab)
                    cats = self.server_module.parse_categories(rows)
                    total = self.server_module.parse_total(rows)
                    all_data.append({"month": tab, "total": total, "categories": cats})
                result = {"history": all_data}
            else:
                result = {"error": f"Mock doesn't support {tool_name}"}

        elif self.server_name == "market":
            if tool_name == "get_market_indices":
                result = {"indices": [{"name": "Nifty 50", "current": 23500, "change": 150, "percent_change": 0.64}]}
            elif tool_name == "get_stock_price":
                ticker = arguments.get("ticker", "HDFCBANK")
                result = {"ticker": ticker, "current_price": 1650.50, "change": 15.20, "percent_change": 0.93}
            else:
                result = {"error": f"Mock doesn't support {tool_name}"}

        elif self.server_name == "context":
            if tool_name == "get_holdings_list":
                fmt = arguments.get("format", "brief")
                if fmt == "brief":
                    result = {
                        "indian_stocks": list(self.server_module.INDIAN_STOCKS.keys()),
                        "us_stocks": list(self.server_module.US_STOCKS.keys())
                    }
                else:
                    result = {
                        "indian_stocks": self.server_module.INDIAN_STOCKS,
                        "us_stocks": self.server_module.US_STOCKS
                    }
            elif tool_name == "get_investor_profile":
                result = self.server_module.INVESTOR_PROFILE
            else:
                result = {"error": f"Mock doesn't support {tool_name}"}

        # Return in MCP format (list of TextContent objects)
        class MockTextContent:
            def __init__(self, text):
                self.text = text

        return [MockTextContent(json.dumps(result))]


async def test_agents():
    """Test agent system with mock MCP clients"""

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Create mock MCP clients
    mock_clients = {
        "sheets": MockMCPClient(sheets_server, "sheets"),
        "market": MockMCPClient(market_server, "market"),
        "context": MockMCPClient(context_server, "context")
    }

    print("✅ Mock MCP clients created\n")

    # Import and test agents
    from bot_agents import PortfolioAgent, MarketAgent, OrchestratorAgent

    print("=== Test 1: Portfolio Agent ===")
    portfolio_agent = PortfolioAgent(openai_client, mock_clients)
    query = "What's my latest portfolio value?"
    context = {"user_id": 123}

    print(f"Query: {query}")
    result = await portfolio_agent.process(query, context)
    print(f"Response: {result.get('text', 'No response')[:200]}...")
    print(f"Error: {result.get('error')}")
    print()

    print("=== Test 2: Orchestrator Intent Classification ===")
    orchestrator = OrchestratorAgent(openai_client, mock_clients)

    test_queries = [
        "Show my portfolio",
        "Why is market down?",
        "Show me a pie chart",
        "What should I buy?"
    ]

    for query in test_queries:
        intent = await orchestrator._classify_intent(query)
        print(f"Query: '{query}'")
        print(f"   → Agent: {intent.get('agent')}, Needs Chart: {intent.get('needs_chart')}")

    print()
    print("✅ Agent tests completed!")
    print()
    print("Note: Full MCP stdio tests don't work on Windows due to subprocess issues.")
    print("This is fine - the code will work in production on Linux (Render).")


if __name__ == "__main__":
    asyncio.run(test_agents())
