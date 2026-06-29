from __future__ import annotations

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from config.settings import get_settings

settings = get_settings()

_client: chromadb.PersistentClient | None = None
_collection: chromadb.Collection | None=None

def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_path)
    return _client

def get_collection()-> chromadb.Collection:
    global _collection
    if _collection is None:
        client = get_client()
        embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name = settings.embedding_model
        )
        _collection = client.get_or_create_collection(
            name = settings.chroma_collection_name,
            embedding_function = embedding_fn,
            metadata = {"hnsw:space":"cosine"}
        )
    return _collection