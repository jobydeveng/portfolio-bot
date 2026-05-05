"""
Chart Agent
Specialized agent for generating chart specifications for portfolio visualization
"""

import json
from typing import Any
from openai import OpenAI
from .base_agent import BaseAgent
from .agent_config import CHART_AGENT_PROMPT


class ChartAgent(BaseAgent):
    """Agent specialized in data visualization and chart generation"""

    def __init__(self, openai_client: OpenAI, mcp_clients: dict[str, Any]):
        super().__init__("chart", openai_client, mcp_clients)

    def get_system_prompt(self) -> str:
        return CHART_AGENT_PROMPT

    async def process(self, query: str, context: dict) -> dict:
        """
        Process chart generation query

        Args:
            query: User query
            context: Context dict

        Returns:
            Dict with "text" (description), "data" (chart config), "error" (if any)
        """
        try:
            # Build messages
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": query}
            ]

            # Add context
            context_summary = self.build_context_summary(context)
            if context_summary != "No additional context":
                messages.insert(1, {"role": "system", "content": f"Context:\n{context_summary}"})

            # Define available tools
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_latest_portfolio",
                        "description": "Get latest month's portfolio data for charts",
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_portfolio_history",
                        "description": "Get portfolio history for trend charts",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Max months to return"}
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_month_portfolio",
                        "description": "Get specific month data for comparison charts",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "month_query": {"type": "string", "description": "Month name"}
                            },
                            "required": ["month_query"]
                        }
                    }
                }
            ]

            # Call LLM with tools
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.5  # Lower temperature for more consistent chart specs
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

                    # All tools are from sheets server
                    result = await self.call_mcp_tool("sheets", function_name, function_args)

                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(result)
                    })

                # Get final response with chart specification
                final_response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.5,
                    response_format={"type": "json_object"}  # Request JSON output
                )

                response_text = final_response.choices[0].message.content.strip()

                # Parse JSON response
                try:
                    chart_spec = json.loads(response_text)
                    return {
                        "text": chart_spec.get("description", "Chart generated"),
                        "data": chart_spec,
                        "error": None
                    }
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse chart spec JSON: {e}")
                    return {
                        "text": response_text,  # Return as text if JSON parsing fails
                        "data": None,
                        "error": f"Chart spec parsing failed: {str(e)}"
                    }

            else:
                # No tool calls - might be an error or clarification request
                return {
                    "text": response_message.content.strip(),
                    "data": None,
                    "error": None
                }

        except Exception as e:
            self.logger.error(f"Chart agent error: {e}", exc_info=True)
            return {
                "text": None,
                "data": None,
                "error": f"Chart generation failed: {str(e)}"
            }
