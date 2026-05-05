# Multi-Agent Portfolio Bot Architecture

## Overview

This project has been refactored into a **multi-agent architecture** with **MCP (Model Context Protocol) integration**. The new design separates concerns, makes the system extensible, and follows best practices for agentic AI applications.

## Components

### 1. MCP Servers (Data Layer)

Located in `mcp_servers/`, these are standalone servers that provide data access via MCP protocol:

#### Google Sheets Server (`google_sheets_server/`)
- **Purpose**: Access portfolio data from Google Sheets
- **Tools**:
  - `fetch_sheet_tabs()` - Get all sheet tab names
  - `fetch_sheet_data(sheet_name)` - Get specific sheet data
  - `get_latest_portfolio()` - Get current month's portfolio
  - `get_portfolio_history(limit)` - Get historical data
  - `get_month_portfolio(month_query)` - Get specific month by name
- **Caching**: 5-minute TTL for all data
- **Testing**: Run `python mcp_servers/google_sheets_server/test_client.py`

#### Market Data Server (`market_data_server/`)
- **Purpose**: Live market data via yfinance
- **Tools**:
  - `get_stock_price(ticker)` - Current price and change
  - `get_stock_info(ticker)` - PE, PB, 52W high/low, market cap
  - `get_historical_data(ticker, period)` - Historical prices
  - `get_market_indices()` - Major Indian and US indices
  - `get_portfolio_stocks()` - Live prices for portfolio stocks
- **Features**: Auto-adds `.NS` suffix for Indian stocks, 5-minute cache
- **Testing**: Create `test_client.py` similar to sheets server

#### Portfolio Context Server (`portfolio_context_server/`)
- **Purpose**: Structured portfolio holdings and context (replaces hardcoded HOLDINGS_CONTEXT)
- **Tools**:
  - `get_investor_profile()` - User profile (age, risk appetite, goals)
  - `get_holdings_list(format)` - All holdings (stocks, MFs, ETFs)
  - `get_sector_exposure()` - Sector breakdown for Indian stocks
  - `get_portfolio_strategy()` - Investment strategy and themes
  - `get_stock_list(market)` - Stocks by market (Indian, US, all)
- **Data**: Currently static (from original HOLDINGS_CONTEXT), but designed to be dynamic

### 2. Agent System (Intelligence Layer)

Located in `bot_agents/`, these are specialized AI agents powered by GPT-4o:

#### Base Agent (`base_agent.py`)
- Abstract base class for all agents
- Common functionality: MCP tool calling, LLM integration, logging
- Handles tool result parsing and error handling

#### Portfolio Agent (`portfolio_agent.py`)
- **Specialty**: Portfolio analysis, tracking, month comparisons
- **MCP Servers Used**: Google Sheets, Portfolio Context
- **System Prompt**: Expert in portfolio composition, allocation, tracking
- **Example Queries**: "Show my portfolio", "Compare March vs April", "What's my return this year?"

#### Market Agent (`market_agent.py`)
- **Specialty**: Market analysis, stock valuation, investment opportunities
- **MCP Servers Used**: Market Data, Portfolio Context
- **System Prompt**: Expert in fundamental analysis, market trends, stock evaluation
- **Example Queries**: "Why is market down?", "Is HDFC Bank overvalued?", "What should I buy?"

#### Chart Agent (`chart_agent.py`)
- **Specialty**: Data visualization
- **MCP Servers Used**: Google Sheets
- **System Prompt**: Expert in choosing right visualization for data
- **Returns**: JSON chart specifications (not images)
- **Example Queries**: "Show pie chart", "Show growth trend", "Compare January vs March"

#### Orchestrator Agent (`orchestrator_agent.py`)
- **Role**: Main coordinator that routes queries to specialists
- **Intent Classification**: Uses GPT-4o-mini to classify queries
- **Multi-Agent Workflows**: Can chain multiple agents (e.g., Portfolio → Market for recommendations)
- **Handles**: Simple responses (greetings) without agent calls

