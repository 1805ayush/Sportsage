from __future__ import annotations
import logging
from datetime import date
import httpx
from config.settings import get_settings
from pipeline.models import MatchLineup,MatchStats,Player

settings = get_settings()
logger = logging.getLogger(__name__)

_HEADERS = {"Authorization": f"Token {settings.bsd_api_key}"}

async def fetch_xg_stats(client: httpx.AsyncClient, competition: str,
                        date_from: date | None=None, 
                        date_to: date | None= None)-> list[MatchStats]:
    league_id = settings.bsd_league_ids.get(competition)
    if not league_id:
        logger.warning("No BSD league ID configured for the competition: %s", competition)
        return []
    
    today = date.today()
    date_from = date_from or today
    date_to = date_to or today

    url = f"{settings.bsd_base_url}/api/events/"
    params = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "league": league_id,
    }
    data = await _get(client, url,params=params)
    if data is None:
        return []
    
    if data.get("next"):
        logger.info("BSD events response paginated - only first page fetched (%s)",url)

    stats: list[MatchStats] = []
    for raw in data.get("results",[]):
        try:
            stats.append(_parse_xg(raw))
        except Exception as exc:
            logger.warning("Skipping BSD event (xG parse error): %s",exc)
    
    return stats

async def fetch_lineup(client: httpx.AsyncClient, event_id:str)-> MatchLineup | None:
    url = f"{settings.bsd_base_url}/api/events/{event_id}/"
    params = {"full": "true"}

    data = await _get(client, url, params=params)
    if data is None:
        return None
    
    lineups = data.get("lineups")
    if not lineups:
        return None
    
    try:
        return _parse_lineup(event_id,lineups)
    except Exception as exc:
        logger.warning("Skipping BSD lineup (parse error) [%s]: %s", event_id, exc)
        return None
    

async def _get(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None = None,
) -> dict | None:
    try:
        resp = await client.get(url, headers=_HEADERS, params=params, timeout=10)
 
        if resp.status_code == 401:
            logger.error("BSD auth failed — check BSD_API_KEY: %s", url)
            return None
        if resp.status_code == 429:
            logger.warning("BSD rate limit hit: %s", url)
            return None
 
        resp.raise_for_status()
        return resp.json()
 
    except httpx.HTTPError as exc:
        logger.error("BSD request failed [%s]: %s", url, exc)
        return None
 
 
# ── parsing ───────────────────────────────────────────────────────────────
 
def _parse_xg(raw: dict) -> MatchStats:
    # Prefer the final settled xG; fall back to the live running total
    # for matches still in progress.
    home_xg = raw.get("actual_home_xg")
    if home_xg is None:
        home_xg = raw.get("home_xg_live")
 
    away_xg = raw.get("actual_away_xg")
    if away_xg is None:
        away_xg = raw.get("away_xg_live")
 
    return MatchStats(
        match_id=str(raw["id"]),
        home_xg=home_xg,
        away_xg=away_xg,
    )
 
 
def _parse_lineup(event_id: str, lineups: dict) -> MatchLineup:
    home = lineups.get("home", {})
    away = lineups.get("away", {})
 
    return MatchLineup(
        match_id=event_id,
        home_lineup=[_parse_player(p) for p in home.get("players", [])],
        away_lineup=[_parse_player(p) for p in away.get("players", [])],
        home_formation=home.get("formation"),
        away_formation=away.get("formation"),
    )
 
 
def _parse_player(raw: dict) -> Player:
    number = raw.get("jersey_number")
    return Player(
        id=str(raw["player_id"]) if raw.get("player_id") is not None else None,
        name=raw["name"],
        position=raw.get("specific_position") or raw.get("position"),
        number=int(number) if number is not None and str(number).isdigit() else None,
    )
         
