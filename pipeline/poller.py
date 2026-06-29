from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
 
from config.settings import get_settings
from pipeline.models import MatchStatus
from pipeline.fetchers.espn import fetch_live_scores
from pipeline.fetchers.football_data import fetch_matches, fetch_scorers, fetch_standings
from pipeline.writers.redis_writer import write_live_scores
from pipeline.writers.sqlite_writer import write_matches, write_scorers, write_standings
from storage.redis_client import get_redis
from storage.sqlite_client import get_db
 
settings = get_settings()
logger = logging.getLogger(__name__)
 
_LIVE_JOB_ID = "poll_live_scores"
_STANDINGS_JOB_ID = "poll_standings_and_stats"

class Poller:
    def __init__(self)->None:
        self.scheduler = AsyncIOScheduler()
        self.client: httpx.AsyncClient |None =None
        self._current_live_interval = settings.poll_interval_idle
    
    async def start(self)-> None:
        self.client =httpx.AsyncClient()
        self.scheduler.add_job(
            self.poll_live_scores,
            "interval",
            seconds = settings.poll_interval_idle,
            id = _LIVE_JOB_ID,
            next_run_time = datetime.now(),
            max_instances =1
        )

        self.scheduler.add_job(
            self.poll_standings_and_stats,
            "interval",
            seconds=300,
            id= _STANDINGS_JOB_ID,
            next_run_time = datetime.now(),
            max_instances =1
        )

        self.scheduler.start()
        logger.info("Poller started — live job + standings job scheduled")

    async def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        if self.client:
            await self.client.aclose()
        logger.info("Poller stopped")
    
    async def poll_live_scores(self)-> None:
        redis = await get_redis()
        any_live = False
        total_written = 0

        for competition in settings.competitions:
            scores = await fetch_live_scores(self.client, competition)
            if any(s.status in (MatchStatus.IN_PLAY, MatchStatus.PAUSED) for s in scores):
                any_live = True
            total_written += await write_live_scores(redis,scores)
        logger.info(
            "Live poll: %d competitions checked, %d deltas written",
            len(settings.competitions), total_written,
        )
        self._adapt_interval(any_live)

    def _adapt_interval(self, any_live: bool)->None:
        target = settings.poll_interval_live if any_live else settings.poll_interval_idle
        if target!=self._current_live_interval:
            self.scheduler.reschedule_job(
                _LIVE_JOB_ID, trigger="interval", seconds=target
            )
            self._current_live_interval =target
            logger.info(
                "Adaptive polling: interval changed to %ds(%s)",
                target,"live" if any_live else "idle"
            )
    
    async def poll_standings_and_stats(self) -> None:
            db = await get_db()

            try:
                for competition in settings.competitions:
                    standings = await fetch_standings(self.client, competition)
                    await write_standings(db, standings)
                    await asyncio.sleep(settings.football_data_request_gap)  # respect 10 req/min

                    scorers = await fetch_scorers(self.client, competition)
                    await write_scorers(db, scorers)
                    await asyncio.sleep(settings.football_data_request_gap)

                    matches = await fetch_matches(self.client, competition)
                    await write_matches(db, matches)
                    await asyncio.sleep(settings.football_data_request_gap)
            except asyncio.CancelledError:
                logger.info("Standings poll cancelled mid-cycle (shutdown) — will resume next run")
                raise

            logger.info("Standings/scorers/fixtures poll complete (%d competitions)", len(settings.competitions))