### 3. Integration Layer (bot_v2.py)

The main bot that ties everything together:

- **MCP Client Management**: Starts all 3 MCP servers as stdio subprocesses
- **Orchestrator Initialization**: Creates orchestrator with access to all agents
- **Telegram Handlers**: /start, /portfolio, text messages, voice messages
- **Response Formatting**: Converts agent outputs to Telegram messages/photos
- **Conversation State**: Tracks last 3 messages per user (30-minute TTL)
- **Chart Rendering**: Uses `chart_utils.py` to convert chart specs to PNG images

### 4. Chart Utilities (`chart_utils.py`)

- Functions to render matplotlib charts from agent specifications
- Preserves original dark theme (`#0a1628` background)
- Chart types: pie, bar, trend, comparison, stock P&L

## Data Flow

### Example: "Show my portfolio"

```
User → Telegram → bot_v2.py → OrchestratorAgent
                                    ↓ (classifies intent as "portfolio")
                                PortfolioAgent
                                    ↓ (calls MCP tools)
                      Google Sheets MCP Server ← portfolio data
                      Portfolio Context MCP Server ← holdings list
                                    ↓ (GPT-4o analysis)
                                Returns text response
                                    ↓
                         bot_v2.py formats & sends
                                    ↓
                                Telegram → User
```

### Example: "What should I buy?"

```
User → Telegram → bot_v2.py → OrchestratorAgent
                                    ↓ (classifies as "market" + needs portfolio context)
                                PortfolioAgent (fetch current portfolio)
                                    ↓
                                MarketAgent (with portfolio context)
                                    ↓ (calls MCP tools)
                      Market Data MCP Server ← live stock prices, PE ratios
                      Portfolio Context MCP Server ← sector exposure
                                    ↓ (GPT-4o analysis with live data)
                                Returns investment recommendations
                                    ↓
                         bot_v2.py formats & sends
                                    ↓
                                Telegram → User
```

### Example: "Show pie chart"

```
User → Telegram → bot_v2.py → OrchestratorAgent
                                    ↓ (classifies as "chart")
                                ChartAgent
                                    ↓ (calls MCP tools)
                      Google Sheets MCP Server ← latest portfolio
                                    ↓ (GPT-4o generates chart spec)
                                Returns JSON chart config
                                    ↓
                         bot_v2.py → chart_utils.render_chart_from_spec()
                                    ↓ (matplotlib generates PNG)
                                Sends photo to Telegram
                                    ↓
                                Telegram → User
```

## Key Design Decisions

### Why MCP?
- **Separation of Concerns**: Data access logic separated from bot logic
- **Reusability**: MCP servers can be used by other apps (Claude Desktop, future projects)
- **Testability**: Each MCP server can be tested independently
- **Extensibility**: Easy to add new data sources (Zerodha API, news APIs) without touching bot code

### Why Multi-Agent?
- **Focused Expertise**: Each agent has a specialized system prompt and tools
- **Better Prompts**: Shorter, domain-specific prompts instead of one monolithic prompt
- **Scalability**: Easy to add new agents (e.g., news analyst, tax planner)
- **Debugging**: Easier to trace issues to specific agents

### Why Orchestrator Pattern?
- **Smart Routing**: Intent classification routes to right specialist
- **Multi-Step Workflows**: Can chain agents for complex queries
- **Fallback Handling**: Handles simple queries without agent calls

## Running the System

### Local Development (Polling Mode)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables in .streamlit/secrets.toml
# TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, SHEETS_API_KEY, SHEET_ID

# Run bot
python bot_v2.py
```

### Production (Webhook Mode on Render)

- Update `webhook_app.py` to import `bot_v2` instead of `bot` (line 14)
- Deploy to Render with existing `render.yaml`
- MCP servers run as stdio subprocesses within the same container

## Testing

### Test MCP Servers

```bash
# Google Sheets server
cd mcp_servers/google_sheets_server
python test_client.py

