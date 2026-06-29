from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from datasets import Dataset
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, faithfulness

from agents.graph import graph
from agents.state import AgentState
from config.settings import get_settings
from storage.redis_client import close_redis
from storage.sqlite_client import close_db

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

QUERIES_FILE = Path("eval/queries.json")
RESULTS_DIR  = Path("eval/results")
RESULTS_DIR.mkdir(exist_ok=True)

# seconds between queries — Groq free tier: ~6k tokens/min
# each query uses ~2–4 LLM calls × ~500 tokens = 1–2k tokens
_QUERY_SLEEP = 15

# agent outputs that mean "nothing useful retrieved" — excluded from contexts
_EMPTY_RESPONSES = {
    "No live match data is currently available.",
    "No historical data has been indexed yet.",
    "No results found for this query.",
    "No recent web results found for this query.",
    "Web search failed — no results available.",
    "Failed to generate a SQL query.",
    "Could not generate a safe query for this question.",
    "No answer generated.",
}


# ── data loading ──────────────────────────────────────────────────────────
from itertools import islice

def load_queries(limit: int | None = None) -> list[dict]:
    raw = QUERIES_FILE.read_text()
    clean = re.sub(r"//.*", "", raw)           # strip JS-style comments
    queries = json.loads(clean)["queries"]
    if limit:
        # take evenly from each category
        by_cat = {}
        for q in queries:
            by_cat.setdefault(q["category"], []).append(q)
        per_cat = limit // len(by_cat)
        balanced = []
        for cat_queries in by_cat.values():
            balanced.extend(cat_queries[:per_cat])
        return balanced
    return queries


# ── query execution ───────────────────────────────────────────────────────

async def run_single_query(question: str) -> dict:
    """Run a query through the full agent pipeline and capture state."""
    # capture routing separately — LangGraph doesn't reliably pass intents
    # back in ainvoke() return value (known state-merging issue in 0.2.x)
    from agents.router import classify_intent

    # retry classify_intent up to 3 times on rate limit errors
    intents = ["web"]
    for attempt in range(3):
        try:
            routing = await classify_intent({"query": question})
            intents = routing.get("intents", ["web"])
            break
        except Exception as exc:
            if "429" in str(exc) or "rate_limit" in str(exc).lower():
                wait = (attempt + 1) * 30
                logger.warning("Rate limit hit — waiting %ds before retry %d/3", wait, attempt + 1)
                time.sleep(wait)
            else:
                logger.error("classify_intent failed: %s", exc)
                break

    initial_state: AgentState = {
        "query":        question,
        "intents":      [],
        "live_data":    None,
        "rag_data":     None,
        "sql_data":     None,
        "web_data":     None,
        "final_answer": None,
        "error":        None,
    }
    state = await graph.ainvoke(initial_state)

    # collect non-trivial agent outputs as contexts for RAGAS
    contexts = [
        val for field in ("live_data", "rag_data", "sql_data", "web_data")
        if (val := state.get(field)) and val not in _EMPTY_RESPONSES
    ]

    return {
        "intents":  intents,                           # from direct classify_intent call
        "answer":   state.get("final_answer", ""),
        "contexts": contexts or ["No context retrieved."],
    }


# ── metrics ───────────────────────────────────────────────────────────────

def compute_routing_accuracy(results: list[dict]) -> dict:
    """Routing accuracy: at least one expected intent was dispatched."""
    per_cat: dict[str, dict] = {}
    correct = 0

    for r in results:
        hit = bool(set(r["expected_intents"]) & set(r["actual_intents"]))
        if hit:
            correct += 1

        cat = r["category"]
        if cat not in per_cat:
            per_cat[cat] = {"correct": 0, "total": 0}
        per_cat[cat]["total"] += 1
        if hit:
            per_cat[cat]["correct"] += 1

    return {
        "overall": correct / len(results) if results else 0.0,
        "per_category": {
            cat: v["correct"] / v["total"]
            for cat, v in per_cat.items()
        },
    }


def compute_ragas_metrics(results: list[dict]) -> dict:
    """Run RAGAS faithfulness + answer_relevancy using Groq + local embeddings."""
    logger.info("Running RAGAS evaluation (%d samples)...", len(results))

    ragas_llm = LangchainLLMWrapper(ChatGroq(
        model=settings.groq_model,
        temperature=0.0,
        api_key=settings.groq_api_key,
    ))
    ragas_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name=settings.embedding_model)
    )

    dataset = Dataset.from_dict({
        "question":     [r["question"]   for r in results],
        "answer":       [r["answer"]     for r in results],
        "contexts":     [r["contexts"]   for r in results],
        "ground_truth": [r["ground_truth"] for r in results],
    })

    scores = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=ragas_llm,
        embeddings=ragas_embeddings,
    )
    df = scores.to_pandas()
    return {
        "faithfulness":     float(df["faithfulness"].mean()),
        "answer_relevancy": float(df["answer_relevancy"].mean()),
    }


# ── main ──────────────────────────────────────────────────────────────────

async def main(limit: int | None = None) -> None:
    queries = load_queries(limit)
    logger.info("Evaluating %d queries (sleep=%ds between each)...",
                len(queries), _QUERY_SLEEP)

    results = []
    for i, q in enumerate(queries):
        logger.info("[%d/%d] %s", i + 1, len(queries), q["question"][:70])
        try:
            output = await run_single_query(q["question"])
        except Exception as exc:                        # noqa: BLE001
            logger.error("Query %s failed: %s", q["id"], exc)
            output = {"intents": [], "answer": "ERROR", "contexts": ["ERROR"]}

        results.append({
            "id":               q["id"],
            "category":         q["category"],
            "question":         q["question"],
            "expected_intents": q["expected_intents"],
            "actual_intents":   output["intents"],
            "answer":           output["answer"],
            "contexts":         output["contexts"],
            "ground_truth":     q["ground_truth"],
        })

        if i < len(queries) - 1:
            time.sleep(_QUERY_SLEEP)

    # ── compute metrics ───────────────────────────────────────────────────
    routing = compute_routing_accuracy(results)
    ragas   = compute_ragas_metrics(results)

    # ── save results ──────────────────────────────────────────────────────
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"eval_{ts}.json"
    out_file.write_text(json.dumps({
        "timestamp":        ts,
        "n_queries":        len(results),
        "routing_accuracy": routing,
        "ragas_scores":     ragas,
        "results":          results,
    }, indent=2))

    # ── summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print(f"  Queries evaluated:   {len(results)}")
    print(f"  Routing accuracy:    {routing['overall']:.1%}  (overall)")
    for cat, acc in routing["per_category"].items():
        print(f"    {cat:<8}            {acc:.1%}")
    print(f"  Faithfulness:        {ragas['faithfulness']:.3f}")
    print(f"  Answer relevancy:    {ragas['answer_relevancy']:.3f}")
    print(f"  Results saved →      {out_file}")
    print("=" * 55)

    await close_redis()
    await close_db()


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(limit=_limit))