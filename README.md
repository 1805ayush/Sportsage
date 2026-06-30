# SportsSage ⚽

A multi-agent sports intelligence system that answers football/soccer questions using live World Cup 2026 data, historical match results, structured statistics, and real-time web search — built and deployed during the actual 2026 FIFA World Cup.

**Live demo:** https://sportsage.streamlit.app/
**API:** https://sportsage-api.onrender.com
**Repo:** https://github.com/1805ayush/Sportsage

---

## What it does

Ask a question in plain English — *"How is Argentina doing in the World Cup?"*, *"Who are the top scorers in the Premier League?"*, *"What's the latest news on Mbappé?"* — and SportsSage figures out which data source(s) can answer it, retrieves from the right ones in parallel, and synthesizes one coherent response.

No single API or database could answer all of these questions. The system routes between four specialist agents depending on what the question actually needs:

| Agent | Source | Handles |
|---|---|---|
| **Live** | Redis Streams (ESPN, polled every 15 min) | Current scores, match status, live minute |
| **Historical RAG** | ChromaDB + BM25 hybrid search | Past results, match history (907 seeded matches) |
| **SQL Stats** | SQLite (text-to-SQL via Groq) | Standings, top scorers, points, goal difference |
| **Web Search** | DuckDuckGo | Recent news, transfers, injuries |

A query like *"Compare Haaland's Premier League goals to the top World Cup scorers"* triggers **two agents in parallel**, merged into one answer by the synthesizer.

---

## Architecture

```
Sports APIs (ESPN, football-data.org, BSD)
        │
        ▼
  GitHub Actions — scheduled poller (every 15 min)
        │
        ├──→ Upstash Redis (live scores, delta-detected)
        └──→ SQLite + ChromaDB (standings, scorers, 907 historical match summaries)
                │
                ▼
        LangGraph agent pipeline
        Router → [Live | RAG | SQL | Web] (parallel) → Synthesizer
                │
                ▼
        Render (FastAPI + SSE) ──→ Streamlit Cloud (chat + live scoreboard)
```

A GitHub Actions workflow runs the polling pipeline every 15 minutes — completely serverless, no always-on infrastructure required. It writes live scores and structured stats into Upstash Redis and SQLite. User queries hit the LangGraph pipeline, which classifies intent, dispatches to the relevant agent(s) concurrently via `asyncio.gather`, and merges their outputs into one grounded answer.

---

## Tech stack

**Agent orchestration** — LangGraph, Groq (Llama 3.3 70B)
**Retrieval** — ChromaDB (vector) + BM25 (keyword), Reciprocal Rank Fusion for hybrid search
**Data pipeline** — `asyncio`, APScheduler, Redis Streams (delta detection, adaptive polling), scheduled via GitHub Actions
**Storage** — SQLite (`aiosqlite`), Upstash Redis, ChromaDB
**APIs** — ESPN (unofficial, live scores), football-data.org (standings/fixtures/scorers, 7 competitions), BSD (xG, lineups, formations)
**Backend** — FastAPI with Server-Sent Events, deployed on Render
**Frontend** — Streamlit (chat + live scoreboard, custom football-pitch theme with SVG pitch markings), deployed on Streamlit Cloud
**Evaluation** — RAGAS (faithfulness, answer relevancy), custom routing-accuracy harness

Entirely free-tier infrastructure — no paid APIs, models, or hosting required.

---

## Results

Evaluated on 20 hand-curated queries, balanced across all four intent types:

| Metric | Score | Target |
|---|---|---|
| Routing accuracy (overall) | **95%** | >75% |
| Routing accuracy — live / SQL / web | 100% each | — |
| Routing accuracy — RAG | 80% | — |
| Answer relevancy (RAGAS) | **0.805** | >0.92 |
| Faithfulness (RAGAS) | **0.562** | >0.78 |

**Known limitation:** faithfulness is below target. When multiple agents contribute context, the synthesizer occasionally blends in plausible-sounding details not present in any retrieved source — most visible when web search results (which can include all-time records) get merged with current-season stats. This is a known failure mode of multi-source LLM synthesis; tightening the synthesizer's system prompt to strictly forbid adding facts beyond the provided context is the identified fix, not yet re-evaluated.

---

## Build notes — real engineering, not a clean-room demo

This was built live, end-to-end, debugged against real APIs with real data:

- **ESPN's soccer clock format** (`"63'"` not `"63:00"`) required custom minute parsing.
- **Scheduled matches showing `0-0`** is indistinguishable from a genuine scoreless draw — fixed by returning `None` for unstarted matches.
- **World Cup knockout fixtures** with undetermined teams (`null` before the bracket resolves) handled with a `TBD` placeholder instead of dropping the match.
- **Stale match data** — the poller only fetches "today's" ESPN scoreboard, so a finished match from a previous day can freeze in its last-known `SCHEDULED` state if never re-polled. Fixed at the UI layer by dropping any `SCHEDULED` match whose kickoff time has already passed, caught live during testing when the Round of 32 knockout results (Morocco eliminating the Netherlands on penalties, Paraguay's historic upset of Germany) showed as "upcoming" hours after they'd actually finished.
- **football-data.org's free tier doesn't serve live scores** — confirmed via direct API testing. Live data comes from ESPN; football-data.org covers standings/fixtures/scorers instead.
- **LangGraph 0.2.x state-passing issue** — router output wasn't reliably available to downstream nodes via the standard multi-node graph pattern; resolved by collapsing routing + agent dispatch into a single coordinator node.
- **Background workers require paid tiers** on most free hosting (Render, Fly.io) — solved by running the poller as a scheduled GitHub Actions workflow instead, which is free and a legitimate production pattern for periodic jobs.

---

## Project structure

```
sportsage/
├── pipeline/          # Fetchers (ESPN, football-data.org, BSD) + writers (Redis, SQLite, ChromaDB)
├── storage/            # DB clients + schema
├── agents/              # LangGraph nodes: router, live, RAG, SQL, web, synthesizer, graph
├── api/                  # FastAPI server + SSE stream endpoint
├── ui/                    # Streamlit app, chat, scoreboard
├── ingestion/         # One-time historical data seeding
├── eval/                  # RAGAS + routing accuracy eval harness
├── config/             # Typed settings (Pydantic)
├── .github/workflows/  # Scheduled poller (every 15 min)
└── main.py            # Poller entrypoint
```

---

## Running locally

```bash
git clone https://github.com/1805ayush/Sportsage
cd Sportsage
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # add your API keys

# one-time historical seeding
python -m ingestion.seed_sqlite
python -m ingestion.seed_chroma

# run all three (separate terminals)
python main.py                                    # poller
uvicorn api.server:app --reload --port 8000        # API
streamlit run ui/app.py                            # UI
```

Free API keys needed: [Groq](https://console.groq.com), [football-data.org](https://www.football-data.org/client/register), [BSD](https://sports.bzzoiro.com/register/).

---

## Deployment

- **Streamlit Cloud** — chat UI + live scoreboard
- **Render** (free tier) — FastAPI SSE backend
- **Upstash** (free tier) — Redis for live score streaming
- **GitHub Actions** (free, public repo) — scheduled poller, runs every 15 minutes

Note: Render's free web service spins down after 15 minutes of inactivity — first API request after idle takes ~30s to wake up.
