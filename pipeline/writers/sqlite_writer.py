from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite 

from config.settings import get_settings
from pipeline.models import Match, Scorer, Standing, Team

settings = get_settings()
logger =logging.getLogger(__name__)

async def upsert_team(db:aiosqlite.COnnection, team:Team)-> None:
    await db.execute(
        """
        INSERT INTO teams (id, name, short_name, tla)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, short_name=excluded.short_name, tla=excluded.tla
        """,
        (team.id, team.name, team.short_name, team.tla),        
    )

async def ensure_competition(db:aiosqlite.Connection, code: str)-> None:
    name = settings.competition_names.get(code,code)
    await db.execute(
        "INSERT OR IGNORE INTO competitions (id, name, code, country, season) "
        "VALUES (?, ?, ?, NULL, NULL)",
        (code, name, code),
    )

async def write_matches(db: aiosqlite.Connection,matches: list[Match])-> int:
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for m in matches:
        try:
            await ensure_competition(db, m.competition)
            await upsert_team(db, m.home_team)
            await upsert_team(db, m.away_team)
 
            await db.execute(
                """
                INSERT INTO matches (
                    id, competition, season, matchday, status, utc_date,
                    home_team_id, away_team_id, home_score, away_score,
                    ht_home, ht_away, minute, stage, group_name, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    home_score=excluded.home_score,
                    away_score=excluded.away_score,
                    ht_home=excluded.ht_home,
                    ht_away=excluded.ht_away,
                    minute=excluded.minute,
                    stage=excluded.stage,
                    group_name=excluded.group_name,
                    updated_at=excluded.updated_at
                """,
                (
                    m.id, m.competition, m.season, m.matchday, m.status.value,
                    m.utc_date.isoformat(),
                    m.home_team.id, m.away_team.id, m.home_score, m.away_score,
                    m.ht_home, m.ht_away, m.minute, m.stage, m.group, now,
                ),
            )
            written += 1
        except Exception as exc:                        # noqa: BLE001
            logger.warning("Skipping match write [%s]: %s", m.id, exc)
 
    await db.commit()
    return written

async def write_standings(db: aiosqlite.Connection,standings: list[Standing])->int:
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for s in standings:
        try:
            await ensure_competition(db,s.competition)
            await upsert_team(db,s.team)

            stage = s.stage or ""
            group_name = s.group or ""
            await db.execute(
                """
                INSERT INTO standings (
                    competition, season, stage, group_name, team_id, position,
                    played, won, drawn, lost, goals_for, goals_against,
                    goal_diff, points, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(competition, season, stage, group_name, team_id) DO UPDATE SET
                    position=excluded.position,
                    played=excluded.played,
                    won=excluded.won,
                    drawn=excluded.drawn,
                    lost=excluded.lost,
                    goals_for=excluded.goals_for,
                    goals_against=excluded.goals_against,
                    goal_diff=excluded.goal_diff,
                    points=excluded.points,
                    updated_at=excluded.updated_at
                """,
                (
                    s.competition, s.season, stage, group_name, s.team.id, s.position,
                    s.played, s.won, s.drawn, s.lost, s.goals_for, s.goals_against,
                    s.goal_diff, s.points, now,
                ),
            )
            written += 1
        except Exception as exc:                        # noqa: BLE001
            logger.warning("Skipping standing write [%s]: %s", s.team.name, exc)
 
    await db.commit()
    return written

async def write_scorers(db: aiosqlite.Connection, scorers: list[Scorer]) -> int:
    """Upsert a batch of scorer rows. Returns count written."""
    now = datetime.now(timezone.utc).isoformat()
    written = 0
 
    for sc in scorers:
        try:
            await ensure_competition(db, sc.competition)
            team_id = None
            if sc.team:
                await upsert_team(db, sc.team)
                team_id = sc.team.id
 
            await db.execute(
                """
                INSERT INTO scorers (
                    competition, season, player_name, team_id,
                    goals, assists, penalties, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(competition, season, player_name) DO UPDATE SET
                    team_id=excluded.team_id,
                    goals=excluded.goals,
                    assists=excluded.assists,
                    penalties=excluded.penalties,
                    updated_at=excluded.updated_at
                """,
                (
                    sc.competition, sc.season, sc.player_name, team_id,
                    sc.goals, sc.assists, sc.penalties, now,
                ),
            )
            written += 1
        except Exception as exc:                        # noqa: BLE001
            logger.warning("Skipping scorer write [%s]: %s", sc.player_name, exc)
 
    await db.commit()
    return written