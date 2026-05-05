"""
AI-powered Portfolio Telegram Bot V2 — Multi-Agent with MCP
- Multi-agent architecture (orchestrator, portfolio, market, chart agents)
- MCP servers for Google Sheets, Market Data, Portfolio Context
- Voice input via Whisper
- Chart generation
"""

import os
import sys
import logging
import tempfile
import asyncio
import subprocess
from datetime import datetime, timedelta
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import agent system
from bot_agents import OrchestratorAgent
from bot_agents.chart_utils import render_chart_from_spec

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_KEY = os.environ["OPENAI_API_KEY"]
SHEET_ID = os.environ.get("SHEET_ID", "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE")
API_KEY = os.environ.get("SHEETS_API_KEY", "")
APP_URL = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")

openai_client = OpenAI(api_key=OPENAI_KEY)

# MCP Clients (global, initialized in setup)
mcp_clients = {}

# Orchestrator Agent (global, initialized in setup)
orchestrator = None

# Conversation state (simple in-memory storage)
conversation_history = {}  # {user_id: [messages]}
HISTORY_LIMIT = 3  # Keep last 3 messages per user
HISTORY_TTL = timedelta(minutes=30)
last_activity = {}  # {user_id: timestamp}


# ── MCP Setup ──────────────────────────────────────────────────────────────────

async def start_mcp_server(server_path: str, server_name: str):
    """
    Start an MCP server as a stdio subprocess and return client session context

    Args:
        server_path: Path to server.py file
        server_name: Name for logging

    Returns:
        Tuple of (read_stream, write_stream) for creating ClientSession
    """
    logger.info(f"Starting MCP server: {server_name} at {server_path}")

    # Set environment variables for MCP servers
    env = os.environ.copy()
    env["SHEET_ID"] = SHEET_ID
    env["SHEETS_API_KEY"] = API_KEY

    # Server parameters
    server_params = StdioServerParameters(
        command=sys.executable,  # Python interpreter
        args=[server_path],
        env=env
    )

    # Return the context manager
    return stdio_client(server_params)


async def setup_mcp_clients():
    """Initialize all MCP client sessions"""
    global mcp_clients

    try:
        # Start Google Sheets server
        sheets_ctx = await start_mcp_server(
            "mcp_servers/google_sheets_server/server.py",
            "google-sheets"
        )
        read_s, write_s = await sheets_ctx.__aenter__()
        sheets_session = ClientSession(read_s, write_s)
        await sheets_session.initialize()
        mcp_clients["sheets"] = sheets_session

        # Start Market Data server
        market_ctx = await start_mcp_server(
            "mcp_servers/market_data_server/server.py",
            "market-data"
        )
        read_m, write_m = await market_ctx.__aenter__()
        market_session = ClientSession(read_m, write_m)
        await market_session.initialize()
        mcp_clients["market"] = market_session

        # Start Portfolio Context server
        context_ctx = await start_mcp_server(
            "mcp_servers/portfolio_context_server/server.py",
            "portfolio-context"
        )
        read_c, write_c = await context_ctx.__aenter__()
        context_session = ClientSession(read_c, write_c)
        await context_session.initialize()
        mcp_clients["context"] = context_session

        logger.info("All MCP clients initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize MCP clients: {e}", exc_info=True)
        raise


# ── Agent Setup ────────────────────────────────────────────────────────────────

async def setup_orchestrator():
    """Initialize the orchestrator agent"""
    global orchestrator

    if not mcp_clients:
        raise RuntimeError("MCP clients not initialized. Call setup_mcp_clients() first.")

    orchestrator = OrchestratorAgent(openai_client, mcp_clients)
    logger.info("Orchestrator agent initialized")


# ── Conversation State Management ──────────────────────────────────────────────

def add_to_history(user_id: int, role: str, content: str):
    """Add message to conversation history"""
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": role,
        "content": content
    })

    # Keep only last N messages
    if len(conversation_history[user_id]) > HISTORY_LIMIT:
        conversation_history[user_id] = conversation_history[user_id][-HISTORY_LIMIT:]

    # Update last activity
    last_activity[user_id] = datetime.now()


def get_history(user_id: int) -> list:
    """Get conversation history for user"""
    # Clean up stale history
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
    """
    Main query processing function - routes to orchestrator

    Args:
        update: Telegram update
        context: Telegram context
        text: User query text
    """
    await update.message.chat.send_action(ChatAction.TYPING)

    user_id = update.effective_user.id

    try:
        # Get conversation history
        history = get_history(user_id)

        # Add user message to history
        add_to_history(user_id, "user", text)

        # Build context for orchestrator
        query_context = {
            "user_id": user_id,
            "conversation_history": history
        }

        # Call orchestrator
        result = await orchestrator.process(text, query_context)

        # Add assistant response to history
        if result.get("text"):
            add_to_history(user_id, "assistant", result["text"])

        # Handle response based on type
        response_type = result.get("response_type", "text")

        if response_type == "text":
            # Text-only response
            await update.message.reply_text(result["text"])

        elif response_type == "chart":
            # Chart-only response
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
            # Text + Chart
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


async def main():
    """Main entry point for standalone bot (polling mode)"""
    logger.info("Starting bot in polling mode...")

    # Setup MCP clients
    await setup_mcp_clients()

    # Setup orchestrator
    await setup_orchestrator()

    # Build and start bot
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    setup_bot_handlers(application)

    logger.info("Bot started successfully in polling mode")
    await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
