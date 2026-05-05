"""
Portfolio Agent
Specialized agent for portfolio analysis, tracking, and comparison
"""

import json
from typing import Any
from openai import OpenAI
from .base_agent import BaseAgent
from .agent_config import PORTFOLIO_AGENT_PROMPT


class PortfolioAgent(BaseAgent):
    """Agent specialized in portfolio analysis and tracking"""

    def __init__(self, openai_client: OpenAI, mcp_clients: dict[str, Any]):
        super().__init__("portfolio", openai_client, mcp_clients)

    def get_system_prompt(self) -> str:
        return PORTFOLIO_AGENT_PROMPT

    async def process(self, query: str, context: dict) -> dict:
        """
        Process portfolio-related query

        Args:
            query: User query
            context: Context dict

        Returns:
            Dict with "text" (response), "data" (optional structured data), "error" (if any)
        """
        try:
            # Build the LLM messages with tool-calling capability
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": query}
            ]

            # Add context if available
            context_summary = self.build_context_summary(context)
            if context_summary != "No additional context":
                messages.insert(1, {"role": "system", "content": f"Context:\n{context_summary}"})

            # Define available tools for this agent
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_latest_portfolio",
                        "description": "Get the latest month's portfolio summary (categories and total value)",
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_portfolio_history",
                        "description": "Get portfolio history for multiple months",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Max months to return (optional)"}
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_month_portfolio",
                        "description": "Get portfolio data for a specific month by name",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "month_query": {"type": "string", "description": "Month name (e.g., 'March', 'Apr')"}
                            },
                            "required": ["month_query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_holdings_list",
                        "description": "Get list of all holdings (stocks, mutual funds)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "format": {"type": "string", "enum": ["detailed", "brief"], "description": "Output format"}
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_sector_exposure",
                        "description": "Get sector exposure breakdown for Indian stocks",
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                }
            ]

            # Call LLM with tool definitions
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
                # Execute tool calls
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    self.logger.info(f"Tool call: {function_name} with {function_args}")

                    # Route to appropriate MCP server
                    if function_name in ["get_latest_portfolio", "get_portfolio_history", "get_month_portfolio"]:
                        result = await self.call_mcp_tool("sheets", function_name, function_args)
                    elif function_name in ["get_holdings_list", "get_sector_exposure"]:
                        result = await self.call_mcp_tool("context", function_name, function_args)
                    else:
                        result = {"error": f"Unknown tool: {function_name}"}

                    # Add tool response to messages
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(result)
                    })

                # Get final response from LLM
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
                # No tool calls, just return the response
                return {
                    "text": response_message.content.strip(),
                    "data": None,
                    "error": None
                }

        except Exception as e:
            self.logger.error(f"Portfolio agent error: {e}", exc_info=True)
            return {
                "text": None,
                "data": None,
                "error": f"Portfolio analysis failed: {str(e)}"
            }
