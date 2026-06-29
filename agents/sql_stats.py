from __future__ import annotations

import logging 
import re
import aiosqlite
from langchain_groq import ChatGroq

from agents.state import AgentState
from config.settings import get_settings
from storage.sqlite_client import get_db

settings = get_settings()
logger = logging.getLogger(__name__)
 

_SCHEMA = """
Tables in the SportsSage SQLite database:
 
competitions(id TEXT PK, name TEXT, code TEXT)
  -- competition codes: PL=Premier League, WC=World Cup, CL=Champions League,
  --   BL1=Bundesliga, SA=Serie A, FL1=Ligue 1, PD=La Liga
 
teams(id TEXT PK, name TEXT, short_name TEXT, tla TEXT)
  -- tla = three-letter code e.g. ARS, MCI, BRA
 
matches(id TEXT PK, competition TEXT FK->competitions.id,
        season INTEGER, matchday INTEGER, status TEXT,
        utc_date TEXT, home_team_id TEXT FK->teams.id,
        away_team_id TEXT FK->teams.id,
        home_score INTEGER, away_score INTEGER,
        ht_home INTEGER, ht_away INTEGER,
        stage TEXT, group_name TEXT)
  -- status: SCHEDULED | IN_PLAY | PAUSED | FINISHED | POSTPONED | CANCELLED
  -- stage: GROUP_STAGE | REGULAR_SEASON | ROUND_OF_16 | QUARTER_FINALS |
  --        SEMI_FINALS | FINAL | LEAGUE_STAGE
  -- group_name: 'Group A', 'Group B' ... (World Cup only, empty string otherwise)
  -- IMPORTANT: join teams twice — once for home, once for away — to get names
 
standings(id INTEGER PK, competition TEXT, season INTEGER,
          stage TEXT, group_name TEXT,
          team_id TEXT FK->teams.id, position INTEGER,
          played INTEGER, won INTEGER, drawn INTEGER, lost INTEGER,
          goals_for INTEGER, goals_against INTEGER,
          goal_diff INTEGER, points INTEGER)
  -- IMPORTANT: join teams to get team name from team_id
 
scorers(id INTEGER PK, competition TEXT, season INTEGER,
        player_name TEXT, team_id TEXT,
        goals INTEGER, assists INTEGER, penalties INTEGER)
  -- player_name is stored directly as a string
"""
 
_SYSTEM_PROMPT = f"""You are a SQL expert generating SQLite queries for SportsSage,
a football/soccer Q&A system.
 
{_SCHEMA}
 
Rules — follow exactly:
1. Return ONLY the raw SQL query. No explanation, no markdown, no backticks.
2. Only SELECT statements. Never INSERT, UPDATE, DELETE, or DROP.
3. When referencing teams in matches, always join the teams table twice:
     JOIN teams ht ON m.home_team_id = ht.id
     JOIN teams at ON m.away_team_id = at.id
4. For team name searches use short LIKE fragments — team names are stored in
   their NATIVE LANGUAGE form (e.g. "FC Bayern München" not "Bayern Munich",
   "Paris Saint-Germain" not "PSG", "Internazionale" not "Inter Milan").
   Use the shortest unambiguous fragment: '%Bayern%', '%Dortmund%', '%Arsenal%'
5. For top scorers: ORDER BY goals DESC LIMIT 10
6. For standings: ORDER BY position ASC
7. For season filters: Bundesliga/PL/La Liga/Serie A/Ligue 1 current season is stored as season=2025 (start year of 2025-26). World Cup is season=2026. Champions League is season=2025.
8. Never filter by season unless the user specifically asks about a particular season."""
 
_llm = ChatGroq(
    model = settings.groq_model,
    temperature = 0.0,
    api_key = settings.groq_api_key
)

async def query_sql_stats(state: AgentState)-> dict:
    query = state["query"]

    try:
        response = await _llm.ainvoke([
            ("system",_SYSTEM_PROMPT),
            ("human",query),
        ])
        sql = _clean_sql(response.content)
    except Exception as exc:
        logger.error("SQL generation failed for %r: %s", query, exc)
        return {"sql_data": "Failed to generate a SQL query."}
    
    if not sql.upper().lstrip().startswith("SELECT"):
        logger.warning("Non-SELECT SQL blocked: %r", sql)
        return {"sql_data": "Could not generate a safe query for this question."}
 
    logger.info("Executing generated SQL: %s", sql)

    db = await get_db()
    try:
        async with db.execute(sql) as cur:
            rows = await cur.fetchmany(20)
            desc = cur.description
    except aiosqlite.Error as exc:
        logger.error("SQL execution failed [%s]: %s", sql, exc)
        return {"sql_data": f"Query execution failed: {exc}"}
 
    if not rows:
        return {"sql_data": "No results found for this query."}
 
    return {"sql_data": _format_rows(rows, desc)}


def _clean_sql(text: str) -> str:
    """Strip markdown fences and trailing semicolons — LLMs often add these."""
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    return text.strip().rstrip(";").strip()
 
 
def _format_rows(rows: list, description) -> str:
    """Format result rows as human-readable text with column labels."""
    if not description:
        return str(rows)
 
    col_names = [d[0] for d in description]
    lines = []
    for row in rows:
        parts = [f"{col}={val}" for col, val in zip(col_names, row)]
        lines.append("  ".join(parts))
 
    return "\n".join(lines)

