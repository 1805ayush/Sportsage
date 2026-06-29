from __future__ import annotations

import hashlib
import logging
import redis.asyncio as aioredis

from config.settings import get_settings
from pipeline.models import LiveScore
from storage.redis_client import stream_key

settings = get_settings()
logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 6*60*60

async def write_live_score(redis: aioredis.Redis, score: LiveScore)-> bool:
    state_key = f"last_state:{score.match_id}"
    new_hash = _hash_score(score)

    old_hash_raw = await redis.get(state_key)
    old_hash = old_hash_raw.decode() if old_hash_raw else None

    if old_hash==new_hash:
        return False
    await redis.set(state_key,new_hash,ex = _STATE_TTL_SECONDS)
    stream = stream_key(score.competition)
    await redis.xadd(
        stream,
        score.to_redis_dict(),
        maxlen = settings.redis_stream_maxlen,
        approximate = True
    )

    logger.info(
        "Score delta written: %s %s-%s %s [%s]",
        score.home_team, score.home_score, score.away_score,
        score.away_team, score.status,
    )
    return True

async def write_live_scores(redis: aioredis.Redis, scores: list[LiveScore])->int:
    written = 0
    for score in scores:
        if await write_live_score(redis,score):
            written+=1
    return written

def _hash_score(score: LiveScore) -> str:
    payload = f"{score.home_score}|{score.away_score}|{score.status}|{score.minute}"
    return hashlib.md5(payload.encode()).hexdigest()
 