#!/usr/bin/env python3
"""
Market Data MCP Server using yfinance
Provides tools to fetch live market data, stock prices, and analysis
"""

import os
import json
import logging
import yfinance as yf
from datetime import datetime, timedelta
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("market_data_server")

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


def normalize_ticker(symbol: str) -> str:
    """Normalize ticker symbol - add .NS for Indian stocks if needed"""
    symbol = symbol.upper().strip()
    # If it's already a full symbol (has .NS or starts with ^), return as-is
    if symbol.endswith(".NS") or symbol.startswith("^"):
        return symbol
    # Common US stock symbols (don't add .NS)
    us_symbols = {"META", "MSFT", "AMZN", "GOOGL", "AAPL", "NVDA", "TSLA",
                  "IBIT", "SOXX", "QQQ", "SPY", "IWM"}
    if symbol in us_symbols:
        return symbol
    # Default: assume Indian stock, add .NS
    return f"{symbol}.NS"


# ── MCP Server Setup ───────────────────────────────────────────────────────────

server = Server("market-data-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="get_stock_price",
            description="Get current price and change for a stock ticker",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'HDFCBANK' for Indian stocks, 'MSFT' for US stocks). Indian stocks will auto-add .NS suffix."
                    }
                },
                "required": ["ticker"]
            }
        ),
        Tool(
            name="get_stock_info",
            description="Get detailed information about a stock (PE, PB, 52-week high/low, market cap, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    }
                },
                "required": ["ticker"]
            }
        ),
        Tool(
            name="get_historical_data",
            description="Get historical price data for a stock",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period (e.g., '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')",
                        "default": "1y"
                    }
                },
                "required": ["ticker"]
            }
        ),
        Tool(
            name="get_market_indices",
            description="Get current prices for major Indian and US market indices",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_portfolio_stocks",
            description="Get live prices for a predefined list of portfolio stocks (Indian and US)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "get_stock_price":
            ticker_input = arguments["ticker"]
            ticker = normalize_ticker(ticker_input)

            cache_key = f"price_{ticker}"
            cached = _get_cached(cache_key)
            if cached is not None:
                return [TextContent(type="text", text=json.dumps(cached, indent=2))]

            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")

                if hist.empty:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": f"No data found for {ticker}"})
                    )]

                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                change = current - prev
                pct_change = (change / prev * 100) if prev else 0

                result = {
                    "ticker": ticker,
                    "current_price": round(current, 2),
                    "previous_close": round(prev, 2),
                    "change": round(change, 2),
                    "percent_change": round(pct_change, 2)
                }

                _set_cache(cache_key, result)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Failed to fetch price for {ticker}: {str(e)}"})
                )]

        elif name == "get_stock_info":
            ticker_input = arguments["ticker"]
            ticker = normalize_ticker(ticker_input)

            cache_key = f"info_{ticker}"
            cached = _get_cached(cache_key)
            if cached is not None:
                return [TextContent(type="text", text=json.dumps(cached, indent=2))]

            try:
                t = yf.Ticker(ticker)
                info = t.info
                hist = t.history(period="1y")

                if hist.empty:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": f"No data found for {ticker}"})
                    )]

                current = float(hist["Close"].iloc[-1])
                high52 = float(hist["High"].max())
                low52 = float(hist["Low"].min())
                pct_from_high = ((current - high52) / high52 * 100)
                pct_from_low = ((current - low52) / low52 * 100)

                result = {
                    "ticker": ticker,
                    "name": info.get("longName", ticker),
                    "current_price": round(current, 2),
                    "52_week_high": round(high52, 2),
                    "52_week_low": round(low52, 2),
                    "pct_from_high": round(pct_from_high, 2),
                    "pct_from_low": round(pct_from_low, 2),
                    "pe_ratio": info.get("trailingPE"),
                    "pb_ratio": info.get("priceToBook"),
                    "market_cap": info.get("marketCap"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry")
                }

                _set_cache(cache_key, result)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Failed to fetch info for {ticker}: {str(e)}"})
                )]

        elif name == "get_historical_data":
            ticker_input = arguments["ticker"]
            period = arguments.get("period", "1y")
            ticker = normalize_ticker(ticker_input)

            try:
                t = yf.Ticker(ticker)
                hist = t.history(period=period)

                if hist.empty:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": f"No data found for {ticker}"})
                    )]

                # Convert to list of dicts for JSON serialization
                data = []
                for date, row in hist.iterrows():
                    data.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "volume": int(row["Volume"])
                    })

                result = {
                    "ticker": ticker,
                    "period": period,
                    "data_points": len(data),
                    "data": data
                }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Failed to fetch historical data for {ticker}: {str(e)}"})
                )]

        elif name == "get_market_indices":
            cache_key = "market_indices"
            cached = _get_cached(cache_key)
            if cached is not None:
                return [TextContent(type="text", text=json.dumps(cached, indent=2))]

            indices = {
                "^NSEI": "Nifty 50",
                "^NSEBANK": "BankNifty",
                "^GSPC": "S&P 500",
                "^IXIC": "NASDAQ",
                "^DJI": "Dow Jones"
            }

            result = {"indices": []}
            for symbol, name in indices.items():
                try:
                    t = yf.Ticker(symbol)
                    hist = t.history(period="5d")
                    if not hist.empty:
                        current = float(hist["Close"].iloc[-1])
                        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                        change = current - prev
                        pct_change = (change / prev * 100) if prev else 0

                        result["indices"].append({
                            "name": name,
                            "symbol": symbol,
                            "current": round(current, 2),
                            "change": round(change, 2),
                            "percent_change": round(pct_change, 2)
                        })
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol}: {e}")

            _set_cache(cache_key, result)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_portfolio_stocks":
            cache_key = "portfolio_stocks"
            cached = _get_cached(cache_key)
            if cached is not None:
                return [TextContent(type="text", text=json.dumps(cached, indent=2))]

            # Key portfolio stocks
            tickers = {
                # Indian stocks
                "HDFCBANK.NS": "HDFC Bank",
                "ICICIBANK.NS": "ICICI Bank",
                "RELIANCE.NS": "Reliance",
                "BAJFINANCE.NS": "Bajaj Finance",
                "SBIN.NS": "SBI",
                "AXISBANK.NS": "Axis Bank",
                "ITC.NS": "ITC",
                "GOLDBEES.NS": "Gold BeES",
                # US stocks
                "META": "META",
                "MSFT": "Microsoft",
                "AMZN": "Amazon",
                "GOOGL": "Google",
                "NVDA": "NVIDIA"
            }

            result = {"stocks": []}
            for symbol, name in tickers.items():
                try:
                    t = yf.Ticker(symbol)
                    hist = t.history(period="5d")
                    if not hist.empty:
                        current = float(hist["Close"].iloc[-1])
                        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                        change = current - prev
                        pct_change = (change / prev * 100) if prev else 0

                        result["stocks"].append({
                            "name": name,
                            "ticker": symbol,
                            "current": round(current, 2),
                            "change": round(change, 2),
                            "percent_change": round(pct_change, 2)
                        })
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol}: {e}")

            _set_cache(cache_key, result)
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
