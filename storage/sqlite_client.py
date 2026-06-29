import asyncio
import aiosqlite
from pathlib import Path

from config.settings import get_settings
settings = get_settings()

SCHEMA_PATH = Path(__file__).parent/"schema.sql"
_db: aiosqlite.Connection |None =None

async def get_db()-> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await _connect()
    return _db

async def _connect()-> aiosqlite.Connection:
    db_path = Path(settings.sqlite_db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_node=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await _run_schema(db)
    return db

async def _run_schema(db: aiosqlite.Connection)-> None:
    schema = SCHEMA_PATH.read_text()
    await db.executescript(schema)
    await db.commit()

async def close_db()-> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None