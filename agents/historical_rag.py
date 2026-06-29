from __future__ import annotations

import asyncio
import logging

from rank_bm25 import BM25Okapi

from agents.state import AgentState
from config.settings import get_settings
from storage.chroma_client import get_collection

settings = get_settings()
logger = logging.getLogger(__name__)

_bm25_index: BM25Okapi | None= None
_corpus_ids: list[str] = []
_id_to_text: dict[str,str] = {}

async def _ensure_bm25_index() -> None:
    global _bm25_index, _corpus_ids,_id_to_text

    if _bm25_index is not None:
        return 
    
    collection = get_collection()
    data = await asyncio.to_thread(collection.get, include=["documents"])

    ids = data.get("ids",[])
    docs = data.get("documents",[])

    if not ids:
        logger.warning("ChromaDB collection is empty — run ingestion/seed_chroma.py first")
        return
    
    _corpus_ids = ids
    _id_to_text = dict(zip(ids,docs))

    tokenized = [doc.lower().split() for doc in docs]
    _bm25_index = BM25Okapi(tokenized)

    logger.info("BM25 index built over %d documents", len(ids))

async def search_historical(state: AgentState)-> dict:
    query = state["query"]
    await _ensure_bm25_index()

    if _bm25_index is None:
        return {"rag_data":"No historical data has been indexed yet."}
    
    collection =get_collection()
    chroma_results = await asyncio.to_thread(
        collection.query,
        query_texts =[query],
        n_results = settings.chroma_top_k
    )

    chroma_ids = chroma_results["ids"][0] if chroma_results.get("ids") else []

    tokenized_query = query.lower().split()
    bm25_scores = _bm25_index.get_scores(tokenized_query)
    ranked_indices = sorted(
        range(len(bm25_scores)),key =lambda i: bm25_scores[i],reverse = True
    )[: settings.bm25_top_k]
    bm25_ids = [_corpus_ids[i] for i in ranked_indices]

    fused_ids = _reciprocal_rank_fusion([chroma_ids,bm25_ids],top_k =settings.rag_final_top_k)

    if not fused_ids:
        return {"rag_data": "No relevant historical data found."}
    
    lines = [_id_to_text[doc_id] for doc_id in fused_ids if doc_id in _id_to_text]
    return {"rag_data": "\n".join(f"- {line}" for line in lines)}

def _reciprocal_rank_fusion(ranked_lists: list[list[str]],top_k: int, k:int=60)-> list[str]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
 
    return sorted(scores.keys(), key=lambda d: scores[d], reverse=True)[:top_k]   
    