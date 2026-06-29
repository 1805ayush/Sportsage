from __future__ import annotations

import asyncio
import logging

import httpx

from config.settings import get_settings
from pipeline.fetchers.football_data import fetch_matches,fetch_scorers,fetch_standings
from pipeline.writers.sqlite_writer import write_matches, write_scorers,write_standings
from storage.sqlite_client import close_db, get_db

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

async def seed_competition(client: httpx.AsyncClient, db, competition: str)-> None:
    name = settings.competition_names.get(competition, competition)
    print(f"\n--- {name}    ({competition}) ---")
    standings = await fetch_standings(client,competition)
    written = await write_standings(db,standings)

    print(f"    Standings:  {written} rows")
    await asyncio.sleep(settings.football_data_request_gap)

    scorers =await fetch_scorers(client, competition,limit=20)

    written = await write_scorers(db,scorers)

    print(f"    Scorers:    {written} rows")
    await asyncio.sleep(settings.football_data_request_gap)

    matches = await fetch_matches(client, competition,status="FINISHED")
    written = await write_matches(db,matches)

    print(f"  Matches:   {written} rows (finished only)")
    await asyncio.sleep(settings.football_data_request_gap)

async def main()-> None:
    db = await get_db()

    print(f"Seeding {len(settings.competitions)} competitions...")
    print(f"(respecting football-data.org's {settings.football_data_request_gap}s rate-limit gap — this will take a few minutes)")
    async with httpx.AsyncClient() as client:
        for competition in settings.competitions:
            try:
                await seed_competition(client, db, competition)
            except Exception as exc:
                logger.error("Failed to seed %s: %s", competition, exc)
    await close_db()
    print("\nSeeding complete.")

if __name__ == "__main__":
    asyncio.run(main())




