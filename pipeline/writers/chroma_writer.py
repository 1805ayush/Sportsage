from __future__ import annotations

import asyncio
import logging

from storage.chroma_client import get_collection

logger = logging.getLogger(__name__)

DocChunk = dict

async def write_chunks(chunks:list[DocChunk], batch_size: int=100)-> int:
    if not chunks:
        return 0
    
    collection = get_collection()
    written =0

    for i in range(0,len(chunks),batch_size):
        batch = chunks[i:i+batch_size]
        ids = [c["id"] for c in batch]
        documents = [c["text"] for c in batch]
        metadatas = [c.get("metadata",{}) for c in batch]
        try:
            await asyncio.to_thread(
                collection.upsert,
                ids=ids,
                documents = documents,
                metadatas =metadatas
            )
            written+=len(batch)
        except Exception as exc:
            logger.warning("Skipping ChromaDB batch (write error) [%d:%d]: %s",i, i + len(batch), exc,)
 
    return written       


def chunk_text(text:str,chunk_size: int =500, overlap: int =50)->list[str]:
    words = text.split()
    if len(words)<=chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start+chunk_size
        chunks.append(" ".join(words[start:end]))
        if end>=len(words):
            break
        start = end -overlap
    return chunks

def build_chunks_from_document(doc_id: str, text:str, 
    metadata: dict, chunk_size: int =500, overlap: int =50)-> list[DocChunk]:
    pieces = chunk_text(text,chunk_size=chunk_size,overlap=overlap)
    chunks: list[DocChunk] =[]
    for idx, piece in enumerate(pieces):
        chunk_meta = dict(metadata)
        chunk_meta["source_doc_id"] = doc_id
        chunk_meta["chunk_index"] = idx

        chunks.append({
            "id": f"{doc_id}_chunk{idx}",
            "text": piece,
            "metadata": chunk_meta
        })
    return chunks