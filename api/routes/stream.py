from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from config.settings import get_settings
from pipeline.models import LiveScore
from storage.redis_client import get_redis,stream_key

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()

_SCAN_COUNT = 50

@router.get("/scores")
async def get_scores()-> list[dict]:
    redis = await get_redis()
    latest: dict[str,dict] = {}

    for competition in settings.competitions:
        try:
            entries = await redis.xrevrange(stream_key(competition),count = _SCAN_COUNT)
        except Exception as exc:
            logger.warning("xrevrange failed for %s: %s", competition, exc)
            continue

        for _entry_id, fields in entries:
            try:
                score = LiveScore.from_redis_dict(fields)
                if score.match_id not in latest:
                    latest[score.match_id]= score.model_dump()
            except Exception as exc:
                logger.warning("Failed to parse entry in %s: %s", competition, exc)
 
    return list(latest.values())

@router.get("/stream")
async def stream_scores(request: Request)-> EventSourceResponse:

    async def event_generator():
        redis = await get_redis()

        last_ids: dict[str,str] = {
            stream_key(comp): "$" for comp in settings.competitions
        }

        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break
            try:
                results = await redis.xread(
                    last_ids,
                    block= settings.redis_block_ms,
                    count = 10
                )
            except Exception as exc:
                logger.warning("xread failed: %s", exc)
                await asyncio.sleep(1)
                continue
 
            if not results:
                continue

            for stream_name, entries in results:
                stream_str = (stream_name.decode() if isinstance(stream_name, bytes) else stream_name)
                for entry_id, fields in entries:
                    entry_str = (entry_id.decode() if isinstance(entry_id,bytes) else entry_id)
                    try:
                        score = LiveScore.from_redis_dict(fields)
                        yield{
                            "event":"score_update", 
                            "data": json.dumps(score.model_dump())
                        }
                        last_ids[stream_str] = entry_str
                    except Exception as exc:                # noqa: BLE001
                        logger.warning("Failed to parse stream entry: %s", exc)
 
    return EventSourceResponse(event_generator())
