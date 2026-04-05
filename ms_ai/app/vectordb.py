import logging
import os
import time
from typing import Dict, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from dotenv import load_dotenv

load_dotenv()

_client: Optional[ClientAPI] = None
_collection: Optional[Collection] = None

MAX_RETRIES = 3
RETRY_DELAY = 2


def reset_client() -> None:
    """Reset the global client and collection - useful for testing."""
    global _client, _collection
    _client = None
    _collection = None


def get_chroma_client() -> ClientAPI:
    """Get ChromaDB client - using HttpClient for Chroma Cloud"""
    global _client
    if _client is None:
        api_key = os.getenv("CHROMA_API_KEY")
        tenant = os.getenv("CHROMA_TENANT", "default_tenant")
        database = os.getenv("CHROMA_DATABASE", "default_database")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                _client = chromadb.HttpClient(
                    host="api.trychroma.com",
                    port=443,
                    ssl=True,
                    tenant=tenant,
                    database=database,
                    headers={"x-chroma-token": api_key},
                )
                logging.info(
                    f"ChromaDB HttpClient initialized successfully "
                    f"(tenant={tenant}, database={database})"
                )
                break
            except Exception as e:
                logging.error(
                    f"Failed to initialize ChromaDB client "
                    f"(attempt {attempt}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    raise
    return _client


_collections: Dict[str, Collection] = {}


def get_chroma_collection(name: str = "exercises_structured") -> Collection:
    global _collections

    if name in _collections and _collections[name] is not None:
        return _collections[name]

    client = get_chroma_client()

    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        try:
            collection = client.get_collection(name=name)
        except Exception:
            collection = client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )

    if collection is None:
        raise ValueError(f"Failed to get or create collection: {name}")

    _collections[name] = collection
    return collection


async def load_exercise_metadata(exercise_id: str) -> Optional[dict]:
    """Load full exercise metadata from ChromaDB by document ID."""
    collection = get_chroma_collection()

    results = collection.get(ids=[exercise_id], include=["metadatas"])

    if not results or not results.get("metadatas"):
        return None

    return results["metadatas"][0]
