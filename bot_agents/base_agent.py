"""
Base Agent Class
Provides common functionality for all specialized agents
"""

import logging
from abc import ABC, abstractmethod
from typing import Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents with common MCP tool calling and LLM integration"""

    def __init__(self, name: str, openai_client: OpenAI, mcp_clients: dict[str, Any] = None):
        """
        Initialize base agent

        Args:
            name: Agent name for logging
            openai_client: OpenAI client instance
            mcp_clients: Dict of MCP client sessions (e.g., {"sheets": client1, "market": client2})
        """
        self.name = name
        self.openai_client = openai_client
        self.mcp_clients = mcp_clients or {}
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    async def process(self, query: str, context: dict) -> dict:
        """
        Process a query and return a result

        Args:
            query: User query string
            context: Context dict (user_id, conversation_history, etc.)

        Returns:
            Dict with keys: "text" (response text), "data" (optional structured data), "error" (if any)
        """
        pass

    async def call_mcp_tool(self, server_name: str, tool_name: str, arguments: dict = None) -> Any:
        """
        Call an MCP tool and return the result

        Args:
            server_name: Name of the MCP server (e.g., "sheets", "market", "context")
            tool_name: Tool name
            arguments: Tool arguments dict

        Returns:
            Tool result (parsed JSON)
        """
        if server_name not in self.mcp_clients:
            raise ValueError(f"MCP server '{server_name}' not available")

        client = self.mcp_clients[server_name]
        arguments = arguments or {}

        try:
            result = await client.call_tool(tool_name, arguments)
            self.logger.info(f"Called {server_name}.{tool_name} with {arguments}")

            # Parse result - MCP returns list of TextContent
            if result and len(result) > 0:
                import json
                return json.loads(result[0].text)
            return None

        except Exception as e:
            self.logger.error(f"Error calling {server_name}.{tool_name}: {e}", exc_info=True)
            raise

    def call_llm(
        self,
        messages: list[dict],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 1500
    ) -> str:
        """
        Call OpenAI LLM and return response text

        Args:
            messages: List of message dicts ({"role": "...", "content": "..."})
            model: Model name
            temperature: Temperature
            max_tokens: Max tokens

        Returns:
            Response text
        """
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"LLM call failed: {e}", exc_info=True)
            raise

    def build_context_summary(self, context: dict) -> str:
        """
        Build a context summary string from context dict

        Args:
            context: Context dict with conversation_history, user_id, etc.

        Returns:
            Formatted context string
        """
        summary_parts = []

        if "user_id" in context:
            summary_parts.append(f"User ID: {context['user_id']}")

        if "conversation_history" in context and context["conversation_history"]:
            summary_parts.append("\nRecent conversation:")
            for msg in context["conversation_history"][-3:]:  # Last 3 messages
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:100]  # Truncate long messages
                summary_parts.append(f"  {role}: {content}")

        return "\n".join(summary_parts) if summary_parts else "No additional context"
