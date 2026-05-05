"""
Orchestrator Agent
Routes user queries to specialized agents and aggregates results
"""

import json
import logging
from typing import Any
from openai import OpenAI
from .base_agent import BaseAgent
from .agent_config import ORCHESTRATOR_AGENT_PROMPT
from .portfolio_agent import PortfolioAgent
from .market_agent import MarketAgent
from .chart_agent import ChartAgent

logger = logging.getLogger("orchestrator")


class OrchestratorAgent(BaseAgent):
    """Main orchestrator that routes queries to specialized agents"""

    def __init__(self, openai_client: OpenAI, mcp_clients: dict[str, Any]):
        super().__init__("orchestrator", openai_client, mcp_clients)

        # Initialize specialized agents
        self.portfolio_agent = PortfolioAgent(openai_client, mcp_clients)
        self.market_agent = MarketAgent(openai_client, mcp_clients)
        self.chart_agent = ChartAgent(openai_client, mcp_clients)

    def get_system_prompt(self) -> str:
        return ORCHESTRATOR_AGENT_PROMPT

    async def _classify_intent(self, query: str) -> dict:
        """
        Classify user query into intent categories

        Returns:
            Dict with "agent" (portfolio|market|chart|none), "needs_chart" (bool), "confidence" (float)
        """
        classification_prompt = f"""Classify this user query into ONE primary agent category:

Query: "{query}"

Categories:
- portfolio: Questions about portfolio value, composition, returns, month comparisons
- market: Stock analysis, valuations, market trends, "why is X up/down", investment opportunities
- chart: Visualization requests (charts, graphs, trends)
- none: Greetings, thank you, unclear queries

Also indicate if a chart is requested (needs_chart: true/false).

Return JSON:
{{
    "agent": "portfolio|market|chart|none",
    "needs_chart": true/false,
    "reasoning": "brief explanation"
}}
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Faster model for classification
                messages=[{"role": "user", "content": classification_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)
            self.logger.info(f"Intent classification: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Intent classification failed: {e}", exc_info=True)
            # Default to portfolio agent
            return {"agent": "portfolio", "needs_chart": False, "reasoning": "fallback"}

    def get_system_prompt(self) -> str:
        return ORCHESTRATOR_AGENT_PROMPT

    async def process(self, query: str, context: dict) -> dict:
        """
        Process user query by routing to appropriate agent(s)

        Args:
            query: User query
            context: Context dict

        Returns:
            Dict with "response_type" (text|chart|both), "text", "chart", "agent_used"
        """
        try:
            # Handle simple greetings/commands without agent calls
            query_lower = query.lower().strip()
            if query_lower in ["hi", "hello", "hey", "thank you", "thanks", "ok", "okay"]:
                return {
                    "response_type": "text",
                    "text": self._get_simple_response(query_lower),
                    "chart": None,
                    "agent_used": "none"
                }

            # Classify intent
            intent = await self._classify_intent(query)
            agent_type = intent.get("agent", "portfolio")
            needs_chart = intent.get("needs_chart", False)

            # Route to appropriate agent
            if agent_type == "chart" or needs_chart:
                # Chart request
                result = await self.chart_agent.process(query, context)
                if result.get("error"):
                    return {
                        "response_type": "text",
                        "text": f"Chart generation failed: {result['error']}",
                        "chart": None,
                        "agent_used": "chart"
                    }

                return {
                    "response_type": "chart" if result.get("data") else "text",
                    "text": result.get("text", "Chart generated"),
                    "chart": result.get("data"),
                    "agent_used": "chart"
                }

            elif agent_type == "portfolio":
                # Portfolio analysis
                result = await self.portfolio_agent.process(query, context)
                if result.get("error"):
                    return {
                        "response_type": "text",
                        "text": f"Portfolio analysis failed: {result['error']}",
                        "chart": None,
                        "agent_used": "portfolio"
                    }

                return {
                    "response_type": "text",
                    "text": result.get("text", "No response"),
                    "chart": None,
                    "agent_used": "portfolio"
                }

            elif agent_type == "market":
                # Market analysis
                # Check if we should fetch portfolio context first
                if "buy" in query_lower or "opportunity" in query_lower or "recommend" in query_lower:
                    # Fetch portfolio context for recommendation queries
                    try:
                        portfolio_result = await self.portfolio_agent.process("Get my latest portfolio summary", context)
                        context["portfolio_data"] = portfolio_result.get("text", "")
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch portfolio context: {e}")

                result = await self.market_agent.process(query, context)
                if result.get("error"):
                    return {
                        "response_type": "text",
                        "text": f"Market analysis failed: {result['error']}",
                        "chart": None,
                        "agent_used": "market"
                    }

                return {
                    "response_type": "text",
                    "text": result.get("text", "No response"),
                    "chart": None,
                    "agent_used": "market"
                }

            else:  # none
                return {
                    "response_type": "text",
                    "text": "I'm not sure how to help with that. Try asking about your portfolio, market analysis, or requesting a chart!",
                    "chart": None,
                    "agent_used": "none"
                }

        except Exception as e:
            self.logger.error(f"Orchestrator error: {e}", exc_info=True)
            return {
                "response_type": "text",
                "text": f"Sorry, something went wrong: {str(e)}",
                "chart": None,
                "agent_used": "error"
            }

    def _get_simple_response(self, query: str) -> str:
        """Get simple response for greetings and basic commands"""
        responses = {
            "hi": "Hello! How can I help you with your portfolio today?",
            "hello": "Hi! Ask me about your portfolio, market analysis, or request a chart!",
            "hey": "Hey! What would you like to know about your investments?",
            "thank you": "You're welcome! Let me know if you need anything else.",
            "thanks": "Happy to help!",
            "ok": "👍",
            "okay": "Got it!"
        }
        return responses.get(query, "How can I help you?")
