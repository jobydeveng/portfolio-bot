"""
AI-powered Portfolio Telegram Bot V2 — Local Development Version
Windows-friendly: Uses direct MCP server imports instead of stdio

- Multi-agent architecture (orchestrator, portfolio, market, chart agents)
- Direct MCP server function calls (no stdio subprocess issues)
- Voice input via Whisper
- Chart generation
"""

import os
import sys
import logging
import tempfile
import asyncio
import json
from datetime import datetime, timedelta
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction

# Add MCP server paths
sys.path.insert(0, "mcp_servers/google_sheets_server")
sys.path.insert(0, "mcp_servers/market_data_server")
sys.path.insert(0, "mcp_servers/portfolio_context_server")

# Import MCP server modules directly
import mcp_servers.google_sheets_server.server as sheets_server
import mcp_servers.market_data_server.server as market_server
import mcp_servers.portfolio_context_server.server as context_server

# Import agent system
from bot_agents import OrchestratorAgent
from bot_agents.chart_utils import render_chart_from_spec

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
SHEET_ID = os.environ.get("SHEET_ID", "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE")
API_KEY = os.environ.get("SHEETS_API_KEY", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:8501")

if not BOT_TOKEN or not OPENAI_KEY:
    logger.error("Missing required environment variables! Set TELEGRAM_BOT_TOKEN and OPENAI_API_KEY")
    sys.exit(1)

openai_client = OpenAI(api_key=OPENAI_KEY)

# Mock MCP Clients (Windows-friendly)
mcp_clients = {}

# Orchestrator Agent (initialized in setup)
orchestrator = None

# Conversation state
conversation_history = {}
HISTORY_LIMIT = 3
HISTORY_TTL = timedelta(minutes=30)
last_activity = {}


# ── Mock MCP Client Implementation ────────────────────────────────────────────

class MockMCPClient:
    """Mock MCP client that calls server functions directly (Windows-friendly)"""

    def __init__(self, server_module, server_name):
        self.server_module = server_module
        self.server_name = server_name
        self.logger = logging.getLogger(f"mcp.{server_name}")

    async def call_tool(self, tool_name, arguments):
        """Mock MCP call_tool by calling server functions directly"""
        self.logger.info(f"Calling {tool_name} with {arguments}")

        try:
            # Route to appropriate server
            if self.server_name == "sheets":
                result = await self._call_sheets_tool(tool_name, arguments)
            elif self.server_name == "market":
                result = await self._call_market_tool(tool_name, arguments)
            elif self.server_name == "context":
                result = await self._call_context_tool(tool_name, arguments)
            else:
                result = {"error": f"Unknown server: {self.server_name}"}

            # Return in MCP format
            class MockTextContent:
                def __init__(self, text):
                    self.text = text

            return [MockTextContent(json.dumps(result))]

        except Exception as e:
            self.logger.error(f"Tool call failed: {e}", exc_info=True)
            return [MockTextContent(json.dumps({"error": str(e)}))]

    async def _call_sheets_tool(self, tool_name, arguments):
        """Call Google Sheets server functions"""
        if tool_name == "fetch_sheet_tabs":
            tabs = self.server_module.get_sheet_tabs()
            return {"tabs": tabs}

        elif tool_name == "fetch_sheet_data":
            sheet_name = arguments["sheet_name"]
            rows = self.server_module.fetch_sheet(sheet_name)
            cats = self.server_module.parse_categories(rows)
            total = self.server_module.parse_total(rows)
            return {"sheet_name": sheet_name, "total": total, "categories": cats, "raw_rows_count": len(rows)}

        elif tool_name == "get_latest_portfolio":
            tabs = self.server_module.get_sheet_tabs()
            latest_tab = tabs[-1]
            rows = self.server_module.fetch_sheet(latest_tab)
            cats = self.server_module.parse_categories(rows)
            total = self.server_module.parse_total(rows)
            return {"month": latest_tab, "total": total, "categories": cats}

        elif tool_name == "get_portfolio_history":
            limit = arguments.get("limit")
            tabs = self.server_module.get_sheet_tabs()
            if limit and limit > 0:
                tabs = tabs[-limit:]
            all_data = []
            for tab in tabs:
                rows = self.server_module.fetch_sheet(tab)
                cats = self.server_module.parse_categories(rows)
                total = self.server_module.parse_total(rows)
                all_data.append({"month": tab, "total": total, "categories": cats})
            return {"history": all_data}

        elif tool_name == "get_month_portfolio":
            month_query = arguments["month_query"]
            tabs = self.server_module.get_sheet_tabs()
            tab = self.server_module.find_tab_by_month(tabs, month_query)
            if not tab:
                return {"error": f"No sheet found for month: {month_query}"}
            rows = self.server_module.fetch_sheet(tab)
            cats = self.server_module.parse_categories(rows)
            total = self.server_module.parse_total(rows)
            return {"month": tab, "total": total, "categories": cats}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _call_market_tool(self, tool_name, arguments):
        """Call Market Data server functions"""
        # Import yfinance here to avoid startup delay
        import yfinance as yf

        if tool_name == "get_stock_price":
            ticker = self.server_module.normalize_ticker(arguments["ticker"])
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if hist.empty:
                    return {"error": f"No data found for {ticker}"}
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                change = current - prev
                pct_change = (change / prev * 100) if prev else 0
                return {
                    "ticker": ticker,
                    "current_price": round(current, 2),
                    "previous_close": round(prev, 2),
                    "change": round(change, 2),
                    "percent_change": round(pct_change, 2)
                }
            except Exception as e:
                return {"error": f"Failed to fetch price for {ticker}: {str(e)}"}

        elif tool_name == "get_stock_info":
            ticker = self.server_module.normalize_ticker(arguments["ticker"])
            try:
                t = yf.Ticker(ticker)
                info = t.info
                hist = t.history(period="1y")
                if hist.empty:
                    return {"error": f"No data found for {ticker}"}
                current = float(hist["Close"].iloc[-1])
                high52 = float(hist["High"].max())
                low52 = float(hist["Low"].min())
                pct_from_high = ((current - high52) / high52 * 100)
                pct_from_low = ((current - low52) / low52 * 100)
                return {
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
            except Exception as e:
                return {"error": f"Failed to fetch info for {ticker}: {str(e)}"}

        elif tool_name == "get_market_indices":
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
                except:
                    pass
            return result

        elif tool_name == "get_portfolio_stocks":
            tickers = {
                "HDFCBANK.NS": "HDFC Bank", "ICICIBANK.NS": "ICICI Bank",
                "RELIANCE.NS": "Reliance", "BAJFINANCE.NS": "Bajaj Finance",
                "SBIN.NS": "SBI", "AXISBANK.NS": "Axis Bank",
                "ITC.NS": "ITC", "GOLDBEES.NS": "Gold BeES",
                "META": "META", "MSFT": "Microsoft",
                "AMZN": "Amazon", "GOOGL": "Google", "NVDA": "NVIDIA"
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
                            "name": name, "ticker": symbol,
                            "current": round(current, 2),
                            "change": round(change, 2),
                            "percent_change": round(pct_change, 2)
                        })
                except:
                    pass
            return result

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _call_context_tool(self, tool_name, arguments):
        """Call Portfolio Context server functions"""
        if tool_name == "get_investor_profile":
            return self.server_module.INVESTOR_PROFILE

        elif tool_name == "get_holdings_list":
            fmt = arguments.get("format", "detailed")
            if fmt == "brief":
                return {
                    "indian_stocks": list(self.server_module.INDIAN_STOCKS.keys()),
                    "us_stocks": list(self.server_module.US_STOCKS.keys()),
                    "mutual_funds_coin": [mf["name"] for mf in self.server_module.MUTUAL_FUNDS_COIN],
                    "mutual_funds_upstox": [mf["name"] for mf in self.server_module.MUTUAL_FUNDS_UPSTOX]
                }
            else:
                return {
                    "indian_stocks": self.server_module.INDIAN_STOCKS,
                    "us_stocks": self.server_module.US_STOCKS,
                    "mutual_funds_coin": self.server_module.MUTUAL_FUNDS_COIN,
                    "mutual_funds_upstox": self.server_module.MUTUAL_FUNDS_UPSTOX
                }

        elif tool_name == "get_sector_exposure":
            return {
                "sector_groups": self.server_module.SECTOR_GROUPS,
                "summary": {sector: len(stocks) for sector, stocks in self.server_module.SECTOR_GROUPS.items()}
            }

        elif tool_name == "get_portfolio_strategy":
            return self.server_module.PORTFOLIO_STRATEGY

        elif tool_name == "get_stock_list":
            market = arguments.get("market", "all").lower()
            if market == "indian":
                return {"stocks": self.server_module.INDIAN_STOCKS}
            elif market == "us":
                return {"stocks": self.server_module.US_STOCKS}
            else:
                return {
                    "indian_stocks": self.server_module.INDIAN_STOCKS,
                    "us_stocks": self.server_module.US_STOCKS
                }

        else:
            return {"error": f"Unknown tool: {tool_name}"}


# ── Agent Setup ────────────────────────────────────────────────────────────────

async def setup_orchestrator():
    """Initialize the orchestrator agent with mock MCP clients"""
    global orchestrator, mcp_clients

    # Create mock MCP clients
    mcp_clients["sheets"] = MockMCPClient(sheets_server, "sheets")
    mcp_clients["market"] = MockMCPClient(market_server, "market")
    mcp_clients["context"] = MockMCPClient(context_server, "context")

    logger.info("Mock MCP clients created (Windows-friendly mode)")

    orchestrator = OrchestratorAgent(openai_client, mcp_clients)
    logger.info("Orchestrator agent initialized")


# ── Conversation State Management ──────────────────────────────────────────────

def add_to_history(user_id: int, role: str, content: str):
    """Add message to conversation history"""
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": role, "content": content})
    if len(conversation_history[user_id]) > HISTORY_LIMIT:
        conversation_history[user_id] = conversation_history[user_id][-HISTORY_LIMIT:]
    last_activity[user_id] = datetime.now()


def get_history(user_id: int) -> list:
    """Get conversation history for user"""
    if user_id in last_activity:
        if datetime.now() - last_activity[user_id] > HISTORY_TTL:
            conversation_history.pop(user_id, None)
            last_activity.pop(user_id, None)
            return []
    return conversation_history.get(user_id, [])


# ── Telegram Handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome = f"""👋 *Welcome to your AI Portfolio Assistant!*

I can help you with:
• 📊 Portfolio analysis and tracking
• 📈 Market insights and stock valuations
• 💡 Investment opportunities
• 📉 Charts and visualizations
• 🎤 Voice queries (just send a voice message!)

*Try asking:*
- "Show my portfolio"
- "Why is the market down today?"
- "What should I buy?"
- "Show me a pie chart"
- "Is HDFC Bank overvalued?"

Or use quick commands:
/portfolio - Get current portfolio summary
/help - Show this message

🔗 [View Dashboard]({APP_URL})

_Running in local development mode (Windows-friendly)_
"""
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /portfolio command"""
    await process_ai_query(update, context, "Show me my latest portfolio summary")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await start(update, context)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages via Whisper transcription"""
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await voice_file.download_to_drive(tmp.name)
            with open(tmp.name, "rb") as audio:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1", file=audio, language="en"
                )
        text = transcript.text.strip()
        await update.message.reply_text(f'Heard: "{text}"')
        await process_ai_query(update, context, text)
    except Exception as e:
        logger.error(f"Voice processing error: {e}", exc_info=True)
        await update.message.reply_text(f"Could not process voice: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    await process_ai_query(update, context, update.message.text.strip())


async def process_ai_query(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Main query processing function - routes to orchestrator"""
    await update.message.chat.send_action(ChatAction.TYPING)
    user_id = update.effective_user.id

    try:
        history = get_history(user_id)
        add_to_history(user_id, "user", text)

        query_context = {
            "user_id": user_id,
            "conversation_history": history
        }

        # Call orchestrator
        result = await orchestrator.process(text, query_context)

        if result.get("text"):
            add_to_history(user_id, "assistant", result["text"])

        response_type = result.get("response_type", "text")

        if response_type == "text":
            await update.message.reply_text(result["text"])

        elif response_type == "chart":
            chart_spec = result.get("chart")
            if chart_spec:
                try:
                    chart_image = render_chart_from_spec(chart_spec)
                    await update.message.reply_photo(
                        photo=chart_image,
                        caption=result.get("text", "Chart generated")
                    )
                except Exception as e:
                    logger.error(f"Chart rendering error: {e}", exc_info=True)
                    await update.message.reply_text(f"Chart generation failed: {str(e)}")
            else:
                await update.message.reply_text("Chart data not available")

        elif response_type == "both":
            await update.message.reply_text(result["text"])
            chart_spec = result.get("chart")
            if chart_spec:
                try:
                    chart_image = render_chart_from_spec(chart_spec)
                    await update.message.reply_photo(photo=chart_image)
                except Exception as e:
                    logger.error(f"Chart rendering error: {e}", exc_info=True)

        else:
            await update.message.reply_text("Something went wrong processing your request")

    except Exception as e:
        logger.error(f"Query processing error: {e}", exc_info=True)
        await update.message.reply_text(
            f"Sorry, something went wrong: {str(e)}\n\nPlease try again or rephrase your question."
        )


# ── Bot Setup ──────────────────────────────────────────────────────────────────

def setup_bot_handlers(application):
    """Setup all Telegram bot handlers"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("portfolio", portfolio_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


def main():
    """Main entry point for local development (polling mode)"""
    logger.info("Starting bot in LOCAL DEVELOPMENT mode (Windows-friendly)...")
    logger.info("Using direct MCP server imports instead of stdio")

    # Setup orchestrator with mock clients (run in async context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_orchestrator())

    # Build bot with SSL workaround for Windows
    import ssl
    import certifi
    import httpx

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # Create httpx client with proper SSL context
    http_client = httpx.AsyncClient(
        verify=ssl_context,
        timeout=30.0
    )

    # Build application with custom httpx client
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(http_version="1.1", client=http_client)

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )
    setup_bot_handlers(application)

    logger.info("Bot started successfully in polling mode")
    logger.info("Send a message to your Telegram bot to test!")

    # Run polling (this handles its own event loop)
    application.run_polling()


if __name__ == "__main__":
    main()
