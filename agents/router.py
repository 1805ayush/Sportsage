from __future__ import annotations

import logging

from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from agents.state import ALL_INTENTS, AgentState, IntentType
from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class RouterOutput(BaseModel):
    intents: list[IntentType] = Field(
        description="One or more agent types needed to answer the query."
    )

_SYSTEM_PROMPT = """You are a routing agent for SportsSage, a football/soccer Q&A system.
 
Classify the user's query into one or more of these categories:
 
- live: current/in-progress match scores, who's playing right now, live status
- rag: historical facts, past results, player/team history (e.g. "who won the 2022 World Cup")
- sql: structured stats — standings, top scorers, points, goal difference, season totals
- web: recent news, transfers, injuries, rumors — anything not covered above
 
A query can need MULTIPLE categories. Examples:
- "What's the score right now?" -> ["live"]
- "Who won the 2022 World Cup final?" -> ["rag"]
- "Top scorers in the Premier League" -> ["sql"]
- "Compare Haaland's World Cup form to his club season stats" -> ["live", "sql"]
- "Latest news on Mbappe's injury" -> ["web"]
 
Return only the categories actually needed — don't over-select."""    

_llm = ChatGroq(
    model = settings.groq_model,
    temperature = settings.groq_temperature,
    api_key = settings.groq_api_key
)

_structured_llm = _llm.with_structured_output(RouterOutput)

async def classify_intent(state: AgentState)-> dict:
    query = state["query"]
    try:
        result: RouterOutput =await _structured_llm.ainvoke([
            ("system",_SYSTEM_PROMPT),
            ("human", query)
        ])
        intents = [i for i in result.intents if i in ALL_INTENTS]
        if not intents:
            logger.warning("Router returned no valid intents for query: %r — falling back to web", query)
            intents = ["web"]
    except Exception as exc:                            # noqa: BLE001
        logger.error("Router classification failed for query %r: %s", query, exc)
        intents = ["web"]
 
    logger.info("Routed query %r -> %s", query, intents)
    return {"intents": intents}    