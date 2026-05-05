# Reusing Portfolio MCP Servers

Your MCP servers are standalone and can be used in multiple ways across different projects.

## Installation for Other Projects

### Option 1: Copy the Server Directory

```bash
# Copy to your new project
cp -r mcp_servers/google_sheets_server /path/to/new-project/
cd /path/to/new-project/google_sheets_server
pip install -r requirements.txt
```

### Option 2: Create a Python Package

Package structure:
```
portfolio-mcp/
├── setup.py
├── portfolio_mcp/
│   ├── __init__.py
│   ├── sheets.py        # Google Sheets server
│   ├── market.py        # Market data server
│   └── context.py       # Portfolio context server
└── README.md
```

Then install in any project:
```bash
pip install -e /path/to/portfolio-mcp
```

## Usage Examples

### 1. Python Script (Direct MCP Connection)

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def get_portfolio():
    server_params = StdioServerParameters(
        command="python",
        args=["path/to/google_sheets_server/server.py"],
        env={
            "SHEET_ID": "your-sheet-id",
            "SHEETS_API_KEY": "your-api-key"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        
        # Get latest portfolio
        result = await session.call_tool("get_latest_portfolio", {})
        data = json.loads(result[0].text)
        return data

# Run
portfolio = asyncio.run(get_portfolio())
print(f"Total: Rs. {portfolio['total']:,.0f}")
```

### 2. FastAPI Application

```python
from fastapi import FastAPI
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

app = FastAPI()

# Initialize MCP client
mcp_client = None

@app.on_event("startup")
async def startup():
    global mcp_client
    # Setup MCP connection
    server_params = StdioServerParameters(
        command="python",
        args=["path/to/google_sheets_server/server.py"],
        env={"SHEET_ID": "...", "SHEETS_API_KEY": "..."}
    )
    # Store client for reuse
    mcp_client = await setup_mcp_client(server_params)

@app.get("/portfolio")
async def get_portfolio():
    result = await mcp_client.call_tool("get_latest_portfolio", {})
    data = json.loads(result[0].text)
    return data
```

### 3. Streamlit Dashboard

```python
import streamlit as st
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@st.cache_data(ttl=300)
def get_portfolio_data():
    async def fetch():
        server_params = StdioServerParameters(
            command="python",
            args=["path/to/google_sheets_server/server.py"],
            env={"SHEET_ID": "...", "SHEETS_API_KEY": "..."}
        )
        async with stdio_client(server_params) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()
            result = await session.call_tool("get_latest_portfolio", {})
            return json.loads(result[0].text)
    
    return asyncio.run(fetch())

st.title("Portfolio Dashboard")
data = get_portfolio_data()
st.metric("Total Value", f"Rs. {data['total']:,.0f}")
```

### 4. Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "portfolio-sheets": {
      "command": "python",
      "args": ["D:/portfolio-bot/mcp_servers/google_sheets_server/server.py"],
      "env": {
        "SHEET_ID": "your-sheet-id",
        "SHEETS_API_KEY": "your-api-key"
      }
    },
    "market-data": {
      "command": "python",
      "args": ["D:/portfolio-bot/mcp_servers/market_data_server/server.py"]
    }
  }
}
```

Then ask Claude Desktop: "What's my latest portfolio value?"

### 5. Direct Function Import (Same Machine)

```python
import sys
sys.path.insert(0, "D:/portfolio-bot/mcp_servers/google_sheets_server")

import server as sheets_server

# Call functions directly (no MCP protocol overhead)
tabs = sheets_server.get_sheet_tabs()
rows = sheets_server.fetch_sheet(tabs[-1])
categories = sheets_server.parse_categories(rows)
total = sheets_server.parse_total(rows)

print(f"Total: Rs. {total:,.0f}")
print(f"Categories: {list(categories.keys())}")
```

## Adapting for Your Own Data

### Customize Google Sheets Server

1. **Change Sheet Structure**: Edit `parse_categories()` and `parse_total()` in `server.py`
2. **Add New Tools**: Add new `@server.call_tool()` functions
3. **Different Sheet**: Just change `SHEET_ID` environment variable

Example - Adding a "get_transactions" tool:
```python
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_transactions":
        sheet_name = arguments["sheet_name"]
        rows = fetch_sheet(sheet_name)
        transactions = parse_transactions(rows)  # Your custom parser
        return [TextContent(type="text", text=json.dumps(transactions))]
```

### Customize Market Data Server

Change tickers, add new data sources:
```python
# Add crypto prices
def get_crypto_prices():
    cryptos = ["BTC-USD", "ETH-USD"]
    # ... use yfinance or other API
    
# Add custom tool
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_crypto_prices":
        result = get_crypto_prices()
        return [TextContent(type="text", text=json.dumps(result))]
```

## Benefits of MCP Approach

1. **Single Source of Truth**: One server, many consumers
2. **Language Agnostic**: Any language with MCP client can use it
3. **Tool Definitions**: Self-documenting via `list_tools()`
4. **Caching Built-in**: 5-minute TTL reduces API calls
5. **Easy Updates**: Change server code, all clients benefit

## Deployment Options

### Local Development
- Run servers as stdio subprocesses
- Perfect for development and testing

### Production
- Deploy on same server as your app
- Or deploy as separate microservices
- Use process managers (systemd, supervisor) to keep running

### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY google_sheets_server/ .
RUN pip install -r requirements.txt
ENV SHEET_ID=your-sheet-id
ENV SHEETS_API_KEY=your-api-key
CMD ["python", "server.py"]
```

## Security Notes

- **Never commit secrets**: Use environment variables
- **API Keys**: Store in `.env` files (gitignored)
- **Sheet Access**: Make sheets public or use service account auth
- **Network**: MCP over stdio is local-only (secure by default)

## Examples in the Wild

Your MCP servers can power:
- 📊 **Analytics dashboards** (Streamlit, Gradio, custom web apps)
- 🤖 **Chatbots** (Telegram, Discord, Slack, WhatsApp)
- 📱 **Mobile apps** (via REST API wrapper around MCP)
- 🖥️ **Desktop apps** (Electron, PyQt with MCP backend)
- 🧠 **AI agents** (Claude Desktop, custom agent frameworks)
- 📧 **Email reports** (scheduled scripts using MCP data)
- 🔔 **Alerts** (monitor portfolio changes, send notifications)

The possibilities are endless! 🚀
