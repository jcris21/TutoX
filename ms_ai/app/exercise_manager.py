import json
import logging
from typing import Any, Dict, List, Optional

from .models import Exercise, ExerciseStep
from .vectordb import get_chroma_client

logger = logging.getLogger(__name__)

_collection = None
collection_name = "exercises_structured"

def get_or_create_collection():
    global _collection

    if _collection is None:
        client = get_chroma_client()

        try:
            _collection = client.get_collection(name=collection_name)
        except Exception:
            _collection = client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Collection '{collection_name}' created")

    return _collection

def save_exercise(exercise: Exercise) -> str:

    collection = get_or_create_collection()

    exercise_doc = json.dumps(exercise.model_dump(), indent=2)

    metadata = {
        "exercise_id": exercise.exercise_id,
        "module": exercise.module,
        "goal": exercise.goal,
        "odoo_version": exercise.odoo_version,
        "step_count": len(exercise.steps),
        "created_at": exercise.created_at,
    }

    collection.add(
        ids=[exercise.exercise_id],
        documents=[exercise_doc],
        metadatas=[metadata],
    )

    return exercise.exercise_id

def get_step(state, step_index: int):

    doc_raw = state.get("exercise_document")

    if not doc_raw:
        return None

    try:
        doc = json.loads(doc_raw) if isinstance(doc_raw, str) else doc_raw
    except Exception:
        return None

    steps = doc.get("steps", [])

    if step_index >= len(steps):
        return None

    return steps[step_index]

def get_exercise(self, exercise_id: str) -> Optional[Exercise]:
        """
        Retrieves a complete exercise with all steps

        Args:
            exercise_id: Exercise ID to retrieve

        Returns:
            Exercise object or None
        """
        try:
            collection = self._get_or_create_collection()

            results = collection.get(
                ids=[exercise_id],
                include=["documents", "metadatas"],
            )

            if not results["documents"]:
                return None

            exercise_data = json.loads(results["documents"][0])
            return Exercise(**exercise_data)

        except Exception as e:
            logger.error(f"Error retrieving exercise: {e}")
            return None

def search_exercises(query: str, n_results: int = 5) -> List[Dict[str, Any]]:

    collection = get_or_create_collection()

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["metadatas", "documents", "distances"],
    )

    exercises = []

    for metadata, document, distance in zip(
        results["metadatas"][0],
        results["documents"][0],
        results["distances"][0],
    ):
        exercises.append(
            {
                "exercise_id": metadata.get("exercise_id"),
                "module": metadata.get("module"),
                "goal": metadata.get("goal"),
                "step_count": metadata.get("step_count"),
                "similarity_score": 1 - distance,
            }
        )

    return exercises