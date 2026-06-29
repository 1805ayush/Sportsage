from __future__ import annotations 

import asyncio
import logging

from config.settings import get_settings
from pipeline.writers.chroma_writer import build_chunks_from_document, write_chunks
from storage.sqlite_client import close_db,get_db

settings = get_settings()
logging.basicConfig(level= settings.log_level)
logger = logging.getLogger(__name__)

 
_QUERY = """
SELECT
    m.id, m.competition, c.name AS competition_name, m.season,
    m.utc_date, m.home_score, m.away_score, m.stage, m.group_name,
    ht.name AS home_name, at.name AS away_name
FROM matches m
JOIN teams ht ON m.home_team_id = ht.id
JOIN teams at ON m.away_team_id = at.id
JOIN competitions c ON m.competition = c.id
WHERE m.status = 'FINISHED'
  AND m.home_score IS NOT NULL
  AND m.away_score IS NOT NULL
  AND ht.name != 'TBD'
  AND at.name != 'TBD'
"""

def _build_summary(row)->str:
    home,away = row["home_name"], row["away_name"]
    hs, as_ = row["home_score"], row["away_score"]
    comp = row["competition_name"]
    date = (row["utc_date"] or "")[:10]

    if hs > as_:
        result = f"{home} defeated {away} {hs}-{as_}"
    elif as_ > hs:
        result = f"{away} defeated {home} {as_}-{hs}"
    else:
        result = f"{home} and {away} drew {hs}-{hs}"

    summary = f"{result} in the {comp}"

    if row["stage"]:
        summary += f" ({row['stage']}"
        summary += f", {row['group_name']})" if row["group_name"] else ")"
    if date:
        summary += f". Played on {date}."
    else:
        summary += "."
    return summary

async def main()-> None:
    db = await get_db()
    async with db.execute(_QUERY) as cur:
        rows =await cur.fetchall()
    
    if not rows:
        print("No finished matches found in SQLite.")
        print("Run 'python -m ingestion.seed_sqlite' first, then retry.")
        await close_db()
        return
    print(f"Found {len(rows)} finished matches. Building summaries...")

    all_chunks= []
    for row in rows:
        summary = _build_summary(row)
        chunks = build_chunks_from_document(
            doc_id=f"match_{row['id']}",
            text=summary,
            metadata={
                "competition": row["competition"],
                "season": row["season"],
                "home_team": row["home_name"],
                "away_team": row["away_name"],
                "type": "match_result",
            },
        )
        all_chunks.extend(chunks)
    print(f"Writing {len(all_chunks)} chunks to ChromaDB...")
    written = await write_chunks(all_chunks)
    print(f"Done — {written} chunks embedded and stored.")
 
    await close_db()
 
 
if __name__ == "__main__":
    asyncio.run(main())   


