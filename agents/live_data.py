from __future__ import annotations

import logging 

import httpx

from agents.state import AgentState
from config.settings import get_settings
from pipeline.fetchers.espn import fetch_live_scores
from pipeline.models import LiveScore
from storage.redis_client import get_redis, stream_key

settings = get_settings()
logger = logging.getLogger(__name__)

_SCAN_COUNT = 50

async def get_live_data(state: AgentState)-> dict:
    redis = await get_redis()
    latest_by_match :dict[str, LiveScore] = {}

    for competition in settings.competitions:
        stream = stream_key(competition)
        try:
            entries = await redis.xrevrange(stream, count= _SCAN_COUNT)
        except Exception as exc:
            logger.warning("Redis xrevrange failed for %s: %s", stream,exc)
            entries = []
        
        for entry_id, fields in entries:
            try:
                score= LiveScore.from_redis_dict(fields)
            except Exception as exc:                    # noqa: BLE001
                logger.warning("Skipping malformed stream entry in %s: %s", stream, exc)
                continue
            
            if score.match_id not in latest_by_match:
                latest_by_match[score.match_id] = score
        
        if not latest_by_match:
            logger.info("No live data in Redis — falling back to direct ESPN fetch")
            async with httpx.AsyncClient() as client:
                for competition in settings.competitions:
                    scores = await fetch_live_scores(client,competition)
                    for s in scores:
                        latest_by_match[s.match_id] = s
        if not latest_by_match:
            return {"live_data": "No live match data is currently available."}
 
    return {"live_data": _format_scores(list(latest_by_match.values()))}

def _format_scores(scores: list[LiveScore])-> str:
    lines = []
    for s in scores:
        if s.home_score is None or s.away_score is None:
            score_str ="Not Started"
        else:
            score_str = f"{s.home_score}-{s.away_score}"
        
        minute_str = f", {s.minute}'" if s.minute else ""
        lines.append(
            f"{s.home_team} {score_str} {s.away_team} "
            f"({s.competition_name}, {s.status}{minute_str})"
        )
 
    return "\n".join(lines)