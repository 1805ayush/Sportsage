from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ───────────────────────────────────────────────────────────────
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.0

    # ── Sports APIs ───────────────────────────────────────────────────────
    football_data_api_key: str
    football_data_base_url: str = "https://api.football-data.org/v4"
    # ESPN, WC2026, BSD — no keys needed
    espn_base_url: str = "https://site.api.espn.com/apis/site/v2/sports/soccer"
    bsd_api_key: str
    bsd_base_url: str = "https://sports.bzzoiro.com"

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    redis_stream_maxlen: int = 1000     # MAXLEN per stream — keeps memory bounded
    redis_block_ms: int = 5_000         # XREAD BLOCK timeout in ms (SSE endpoint)

    # ── SQLite ────────────────────────────────────────────────────────────
    sqlite_db_path: str = "data/db/sportsage.db"

    # ── ChromaDB ──────────────────────────────────────────────────────────
    chroma_persist_path: str = "data/chroma"
    chroma_collection_name: str = "sports_history"
    embedding_model: str = "all-MiniLM-L6-v2"  # sentence-transformers, runs locally

    # ── Polling intervals (seconds) ───────────────────────────────────────
    poll_interval_live: int = 30        # match status IN_PLAY or PAUSED
    poll_interval_prematch: int = 120   # kickoff within 2 hours
    poll_interval_idle: int = 300       # no active matches

    # football-data.org free tier: 10 req/min → minimum 6s between calls
    football_data_request_gap: float = 6.5

    # ── Competitions ──────────────────────────────────────────────────────
    # football-data.org codes — all covered by the free tier
    competitions: list[str] = ["PL", "WC", "CL", "BL1", "SA", "FL1", "PD"]

    competition_names: dict[str, str] = {
        "PL":  "Premier League",
        "WC":  "FIFA World Cup",
        "CL":  "UEFA Champions League",
        "BL1": "Bundesliga",
        "SA":  "Serie A",
        "FL1": "Ligue 1",
        "PD":  "La Liga",
    }

    # ESPN league slugs (maps to competition codes above)
    espn_league_slugs: dict[str, str] = {
        "PL":  "eng.1",
        "WC":  "fifa.world",
        "CL":  "uefa.champions",
        "BL1": "ger.1",
        "SA":  "ita.1",
        "FL1": "fra.1",
        "PD":  "esp.1",
    }

    bsd_league_ids: dict[str, int] = {
        "PL":  1,
        "PD":  3,
        "SA":  4,
        "BL1": 5,
        "FL1": 6,
        "CL":  7,
        "WC":  27,
    }

    # ── Retrieval ─────────────────────────────────────────────────────────
    bm25_top_k: int = 20        # candidates from BM25 before rerank
    chroma_top_k: int = 20      # candidates from ChromaDB before rerank
    rag_final_top_k: int = 5    # docs passed to synthesizer after rerank

    # ── FastAPI SSE server ────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Misc ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()