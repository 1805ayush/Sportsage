from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.stream import router as stream_router
from config.settings import get_settings

settings = get_settings()
logging.basicConfig(level = settings.log_level)

app = FastAPI(
    title = "SportsSage API",
    description="Live sports data — scores, SSE stream",
    version="1.0.0",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
 
app.include_router(stream_router, prefix="/api/v1", tags=["scores"])
 
 
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
