import asyncio
from storage.sqlite_client import get_db, close_db

SQL = """
SELECT m.utc_date, ht.name AS home_team, at.name AS away_team, m.home_score, m.away_score
FROM matches m
JOIN teams ht ON m.home_team_id = ht.id
JOIN teams at ON m.away_team_id = at.id
WHERE (ht.short_name LIKE '%Bayern%' OR at.short_name LIKE '%Bayern%')
AND m.status = 'FINISHED'
ORDER BY m.utc_date DESC
"""


async def test():
    db = await get_db()

    # step 1: raw execute — does it return rows?
    async with db.execute(SQL) as cur:
        rows = await cur.fetchmany(20)
        desc = cur.description
    print(f"Step 1 — raw execute rows: {len(rows)}")
    if rows:
        print("Sample row:", dict(zip([d[0] for d in desc], rows[0])))

    # step 2: run through query_sql_stats with pre-set SQL to bypass LLM
    from agents.sql_stats import _clean_sql, _format_rows
    cleaned = _clean_sql(SQL)
    print(f"\nStep 2 — after _clean_sql:\n{cleaned}\n")

    async with db.execute(cleaned) as cur:
        rows2 = await cur.fetchmany(20)
        desc2 = cur.description
    print(f"Step 2 — cleaned SQL rows: {len(rows2)}")
    if rows2:
        print(_format_rows(rows2[:3], desc2))

    await close_db()


asyncio.run(test())