#!/usr/bin/env python3
"""
Portfolio Context MCP Server
Provides structured portfolio holdings context, sector exposure, and investment strategy information
"""

import os
import json
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_context_server")

# Investor Profile
INVESTOR_PROFILE = {
    "name": "Joby",
    "age": 33,
    "location": "Kerala, India",
    "risk_appetite": "Medium to Aggressive",
    "investment_horizon": "Long term (5+ years)",
    "goal": "Wealth creation through diversified portfolio"
}

# Indian Stocks Holdings
INDIAN_STOCKS = {
    "AAVAS": {"name": "Aavas Financiers", "sector": "Housing Finance"},
    "ASIANPAINT": {"name": "Asian Paints", "sector": "Paints/Consumer"},
    "AXISBANK": {"name": "Axis Bank", "sector": "Banking"},
    "BAJFINANCE": {"name": "Bajaj Finance", "sector": "NBFC/Finance"},
    "BANKBEES": {"name": "Bank BeES", "sector": "Bank ETF"},
    "GOLDBEES": {"name": "Gold BeES", "sector": "Gold ETF"},
    "GOLDIETF": {"name": "Goldie ETF", "sector": "Gold ETF"},
    "HAPPSTMNDS": {"name": "Happiest Minds", "sector": "IT Midcap"},
    "HDFCBANK": {"name": "HDFC Bank", "sector": "Banking"},
    "HDFCLIFE": {"name": "HDFC Life", "sector": "Insurance"},
    "HINDUNILVR": {"name": "Hindustan Unilever", "sector": "FMCG"},
    "ICICIBANK": {"name": "ICICI Bank", "sector": "Banking"},
    "IDFCFIRSTB": {"name": "IDFC First Bank", "sector": "Banking"},
    "ITBEES": {"name": "IT BeES", "sector": "IT Sector ETF"},
    "ITC": {"name": "ITC", "sector": "FMCG/Conglomerate"},
    "JIOFIN": {"name": "Jio Financial Services", "sector": "Financial Services"},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank", "sector": "Banking"},
    "KWIL": {"name": "Khaitan Wheels", "sector": "Small/MicroCap"},
    "MON100": {"name": "Motilal NASDAQ 100 ETF", "sector": "US Equity ETF"},
    "NESTLEIND": {"name": "Nestle India", "sector": "FMCG"},
    "NIFTYBEES": {"name": "Nifty BeES", "sector": "Nifty 50 ETF"},
    "RELIANCE": {"name": "Reliance Industries", "sector": "Conglomerate"},
    "SBICARD": {"name": "SBI Cards", "sector": "Credit Cards/Finance"},
    "SBIN": {"name": "State Bank of India", "sector": "PSU Banking"}
}

# Sector Classification
SECTOR_GROUPS = {
    "Banking/Finance": [
        "AXISBANK", "BAJFINANCE", "HDFCBANK", "HDFCLIFE", "ICICIBANK",
        "IDFCFIRSTB", "KOTAKBANK", "SBIN", "SBICARD", "JIOFIN", "BANKBEES"
    ],
    "FMCG/Consumer": ["HINDUNILVR", "ITC", "NESTLEIND", "ASIANPAINT"],
    "Gold": ["GOLDBEES", "GOLDIETF"],
    "Index ETFs": ["NIFTYBEES", "ITBEES", "BANKBEES", "MON100"],
    "Others": ["AAVAS", "HAPPSTMNDS", "RELIANCE", "KWIL"]
}

# Mutual Funds
MUTUAL_FUNDS_COIN = [
    {"name": "ICICI Prudential Short Term Fund - Direct", "category": "Debt"},
    {"name": "Axis Large Cap Fund - Direct", "category": "Large Cap Equity"},
    {"name": "Axis NASDAQ 100 US Equity Passive FOF - Direct", "category": "US Tech"},
    {"name": "Canara Robeco ELSS Tax Saver - Direct", "category": "ELSS/Tax saving"},
    {"name": "Edelweiss Nifty Smallcap 250 Index - Direct", "category": "Small Cap"},
    {"name": "ICICI Prudential Nifty 50 Index - Direct", "category": "Large Cap Index", "note": "core holding"},
    {"name": "Kotak Nifty Next 50 Index - Direct", "category": "Next 50 Index"},
    {"name": "Kotak Small Cap Fund - Direct", "category": "Small Cap Active"},
    {"name": "Mirae Asset ELSS Tax Saver - Direct", "category": "ELSS/Tax saving", "note": "core holding"},
    {"name": "Navi Nifty Midcap 150 Index - Direct", "category": "Mid Cap"},
    {"name": "Navi Total Stock Market US Equity FOF - Direct", "category": "US Market"},
    {"name": "Nippon India Nifty 50 Index - Direct", "category": "Large Cap Index"},
    {"name": "Parag Parikh Flexi Cap Fund - Direct", "category": "Flexi Cap", "note": "core holding"},
    {"name": "Quant Flexi Cap Fund - Direct", "category": "Flexi Cap Active"}
]

