from __future__ import annotations

import asyncio
import concurrent.futures
import logging

import streamlit as st

from agents.graph import ask

logger = logging.getLogger(__name__)

_WELCOME = (
    "👋 Hi! I'm **SportsSage**. Ask me anything about football —\n"
    "live scores, standings, historical results, player stats, or latest news."
)

def _run_query(query: str)-> str:
    try:
        return asyncio.run(ask(query))
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor(max_worlers =1) as pool:
            future = pool.submit(asyncio.run, ask(query))
            return future.result()
        
def render_chat()-> None:
    st.title("SportsSage ⚽")
    st.caption("Live scores · standings · history · news")

    if (
        "messages" not in st.session_state
        or not isinstance(st.session_state.messages, list)
        or (st.session_state.messages and "role" not in st.session_state.messages[0])
    ):
        st.session_state.messages = [
            {"role": "assistant", "content": _WELCOME}
        ]
    
    if st.button("🗑️ Clear chat", key="clear"):
        st.session_state.messages = [
            {"role": "assistant", "content": _WELCOME}
        ]
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if prompt := st.chat_input("Ask about football..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = _run_query(prompt)
                except Exception as exc:                # noqa: BLE001
                    logger.error("Query failed: %s", exc)
                    answer = "Sorry, something went wrong. Please try again."
            st.markdown(answer)
 
        st.session_state.messages.append({"role": "assistant", "content": answer})

