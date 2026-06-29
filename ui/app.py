"""SportsSage Streamlit UI — football pitch theme."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from ui.components.chat import render_chat
from ui.components.scoreboard import render_scoreboard

st.set_page_config(
    page_title="SportsSage",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

FIELD_B64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAwIDYwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQgc2xpY2UiPgo8ZyBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIGZpbGw9Im5vbmUiIG9wYWNpdHk9IjAuMTMiPgo8cmVjdCB4PSI0MCIgeT0iNDAiIHdpZHRoPSI5MjAiIGhlaWdodD0iNTIwIiByeD0iMiIvPgo8bGluZSB4MT0iNTAwIiB5MT0iNDAiIHgyPSI1MDAiIHkyPSI1NjAiLz4KPGNpcmNsZSBjeD0iNTAwIiBjeT0iMzAwIiByPSI3MiIvPgo8cmVjdCB4PSI0MCIgeT0iMTUwIiB3aWR0aD0iMTUwIiBoZWlnaHQ9IjMwMCIvPgo8cmVjdCB4PSI0MCIgeT0iMjM1IiB3aWR0aD0iNTAiIGhlaWdodD0iMTMwIi8+CjxyZWN0IHg9IjE4IiB5PSIyNjgiIHdpZHRoPSIyMiIgaGVpZ2h0PSI2NCIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KPHJlY3QgeD0iODEwIiB5PSIxNTAiIHdpZHRoPSIxNTAiIGhlaWdodD0iMzAwIi8+CjxyZWN0IHg9IjkxMCIgeT0iMjM1IiB3aWR0aD0iNTAiIGhlaWdodD0iMTMwIi8+CjxyZWN0IHg9Ijk2MCIgeT0iMjY4IiB3aWR0aD0iMjIiIGhlaWdodD0iNjQiIHN0cm9rZS13aWR0aD0iMi41Ii8+CjxwYXRoIGQ9Ik00MCA2MiBBMjIgMjIgMCAwIDEgNjIgNDAiLz4KPHBhdGggZD0iTTkzOCA0MCBBMjIgMjIgMCAwIDEgOTYwIDYyIi8+CjxwYXRoIGQ9Ik05NjAgNTM4IEEyMiAyMiAwIDAgMSA5MzggNTYwIi8+CjxwYXRoIGQ9Ik02MiA1NjAgQTIyIDIyIDAgMCAxIDQwIDUzOCIvPgo8cGF0aCBkPSJNMTkwIDIzOCBBNzIgNzIgMCAwIDAgMTkwIDM2MiIvPgo8cGF0aCBkPSJNODEwIDIzOCBBNzIgNzIgMCAwIDEgODEwIDM2MiIvPgo8L2c+CjxjaXJjbGUgY3g9IjUwMCIgY3k9IjMwMCIgcj0iNCIgZmlsbD0id2hpdGUiIG9wYWNpdHk9IjAuMjIiLz4KPGNpcmNsZSBjeD0iMTUxIiBjeT0iMzAwIiByPSI0IiBmaWxsPSJ3aGl0ZSIgb3BhY2l0eT0iMC4yMiIvPgo8Y2lyY2xlIGN4PSI4NDkiIGN5PSIzMDAiIHI9IjQiIGZpbGw9IndoaXRlIiBvcGFjaXR5PSIwLjIyIi8+Cjwvc3ZnPg=="

st.markdown(f"""
<style>
.stApp {{
    background:
        url("data:image/svg+xml;base64,{FIELD_B64}") center/cover no-repeat fixed,
        linear-gradient(180deg, #0c2904 0%, #1a4a0a 35%, #1a4a0a 65%, #0c2904 100%);
}}
[data-testid="stSidebar"] {{
    background: #071a02 !important;
    border-right: 2px solid rgba(255,255,255,0.10);
}}
[data-testid="stSidebar"] * {{ color: white !important; }}
.block-container {{
    background: rgba(0,0,0,0.28);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.07);
    position: relative;
    z-index: 1;
}}
[data-testid="stChatMessage"] {{
    background: rgba(0,0,0,0.50) !important;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
}}
[data-testid="stChatInput"] textarea {{
    background: rgba(0,0,0,0.60) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 8px !important;
}}
h1, h2, h3, p, .stMarkdown, label, .stCaption, .stText {{ color: white !important; }}
.stButton > button {{
    background: rgba(255,255,255,0.08);
    color: white;
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 6px;
}}
.stButton > button:hover {{ background: rgba(255,255,255,0.16); }}
[data-testid="stExpander"] {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    border-radius: 6px !important;
}}
hr {{ border-color: rgba(255,255,255,0.07) !important; }}
.stSpinner > div {{ border-top-color: #00ff41 !important; }}
</style>
""", unsafe_allow_html=True)

render_scoreboard()
render_chat()

_REFRESH_INTERVAL = 60
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0
if int(time.time()) % _REFRESH_INTERVAL == 0:
    st.session_state.refresh_count += 1
    st.rerun()