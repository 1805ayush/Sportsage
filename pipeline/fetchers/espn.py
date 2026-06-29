from __future__ import annotations
import logging
from datetime import datetime,timezone

import httpx

from config.settings import get_settings
from pipeline.models import LiveScore,MatchStatus

settings = get_settings()
logger = logging.getLogger(__name__)

async def fetch_live_scores(client: httpx.AsyncClient, competition: str)-> list[LiveScore]:
    slug = settings.espn_league_slugs.get(competition)
    if not slug:
        logger.warning("No ESPN slug confirmed for competition")
        return []
    url = f"{settings.espn_base_url}/{slug}/scoreboard"

    try:
        resp = await client.get(url,timeout = 10)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("ESPN request failed [%s]: %s",competition,exc)
        return []
    
    scores :list[LiveScore] = []
    for event in data.get("events",[]):
        try:
            score = _parse_event(event,competition)
            if score:
                scores.append(score)
        except Exception as exc:
            logger.warning("Skipping ESPN event (parse error): %s", exc)
 
    return scores

def _parse_event(event: dict, competition: str)-> LiveScore |None:
    competitions = event.get("competitions",[])
    if not competitions:
        return None
    
    comp = competitions[0]
    competitors = comp.get("competitors",[])
    if len(competitors)<2:
        return None
    
    home = next((c for c in competitors if c["homeAway"] == "home"),None)
    away = next((c for c in competitors if c["homeAway"] == "away"),None)
    if not home or not away:
        return None
    
    status = _parse_status(comp.get("status",{}))
    minute = _parse_minute(comp.get("status",{}))
    if status == MatchStatus.SCHEDULED:
        home_score = away_score = None
    else:
        home_score = int(home.get("score") or 0)
        away_score = int(away.get("score") or 0)

    return LiveScore(
        match_id=event["id"],
        competition=competition,
        competition_name=settings.competition_names.get(competition, competition),
        home_team=home["team"]["displayName"],
        away_team=away["team"]["displayName"],
        home_score=home_score,
        away_score=away_score,
        status=status,
        minute=minute,
        utc_date=event.get("date", datetime.now(timezone.utc).isoformat()),
        source="espn",        
    )
def _parse_status(status_data: dict) -> MatchStatus:
    status_type = status_data.get("type", {})
    state = status_type.get("state", "pre")
    name  = status_type.get("name", "")
 
    if state == "pre":
        return MatchStatus.SCHEDULED
    if state == "post":
        return MatchStatus.FINISHED
    if state == "in":
        return MatchStatus.PAUSED if "HALFTIME" in name else MatchStatus.IN_PLAY
 
    return MatchStatus.SCHEDULED
 
 
def _parse_minute(status_data: dict) -> int | None:
    clock = status_data.get("displayClock", "")
    if not clock:
        return None
    
    digits = "".join(ch for ch in clock if ch.isdigit() or ch== "+")
    if not digits:
        return None
    
    try:
        return int(digits.split("+")[0])
    except ValueError:
        return None