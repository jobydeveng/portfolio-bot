"""
Market Agent
Specialized agent for market analysis, stock valuation, and investment opportunities
"""

import json
from typing import Any
from openai import OpenAI
from .base_agent import BaseAgent
from .agent_config import MARKET_AGENT_PROMPT


class MarketAgent(BaseAgent):
    """Agent specialized in market analysis and stock research"""

    def __init__(self, openai_client: OpenAI, mcp_clients: dict[str, Any]):
        super().__init__("market", openai_client, mcp_clients)

    def get_system_prompt(self) -> str:
        return MARKET_AGENT_PROMPT

    async def process(self, query: str, context: dict) -> dict:
        """
        Process market analysis query

        Args:
            query: User query
            context: Context dict (may include portfolio data from another agent)

        Returns:
            Dict with "text" (response), "data" (optional), "error" (if any)
        """
        try:
            # Build messages
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": query}
            ]

            # Add context (including portfolio data if provided by orchestrator)
            context_summary = self.build_context_summary(context)
            if "portfolio_data" in context:
                context_summary += f"\n\nCurrent Portfolio Data:\n{json.dumps(context['portfolio_data'], indent=2)}"

            if context_summary != "No additional context":
                messages.insert(1, {"role": "system", "content": f"Context:\n{context_summary}"})

            # Define available tools
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_stock_price",
                        "description": "Get current price and change for a stock ticker",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string", "description": "Stock ticker (e.g., 'HDFCBANK', 'MSFT')"}
                            },
                            "required": ["ticker"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_stock_info",
                        "description": "Get detailed stock info (PE, PB, 52W high/low, market cap)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string", "description": "Stock ticker"}
                            },
                            "required": ["ticker"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_historical_data",
                        "description": "Get historical price data for a stock",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string", "description": "Stock ticker"},
                                "period": {"type": "string", "description": "Period (e.g., '1mo', '3mo', '1y')"}
                            },
                            "required": ["ticker"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_market_indices",
                        "description": "Get current prices for major Indian and US indices",
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_portfolio_stocks",
                        "description": "Get live prices for portfolio stocks",
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_holdings_list",
                        "description": "Get list of current holdings",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "format": {"type": "string", "enum": ["detailed", "brief"]}
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_sector_exposure",
                        "description": "Get current sector exposure from portfolio",
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                }
            ]

            # Call LLM with tools
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.7
            )

            # Handle tool calls
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if tool_calls:
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    self.logger.info(f"Tool call: {function_name} with {function_args}")

                    # Route to appropriate MCP server
                    if function_name in ["get_stock_price", "get_stock_info", "get_historical_data",
                                        "get_market_indices", "get_portfolio_stocks"]:
                        result = await self.call_mcp_tool("market", function_name, function_args)
                    elif function_name in ["get_holdings_list", "get_sector_exposure"]:
                        result = await self.call_mcp_tool("context", function_name, function_args)
                    else:
                        result = {"error": f"Unknown tool: {function_name}"}

                    # Add tool response
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(result)
                    })

                # Get final response
                final_response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7
                )

                return {
                    "text": final_response.choices[0].message.content.strip(),
                    "data": None,
                    "error": None
                }

            else:
                return {
                    "text": response_message.content.strip(),
                    "data": None,
                    "error": None
                }

        except Exception as e:
            self.logger.error(f"Market agent error: {e}", exc_info=True)
            return {
                "text": None,
                "data": None,
                "error": f"Market analysis failed: {str(e)}"
            }
