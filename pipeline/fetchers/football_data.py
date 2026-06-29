from __future__ import annotations

import logging

import httpx

from config.settings import get_settings
from pipeline.models import Match, MatchStatus, Scorer, Standing, Team

settings = get_settings()
logger = logging.getLogger(__name__)

_HEADERS = {"X-Auth-Token": settings.football_data_api_key}

# football-data.org free tier: 10 req/min — settings.football_data_request_gap
# enforces the gap between calls; the poller is responsible for spacing them out.


# ── public fetchers ──────────────────────────────────────────────────────

async def fetch_standings(
    client: httpx.AsyncClient,
    competition: str,
) -> list[Standing]:
    """Fetch current league/group standings for a competition."""
    url = f"{settings.football_data_base_url}/competitions/{competition}/standings"

    data = await _get(client, url)
    if data is None:
        return []

    season = data.get("season", {}).get("startDate", "")[:4]
    season_year = int(season) if season.isdigit() else 0

    standings: list[Standing] = []
    for group in data.get("standings", []):
        stage = group.get("stage")
        group_name = group.get("group")

        for row in group.get("table", []):
            try:
                standings.append(_parse_standing_row(row, competition, season_year, stage, group_name))
            except Exception as exc:                    # noqa: BLE001
                logger.warning("Skipping standings row (parse error): %s", exc)

    return standings


async def fetch_matches(
    client: httpx.AsyncClient,
    competition: str,
    status: str | None = None,
) -> list[Match]:
    """Fetch fixtures/results for a competition.

    Args:
        status: optional filter — SCHEDULED, FINISHED, LIVE, etc.
                (football-data.org param, not our MatchStatus enum)
    """
    url = f"{settings.football_data_base_url}/competitions/{competition}/matches"
    params = {"status": status} if status else None

    data = await _get(client, url, params=params)
    if data is None:
        return []

    matches: list[Match] = []
    for raw in data.get("matches", []):
        try:
            matches.append(_parse_match(raw, competition))
        except Exception as exc:                        # noqa: BLE001
            logger.warning("Skipping match (parse error): %s", exc)

    return matches


async def fetch_scorers(
    client: httpx.AsyncClient,
    competition: str,
    limit: int = 20,
) -> list[Scorer]:
    """Fetch top scorers for a competition."""
    url = f"{settings.football_data_base_url}/competitions/{competition}/scorers"
    params = {"limit": limit}

    data = await _get(client, url, params=params)
    if data is None:
        return []

    season = data.get("season", {}).get("startDate", "")[:4]
    season_year = int(season) if season.isdigit() else 0

    scorers: list[Scorer] = []
    for raw in data.get("scorers", []):
        try:
            scorers.append(_parse_scorer(raw, competition, season_year))
        except Exception as exc:                        # noqa: BLE001
            logger.warning("Skipping scorer (parse error): %s", exc)

    return scorers


# ── HTTP helper ───────────────────────────────────────────────────────────

async def _get(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None = None,
) -> dict | None:
    try:
        resp = await client.get(url, headers=_HEADERS, params=params, timeout=10)

        if resp.status_code == 429:
            logger.warning("football-data.org rate limit hit: %s", url)
            return None

        resp.raise_for_status()
        return resp.json()

    except httpx.HTTPError as exc:
        logger.error("football-data.org request failed [%s]: %s", url, exc)
        return None


# ── parsing ───────────────────────────────────────────────────────────────

def _team_from(raw: dict | None) -> Team:
    # World Cup / Champions League knockout fixtures are often scheduled
    # before the teams are decided (e.g. "Winner Group A") — football-data.org
    # represents this as a team object with id/name set to None. Use a TBD
    # placeholder instead of dropping the whole match, so the bracket
    # structure is still captured ahead of time.
    if not raw or raw.get("id") is None:
        return Team(id="TBD", name="TBD", short_name="TBD", tla="TBD")

    return Team(
        id=str(raw["id"]),
        name=raw.get("name") or "TBD",
        short_name=raw.get("shortName"),
        tla=raw.get("tla"),
    )


def _parse_standing_row(
    row: dict,
    competition: str,
    season: int,
    stage: str | None,
    group_name: str | None,
) -> Standing:
    return Standing(
        competition=competition,
        season=season,
        position=row["position"],
        team=_team_from(row["team"]),
        played=row["playedGames"],
        won=row["won"],
        drawn=row["draw"],
        lost=row["lost"],
        goals_for=row["goalsFor"],
        goals_against=row["goalsAgainst"],
        goal_diff=row["goalDifference"],
        points=row["points"],
        stage=stage,
        group=group_name,
    )


_STATUS_MAP = {
    "SCHEDULED": MatchStatus.SCHEDULED,
    "TIMED": MatchStatus.SCHEDULED,
    "IN_PLAY": MatchStatus.IN_PLAY,
    "PAUSED": MatchStatus.PAUSED,
    "FINISHED": MatchStatus.FINISHED,
    "POSTPONED": MatchStatus.POSTPONED,
    "CANCELLED": MatchStatus.CANCELLED,
    "SUSPENDED": MatchStatus.SUSPENDED,
}


def _parse_match(raw: dict, competition: str) -> Match:
    score = raw.get("score", {})
    full_time = score.get("fullTime", {})
    half_time = score.get("halfTime", {})

    season_str = raw.get("season", {}).get("startDate", "")[:4]
    season_year = int(season_str) if season_str.isdigit() else 0

    return Match(
        id=str(raw["id"]),
        competition=competition,
        season=season_year,
        matchday=raw.get("matchday"),
        status=_STATUS_MAP.get(raw["status"], MatchStatus.SCHEDULED),
        utc_date=raw["utcDate"],
        home_team=_team_from(raw["homeTeam"]),
        away_team=_team_from(raw["awayTeam"]),
        home_score=full_time.get("home"),
        away_score=full_time.get("away"),
        ht_home=half_time.get("home"),
        ht_away=half_time.get("away"),
        stage=raw.get("stage"),
        group=raw.get("group"),
    )


def _parse_scorer(raw: dict, competition: str, season: int) -> Scorer:
    player = raw.get("player", {})
    team_raw = raw.get("team")

    return Scorer(
        competition=competition,
        season=season,
        player_name=player.get("name", "Unknown"),
        team=_team_from(team_raw) if team_raw else None,
        goals=raw.get("goals", 0),
        assists=raw.get("assists") or 0,
        penalties=raw.get("penalties") or 0,
    )