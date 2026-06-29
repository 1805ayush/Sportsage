from __future__ import annotations
import asyncio
import logging
import signal
from config.settings import get_settings
from pipeline.poller import Poller
from storage.redis_client import close_redis
from storage.sqlite_client import close_db

settings =get_settings()

logging.basicConfig(
    level = settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

async def main()->None:
    poller = Poller()
    stop_event = asyncio.Event()

    def _handle_shutdown_signal()-> None:
        logger.info("Shutdown signal received")
        stop_event.set()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_shutdown_signal)
        except NotImplementedError:
            pass
    await poller.start()
    logger.info(
        "SportsSage poller running — %d competitions tracked. Press Ctrl+C to stop.",
        len(settings.competitions),
    )
 
    await stop_event.wait()
 
    logger.info("Shutting down...")
    await poller.stop()
    await close_redis()
    await close_db()
    logger.info("Shutdown complete.")
 
 
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # fallback for platforms where the signal handler above isn't wired up
        logger.info("Interrupted — exiting.")
