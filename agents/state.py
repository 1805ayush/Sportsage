from __future__ import annotations

from typing import Literal, Optional, TypedDict

IntentType = Literal["live", "rag", "sql", "web"]
ALL_INTENTS: list[IntentType] = ["live", "rag", "sql", "web"]

class AgentState(TypedDict, total= False):
    query: str
    live_data : Optional[str]
    rag_data : Optional[str]
    sql_data : Optional[str]
    web_data : Optional[str]
    final_answer : Optional[str]
    error : Optional[str]