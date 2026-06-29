from __future__ import annotations

import logging

from duckduckgo_search import DDGS

from agents.state import AgentState
from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_MAX_RESULTS=5

async def search_web(state: AgentState)-> dict:
    import asyncio
    query = state["query"]

    search_query = f"football soccer {query}"

    try:
        results = await asyncio.to_thread(_ddg_search,search_query)
    except Exception as exc:
        logger.error("DuckDuckGo search failed for %r: %s", query, exc)
        return {"web_data": "Web search failed — no results available."}
 
    if not results:
        return {"web_data": "No recent web results found for this query."}
    
    lines = []
    for r in results:
        title = r.get("title","")
        body = r.get("body","")
        lines.append(f"- {title}: {body}")

    return {"web_data": "\n".join(lines)}

def _ddg_search(query: str) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query,max_results =_MAX_RESULTS))