from __future__ import annotations 
import httpx
import streamlit as st
from datetime import datetime, timedelta, timezone

from config.settings import get_settings

settings = get_settings()

import os
_SCORES_URL = os.getenv(
    "API_BASE_URL",
    f"http://localhost:{settings.api_port}"
) + "/api/v1/scores"

_STATUS_COLOR = {
    "IN_PLAY":   "#00ff41",   # bright green — live
    "PAUSED":    "#ffd700",   # gold — halftime
    "FINISHED":  "#888888",   # grey — full time
    "SCHEDULED": "#4488ff",   # blue — upcoming
    "POSTPONED": "#ff8c00",
    "CANCELLED": "#ff4444",
}
def _in_window(score: dict, hours: int = 24) -> bool:
    """Return True if match kickoff is within ±hours of now."""
    utc_date_str = score.get("utc_date", "")
    if not utc_date_str:
        return False
    try:
        dt = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
 
        if score.get("status") == "SCHEDULED" and dt < now:
            return False  # kickoff time passed but still shows SCHEDULED — stale
 
        return (now - timedelta(hours=hours)) <= dt <= (now + timedelta(hours=hours))
    except Exception:                                   # noqa: BLE001
        return True
    
def render_scoreboard() -> None:
    st.sidebar.markdown(
        "<h2 style='color:white;margin-bottom:4px'>⚽ Live Scores</h2>"
        "<p style='color:#aaa;font-size:11px;margin-top:0'>Past & next 24 hours</p>",
        unsafe_allow_html=True,
    )
 
    scores = _fetch_scores()
    if scores is None:
        st.sidebar.warning("Scores unavailable — is the API server running?")
        return
 
    scores = [s for s in scores if _in_window(s)]
    if not scores:
        st.sidebar.info("No matches in the next/past 24 hours.")
        return
 
    by_comp: dict[str, list[dict]] = {}
    for s in scores:
        comp = s.get("competition_name", s.get("competition", "Other"))
        by_comp.setdefault(comp, []).append(s)
 
    def _comp_priority(item: tuple) -> int:
        statuses = {m["status"] for m in item[1]}
        if "IN_PLAY" in statuses or "PAUSED" in statuses:
            return 0
        if "SCHEDULED" in statuses:
            return 1
        return 2
 
    for comp_name, matches in sorted(by_comp.items(), key=_comp_priority):
        matches.sort(key=lambda m: (
            0 if m["status"] in ("IN_PLAY", "PAUSED") else
            1 if m["status"] == "SCHEDULED" else 2
        ))
        with st.sidebar.expander(comp_name, expanded=True):
            for m in matches:
                _render_match_tile(m)
 
 
def _render_match_tile(m: dict) -> None:
    status   = m.get("status", "SCHEDULED")
    home     = m.get("home_team", "?")
    away     = m.get("away_team", "?")
    h_score  = m.get("home_score")
    a_score  = m.get("away_score")
    minute   = m.get("minute")
 
    color = _STATUS_COLOR.get(status, "#888888")
 
    if h_score is not None and a_score is not None:
        score_str = f"{h_score}–{a_score}"
    else:
        score_str = "vs"
 
    if status == "IN_PLAY":
        badge = f"🟢 {minute}'" if minute else "🟢 LIVE"
    elif status == "PAUSED":
        badge = "⏸ HT"
    elif status == "FINISHED":
        badge = "⚫ FT"
    elif status == "SCHEDULED":
        badge = "🔵 Soon"
    else:
        badge = status
 
    # truncate long names
    h = home[:14] + "…" if len(home) > 14 else home
    a = away[:14] + "…" if len(away) > 14 else away
 
    st.sidebar.markdown(f"""
<div style="
    background: rgba(0,0,0,0.55);
    border: 1px solid rgba(255,255,255,0.1);
    border-left: 3px solid {color};
    border-radius: 6px;
    padding: 7px 10px;
    margin: 5px 0;
    font-family: 'Courier New', monospace;
">
    <div style="color:{color};font-size:10px;letter-spacing:1px;margin-bottom:3px">{badge}</div>
    <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="color:white;font-size:11px;flex:1">{h}</span>
        <span style="color:{color};font-size:14px;font-weight:bold;padding:0 6px;min-width:36px;text-align:center">{score_str}</span>
        <span style="color:white;font-size:11px;flex:1;text-align:right">{a}</span>
    </div>
</div>""", unsafe_allow_html=True)

 
 
def _fetch_scores() -> list[dict] | None:
    """Fetch snapshot from FastAPI. Returns None on any error."""
    try:
        resp = httpx.get(_SCORES_URL, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:                                   # noqa: BLE001
        return None