# Market Data server (create test_client.py)
cd mcp_servers/market_data_server
python test_client.py
```

### Test Bot Locally

1. Use a separate Telegram bot token for testing
2. Run `python bot_v2.py` in polling mode
3. Test queries:
   - "Show my portfolio"
   - "Why is market down?"
   - "Show pie chart"
   - "What should I buy?"

## Migration Path

1. **Test bot_v2.py locally** with separate bot token
2. **Verify all queries work** (portfolio, market, charts, voice)
3. **Update webhook_app.py** import: `import bot_v2 as bot`
4. **Deploy to Render** and monitor logs
5. **Keep bot.py as backup** - don't delete until bot_v2 is stable

## Future Enhancements

Once the multi-agent MCP architecture is working:

1. **Add new MCP servers**:
   - News API server (market news, stock-specific news)
   - Zerodha API server (live holdings, P&L)
   - Economic indicators server (inflation, interest rates)

2. **Add new agents**:
   - News Analyst Agent (analyze news impact on portfolio)
   - Tax Planning Agent (80C, LTCG, tax harvesting)
   - Rebalancing Agent (suggest portfolio rebalancing)

3. **Enhance orchestrator**:
   - Multi-turn conversations with persistent memory
   - User preferences (save preferred chart types, stocks to track)
   - Scheduled reports (daily/weekly portfolio summaries)

4. **Refactor Streamlit dashboard** (`app.py`):
   - Use same MCP servers for data fetching
   - Real-time market data integration
   - Interactive agent chat in dashboard

## Files Overview

```
portfolio-bot/
├── mcp_servers/
│   ├── google_sheets_server/
│   │   ├── server.py              # Google Sheets MCP server
│   │   ├── requirements.txt
│   │   └── test_client.py
│   ├── market_data_server/
│   │   ├── server.py              # Market data MCP server
│   │   └── requirements.txt
│   └── portfolio_context_server/
│       ├── server.py              # Portfolio context MCP server
│       └── requirements.txt
├── bot_agents/
│   ├── __init__.py
│   ├── base_agent.py              # Base agent class
│   ├── agent_config.py            # System prompts
│   ├── portfolio_agent.py         # Portfolio specialist
│   ├── market_agent.py            # Market specialist
│   ├── chart_agent.py             # Visualization specialist
│   ├── orchestrator_agent.py      # Main coordinator
│   └── chart_utils.py             # Chart rendering functions
├── bot_v2.py                      # New multi-agent bot
├── bot.py                         # Original bot (backup)
├── app.py                         # Streamlit dashboard (unchanged)
├── webhook_app.py                 # Webhook entrypoint (update import)
├── requirements.txt               # Updated with mcp>=1.0.0
├── CLAUDE.md                      # Original project docs
└── ARCHITECTURE.md                # This file
```

## Dependencies

New dependencies added:
- `mcp>=1.0.0` - Model Context Protocol client/server

Existing dependencies (unchanged):
- `openai>=1.12.0` - GPT-4o, Whisper
- `python-telegram-bot>=20.7` - Telegram integration
- `yfinance>=0.2.0` - Market data
- `matplotlib>=3.8.0` - Chart generation
- `streamlit==1.40.1` - Web dashboard
- `flask>=3.0.0` - Webhook server

## Environment Variables

Same as before:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `OPENAI_API_KEY` - For GPT-4o and Whisper
- `SHEETS_API_KEY` - Google Sheets API key
- `SHEET_ID` - Google Sheet ID
- `APP_URL` - Render deployment URL

## Logging

All components use Python's `logging` module:
- MCP servers: `INFO` level
- Agents: `INFO` level (per-agent loggers)
- bot_v2.py: `INFO` level

Monitor logs to debug agent routing, MCP tool calls, and errors.
