from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.historical_rag import search_historical
from agents.live_data import get_live_data
from agents.router import classify_intent
from agents.sql_stats import query_sql_stats
from agents.state import AgentState
from agents.synthesizer import synthesize
from agents.web_search import search_web

logger = logging.getLogger(__name__)

_AGENT_MAP ={
    "live": get_live_data,
    "rag": search_historical,
    "sql": query_sql_stats,
    "web": search_web
}

async def route_and_run(state: AgentState)-> dict:
    routing = await classify_intent(state)
    intents = routing.get("intents",["web"])
    logger.info("Intents: %s", intents)

    updated_state = {**state, "intents": intents}
    tasks = [
        _AGENT_MAP[intent](updated_state)
        for intent in intents
        if intent in _AGENT_MAP
    ]
 
    if not tasks:
        return {"intents": intents}
 
    results = await asyncio.gather(*tasks, return_exceptions=True)
 
    merged: dict[str, Any] = {"intents": intents}
    for intent, result in zip(intents, results):
        if isinstance(result, Exception):
            logger.error("Agent '%s' raised: %s", intent, result)
        else:
            merged.update(result)
 
    return merged



def build_graph():
    builder = StateGraph(AgentState)
    # builder.add_node("router", classify_intent)
    builder.add_node("route_and_run", route_and_run)
    builder.add_node("synthesizer", synthesize)

    builder.add_edge(START,"route_and_run")
    # builder.add_edge("router","run_agents")
    builder.add_edge("route_and_run",  "synthesizer")
    builder.add_edge("synthesizer", END)
 
    return builder.compile()

graph = build_graph()

async def ask(query: str) -> str:
    """Run a single query through the full pipeline."""
    result = await graph.ainvoke({"query": query})
    return result.get("final_answer", "No answer generated.")