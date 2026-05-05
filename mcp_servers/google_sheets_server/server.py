#!/usr/bin/env python3
"""
Google Sheets MCP Server for Portfolio Data
Provides tools to fetch and parse portfolio data from Google Sheets
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google_sheets_server")

# Configuration from environment
SHEET_ID = os.environ.get("SHEET_ID", "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE")
API_KEY = os.environ.get("SHEETS_API_KEY", "")
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

# Simple in-memory cache with TTL
_cache = {}
_cache_ttl = timedelta(minutes=5)


def _get_cached(key: str) -> Any | None:
    """Get cached value if not expired"""
    if key in _cache:
        value, timestamp = _cache[key]
        if datetime.now() - timestamp < _cache_ttl:
            return value
        else:
            del _cache[key]
    return None


def _set_cache(key: str, value: Any) -> None:
    """Set cache value with current timestamp"""
    _cache[key] = (value, datetime.now())


def get_sheet_tabs() -> list[str]:
    """Fetch all sheet tab names from the spreadsheet"""
    cache_key = "sheet_tabs"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    url = f"{SHEETS_API}/{SHEET_ID}"
    params = {"key": API_KEY} if API_KEY else {}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    tabs = [s["properties"]["title"] for s in r.json().get("sheets", [])]

    _set_cache(cache_key, tabs)
    return tabs


def fetch_sheet(tab: str) -> list[list[str]]:
    """Fetch raw data from a specific sheet tab (A1:G25)"""
    cache_key = f"sheet_data_{tab}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    url = f"{SHEETS_API}/{SHEET_ID}/values/{requests.utils.quote(tab)}!A1:G25"
    params = {"key": API_KEY} if API_KEY else {}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    rows = r.json().get("values", [])

    _set_cache(cache_key, rows)
    return rows


def parse_categories(rows: list[list[str]]) -> dict[str, float]:
    """Parse category data from rows (columns F-G, indices 5-6)"""
    cats = {}
    for row in rows:
        if len(row) >= 7:
            cat = row[5].strip()
            val = row[6].replace(",", "").strip()
            if cat and cat not in ("Category", "Total"):
                try:
                    cats[cat] = float(val)
                except ValueError:
                    pass
    return cats


def parse_total(rows: list[list[str]]) -> float:
    """Parse total value from rows"""
    for row in rows:
        if len(row) >= 7 and row[5].strip() == "Total":
            try:
                return float(row[6].replace(",", "").strip())
            except ValueError:
                pass
    return 0.0


def find_tab_by_month(tabs: list[str], query: str) -> str | None:
    """Find a sheet tab by month name (e.g., 'March', 'Apr', 'January')"""
    q = query.lower()
    month_map = {
        "jan": "Jan", "january": "Jan", "feb": "Feb", "february": "Feb",
        "mar": "Mar", "march": "March", "apr": "Apr", "april": "Apr",
        "may": "May", "jun": "Jun", "june": "Jun", "jul": "Jul", "july": "Jul",
        "aug": "Aug", "august": "Aug", "sep": "Sep", "sept": "Sep", "september": "Sep",
        "oct": "Oct", "october": "Oct", "nov": "Nov", "november": "Nov",
        "dec": "Dec", "december": "Dec",
    }
    for kw, abbr in month_map.items():
        if kw in q:
            for tab in tabs:
                if abbr.lower() in tab.lower():
                    return tab
    return None


# ── MCP Server Setup ───────────────────────────────────────────────────────────

server = Server("google-sheets-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="fetch_sheet_tabs",
            description="Get list of all sheet tab names in the portfolio spreadsheet",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="fetch_sheet_data",
            description="Fetch raw portfolio data from a specific sheet tab by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet tab (e.g., 'April2026', 'March2026')"
                    }
                },
                "required": ["sheet_name"]
            }
        ),
        Tool(
            name="get_latest_portfolio",
            description="Get the latest month's portfolio summary (categories and total)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_portfolio_history",
            description="Get portfolio history for all months (totals and categories)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of months to return (default: all)",
                        "default": None
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_month_portfolio",
            description="Get portfolio data for a specific month by name (e.g., 'March', 'April')",
            inputSchema={
                "type": "object",
                "properties": {
                    "month_query": {
                        "type": "string",
                        "description": "Month name or abbreviation (e.g., 'March', 'Apr', 'January')"
                    }
                },
                "required": ["month_query"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "fetch_sheet_tabs":
            tabs = get_sheet_tabs()
            return [TextContent(
                type="text",
                text=json.dumps({"tabs": tabs}, indent=2)
            )]

        elif name == "fetch_sheet_data":
            sheet_name = arguments["sheet_name"]
            rows = fetch_sheet(sheet_name)
            cats = parse_categories(rows)
            total = parse_total(rows)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "sheet_name": sheet_name,
                    "total": total,
                    "categories": cats,
                    "raw_rows_count": len(rows)
                }, indent=2)
            )]

        elif name == "get_latest_portfolio":
            tabs = get_sheet_tabs()
            if not tabs:
                return [TextContent(type="text", text=json.dumps({"error": "No sheets found"}))]

            latest_tab = tabs[-1]  # Last tab is always the latest month
            rows = fetch_sheet(latest_tab)
            cats = parse_categories(rows)
            total = parse_total(rows)

            return [TextContent(
                type="text",
                text=json.dumps({
                    "month": latest_tab,
                    "total": total,
                    "categories": cats
                }, indent=2)
            )]

        elif name == "get_portfolio_history":
            limit = arguments.get("limit")
            tabs = get_sheet_tabs()

            if limit and limit > 0:
                tabs = tabs[-limit:]

            all_data = []
            for tab in tabs:
                rows = fetch_sheet(tab)
                cats = parse_categories(rows)
                total = parse_total(rows)
                all_data.append({
                    "month": tab,
                    "total": total,
                    "categories": cats
                })

            return [TextContent(
                type="text",
                text=json.dumps({"history": all_data}, indent=2)
            )]

        elif name == "get_month_portfolio":
            month_query = arguments["month_query"]
            tabs = get_sheet_tabs()
            tab = find_tab_by_month(tabs, month_query)

            if not tab:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"No sheet found for month: {month_query}"})
                )]

            rows = fetch_sheet(tab)
            cats = parse_categories(rows)
            total = parse_total(rows)

            return [TextContent(
                type="text",
                text=json.dumps({
                    "month": tab,
                    "total": total,
                    "categories": cats
                }, indent=2)
            )]

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