MUTUAL_FUNDS_UPSTOX = [
    {"name": "Kotak Multicap Fund", "category": "Multi Cap"},
    {"name": "Kotak Debt Hybrid Fund", "category": "Debt Hybrid"},
    {"name": "ICICI Prudential Equity Savings Fund", "category": "Conservative Hybrid"},
    {"name": "Kotak Equity Savings Fund", "category": "Conservative Hybrid"}
]

# US Stocks
US_STOCKS = {
    "META": {"name": "Meta Platforms", "sector": "Social Media/AI"},
    "MSFT": {"name": "Microsoft", "sector": "Cloud/AI"},
    "AMZN": {"name": "Amazon", "sector": "Ecommerce/Cloud"},
    "GOOGL": {"name": "Alphabet", "sector": "Search/AI"},
    "NVDA": {"name": "NVIDIA", "sector": "AI Chips"},
    "IBIT": {"name": "iShares Bitcoin ETF", "sector": "Crypto"},
    "SOXX": {"name": "iShares Semiconductor ETF", "sector": "Semiconductor"}
}

# Portfolio Strategy
PORTFOLIO_STRATEGY = {
    "core_theme": "Long-term wealth creation, diversified across asset classes",
    "characteristics": [
        "Heavy banking/finance tilt in Indian stocks (concentrated sector bet)",
        "Significant gold allocation as inflation hedge and safe haven",
        "US tech exposure via 3 routes: direct stocks + Axis NASDAQ FOF + Navi US FOF",
        "ELSS funds serve dual purpose: returns + 80C tax saving",
        "Mix of active and passive index funds",
        "Conservative hybrid funds for stability (Upstox)",
        "Crypto exposure via IBIT (indirect, regulated ETF)",
        "Semiconductor theme via SOXX (AI infrastructure play)",
        "FD, RD, PF, NPS for fixed income and retirement",
        "Medium-aggressive profile: smallcap, midcap, flexi cap, US tech"
    ]
}

# ── MCP Server Setup ───────────────────────────────────────────────────────────

server = Server("portfolio-context-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="get_investor_profile",
            description="Get investor profile information (age, risk appetite, goals)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_holdings_list",
            description="Get complete list of holdings (stocks, mutual funds, ETFs)",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["detailed", "brief"],
                        "description": "Output format: 'detailed' includes sector/category info, 'brief' is just names",
                        "default": "detailed"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_sector_exposure",
            description="Get sector exposure breakdown for Indian stocks",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_portfolio_strategy",
            description="Get portfolio strategy, characteristics, and investment themes",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_stock_list",
            description="Get list of stocks by market (Indian or US)",
            inputSchema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["indian", "us", "all"],
                        "description": "Which market stocks to return",
                        "default": "all"
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "get_investor_profile":
            return [TextContent(
                type="text",
                text=json.dumps(INVESTOR_PROFILE, indent=2)
            )]

        elif name == "get_holdings_list":
            fmt = arguments.get("format", "detailed")

            if fmt == "brief":
                result = {
                    "indian_stocks": list(INDIAN_STOCKS.keys()),
                    "us_stocks": list(US_STOCKS.keys()),
                    "mutual_funds_coin": [mf["name"] for mf in MUTUAL_FUNDS_COIN],
                    "mutual_funds_upstox": [mf["name"] for mf in MUTUAL_FUNDS_UPSTOX]
                }
            else:  # detailed
                result = {
                    "indian_stocks": INDIAN_STOCKS,
                    "us_stocks": US_STOCKS,
                    "mutual_funds_coin": MUTUAL_FUNDS_COIN,
                    "mutual_funds_upstox": MUTUAL_FUNDS_UPSTOX
                }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_sector_exposure":
            result = {
                "sector_groups": SECTOR_GROUPS,
                "summary": {
                    sector: len(stocks)
                    for sector, stocks in SECTOR_GROUPS.items()
                }
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_portfolio_strategy":
            return [TextContent(
                type="text",
                text=json.dumps(PORTFOLIO_STRATEGY, indent=2)
            )]

        elif name == "get_stock_list":
            market = arguments.get("market", "all").lower()

            if market == "indian":
                result = {"stocks": INDIAN_STOCKS}
            elif market == "us":
                result = {"stocks": US_STOCKS}
            else:  # all
                result = {
                    "indian_stocks": INDIAN_STOCKS,
                    "us_stocks": US_STOCKS
                }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)})
        )]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
