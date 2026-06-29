from __future__ import annotations

import logging

from langchain_groq import ChatGroq

from agents.state import AgentState
from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are SportsSage, an expert football/soccer assistant.
 
You will be given a user question and context gathered from one or more sources:
- LIVE DATA: current match scores and status from ESPN
- HISTORICAL DATA: past match results from the knowledge base
- STATS DATA: structured statistics from the database (standings, scorers, etc.)
- WEB DATA: recent news and updates from the web
 
Instructions:
- Answer the user's question directly and concisely using the provided context
- Cite your sources naturally inline (e.g. "According to live scores...", "The database shows...", "Recent reports suggest...")
- If multiple sources contributed, weave them together into one coherent answer
- If the context doesn't fully answer the question, say so honestly
- Never make up scores, stats, or facts not present in the context
- Keep answers focused — 2-4 sentences for simple queries, a short paragraph for complex ones
- Use football/soccer terminology naturally"""

_llm = ChatGroq(
    model = settings.groq_model,
    temperature= settings.groq_temperature,
    api_key= settings.groq_api_key
)

async def synthesize(state: AgentState)-> dict:
    query = state.get("query","")
    context_parts: list[str] = []

    if state.get("live_data"):
        context_parts.append(f"LIVE DATA:\n{state['live_data']}")
    
    if state.get("rag_data"):
        context_parts.append(f"HISTORICAL DATA:\n{state['rag_data']}")

    if state.get("sql_data"):
        context_parts.append(f"STATS DATA:\n{state['sql_data']}")
    
    if state.get("web_data"):
        context_parts.append(f"WEB DATA:\n{state['web_data']}")

    if not context_parts:
        return {"final_answer": "I couldn't find any relevant data to answer your question."}
    
    context_block = "\n\n".join(context_parts)
    human_message = f"Question: {query}\n\nContext:\n{context_block}"

    try:
        response = await _llm.ainvoke([
            ("system", _SYSTEM_PROMPT),
            ("human", human_message),
        ])
        return {"final_answer": response.content.strip()}
    except Exception as exc:                            # noqa: BLE001
        logger.error("Synthesizer failed for query %r: %s", query, exc)
        return {"final_answer": f"I found relevant data but failed to generate an answer: {exc}"}
    