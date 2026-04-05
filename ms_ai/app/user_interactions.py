import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .vectordb import get_chroma_client

logger = logging.getLogger(__name__)


class UserInteractionManager:
    """
    Manager for user interactions stored in ChromaDB.
    Handles saving and retrieving user interactions including:
    - Chat messages
    - Feedback events
    - UI events
    """

    def __init__(self):
        self.client = None
        self.collection = None

    def reset_cache(self):
        """Reset the client and collection cache - useful for testing"""
        self.client = None
        self.collection = None

    def _get_collection(self):
        """Get or create user_interactions collection"""
        try:
            if self.collection is None:
                self.client = get_chroma_client()
                self.collection = self.client.get_or_create_collection(
                    name="user_interactions", metadata={"hnsw:space": "cosine"}
                )
                logger.info("user_interactions collection ready")
            return self.collection
        except Exception as e:
            logger.error(f"Error getting collection: {e}")
            raise

    def _sanitize_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure metadata values are valid for Chroma Cloud.
        Only allow: str, int, float, bool.
        Convert None → "" and complex types → str().
        """
        safe = {}

        for key, value in meta.items():
            if value is None:
                safe[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                safe[key] = value
            else:
                safe[key] = str(value)

        return safe

    def save_user_interaction(
        self,
        user_login: str,
        session_id: str,
        interaction_type: str,
        event_data: Dict[str, Any],
        message_text: str = "",
    ) -> Optional[str]:
        """
        Save a user interaction to ChromaDB (Cloud-safe).
        """
        try:
            collection = self._get_collection()

            interaction_id = str(uuid.uuid4())

            logger.info(
                f"Saving interaction: type={interaction_type}, "
                f"user={user_login}, id={interaction_id}"
            )

            metadata = {
                "user_login": user_login or "",
                "session_id": session_id or "",
                "interaction_type": interaction_type or "",
                "timestamp": datetime.utcnow().isoformat(),
            }

            # --- Event specific metadata ---
            if interaction_type == "feedback_event":
                metadata["event_name"] = event_data.get("event_name") or ""
                metadata["feedback_type"] = event_data.get("event_name") or ""

            elif interaction_type == "chat":
                metadata["exercise_id"] = event_data.get("exercise_id") or ""
                metadata["step"] = (
                    int(event_data.get("current_step"))
                    if event_data.get("current_step") is not None
                    else 0
                )

            elif interaction_type == "ui_event":
                metadata["event_name"] = event_data.get("event_name") or ""
                metadata["model"] = event_data.get("context", {}).get("model") or ""

            # Sanitize for Chroma
            metadata = self._sanitize_metadata(metadata)

            document_text = (
                message_text.strip()
                if message_text and message_text.strip()
                else f"{interaction_type} event"
            )

            collection.add(
                ids=[interaction_id],
                documents=[document_text],
                metadatas=[metadata],
            )

            logger.info(f"Interaction saved: {interaction_id}")
            return interaction_id

        except Exception as e:
            logger.error(f"Error saving interaction: {e}", exc_info=True)
            return None

    def get_user_interactions(
        self,
        user_login: str,
        interaction_type: Optional[str] = None,
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve user interactions from ChromaDB.

        Args:
            user_login: User email/login
            interaction_type: Optional filter by type ("chat", "feedback_event", etc.)
            n_results: Number of results to return (truncado en Python)

        Returns:
            List of interaction dicts
        """
        try:
            collection = self._get_collection()

            logger.info(
                f"Retrieving interactions for user={user_login}, "
                f"type={interaction_type}, limit={n_results}"
            )

            # ChromaDB 1.x requires $and for multiple conditions
            if interaction_type:
                where_filter = {
                    "$and": [
                        {"user_login": user_login},
                        {"interaction_type": interaction_type},
                    ]
                }
            else:
                where_filter = {"user_login": user_login}

            logger.info(f"Filter: {where_filter}")

            results = collection.get(
                where=where_filter, include=["metadatas", "documents"]
            )

            interactions = []

            if results and results.get("ids"):
                logger.info(
                    f"Found {len(results['ids'])} interactions (before truncation)"
                )

                # New: truncate in Python to n_results
                for interaction_id, metadata, document in zip(
                    results["ids"][:n_results],
                    results.get("metadatas", [])[:n_results],
                    results.get("documents", [])[:n_results],
                ):
                    interactions.append(
                        {
                            "interaction_id": interaction_id,
                            "user_login": metadata.get("user_login"),
                            "session_id": metadata.get("session_id"),
                            "interaction_type": metadata.get("interaction_type"),
                            "timestamp": metadata.get("timestamp"),
                            "document": document,
                            "metadata": metadata,
                        }
                    )

                logger.info(
                    f"Returning {len(interactions)} interactions (after truncation)"
                )

            return interactions

        except Exception as e:
            logger.error(f"Error retrieving interactions: {e}", exc_info=True)
            return []

    def get_interaction_by_id(
        self, interaction_id: str, user_login: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific interaction by ID.

        Args:
            interaction_id: Interaction ID (UUID)
            user_login: Optional - filter by user (recommended for security)

        Returns:
            Interaction dict or None
        """
        try:
            collection = self._get_collection()

            logger.info(f"Retrieving interaction: {interaction_id}")

            results = collection.get(
                ids=[interaction_id], include=["metadatas", "documents"]
            )

            if results and results.get("ids") and len(results["ids"]) > 0:
                metadata = results["metadatas"][0] if results["metadatas"] else {}
                document = results["documents"][0] if results["documents"] else ""

                # Security: verify user_login matches if provided
                if user_login and metadata.get("user_login") != user_login:
                    return None

                interaction = {
                    "interaction_id": interaction_id,
                    "document": document,
                    "metadata": metadata,
                }

                logger.info(f"Interaction found: {interaction_id}")
                return interaction
            else:
                logger.warning(f"Interaction not found: {interaction_id}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving interaction: {e}", exc_info=True)
            return None

    def search_interactions(
        self,
        query: str,
        user_login: Optional[str] = None,
        interaction_type: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over interactions.

        Args:
            query: Search query string
            user_login: Optional filter by user
            interaction_type: Optional filter by type
            n_results: Number of results

        Returns:
            List of matching interactions
        """
        try:
            collection = self._get_collection()

            logger.info(
                f"Semantic search: query='{query}', "
                f"user={user_login}, type={interaction_type}"
            )

            # ChromaDB 1.x requires $and for multiple conditions
            conditions = []
            if user_login:
                conditions.append({"user_login": user_login})
            if interaction_type:
                conditions.append({"interaction_type": interaction_type})

            if len(conditions) > 1:
                where_filter = {"$and": conditions}
            elif len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {}

            logger.info(f"Filter: {where_filter}")

            # Here we use n_results because query() supports it
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=["metadatas", "documents", "distances"],
            )

            interactions = []

            if results and results.get("ids") and len(results["ids"]) > 0:
                logger.info(f"Found {len(results['ids'][0])} matching interactions")

                for interaction_id, metadata, document, distance in zip(
                    results["ids"][0],
                    results["metadatas"][0] if results["metadatas"] else [],
                    results["documents"][0] if results["documents"] else [],
                    results["distances"][0] if results["distances"] else [],
                ):
                    similarity = 1 - distance

                    interactions.append(
                        {
                            "interaction_id": interaction_id,
                            "user_login": metadata.get("user_login"),
                            "session_id": metadata.get("session_id"),
                            "interaction_type": metadata.get("interaction_type"),
                            "timestamp": metadata.get("timestamp"),
                            "document": document,
                            "metadata": metadata,
                            "similarity_score": similarity,
                        }
                    )

            return interactions

        except Exception as e:
            logger.error(f"Error searching interactions: {e}", exc_info=True)
            return []

    def delete_interaction(self, interaction_id: str) -> bool:
        """
        Delete an interaction by ID.

        Args:
            interaction_id: Interaction ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            collection = self._get_collection()

            logger.info(f"Deleting interaction: {interaction_id}")

            collection.delete(ids=[interaction_id])

            logger.info(f"Interaction deleted: {interaction_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting interaction: {e}", exc_info=True)
            return False

    def get_session_interactions(
        self,
        session_id: str,
        n_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get all interactions for a specific session.

        Args:
            session_id: Session ID
            n_results: Maximum number of results to return

        Returns:
            List of interactions ordered by timestamp
        """
        try:
            collection = self._get_collection()

            logger.info(f"Retrieving interactions for session: {session_id}")

            # Filter by session_id
            where_filter = {"session_id": session_id}

            results = collection.get(
                where=where_filter, include=["metadatas", "documents"]
            )

            interactions = []

            if results and results.get("ids"):
                logger.info(
                    f"Found {len(results['ids'])} interactions (before truncation)"
                )

                for interaction_id, metadata, document in zip(
                    results["ids"][:n_results],
                    results.get("metadatas", [])[:n_results],
                    results.get("documents", [])[:n_results],
                ):
                    interactions.append(
                        {
                            "interaction_id": interaction_id,
                            "user_login": metadata.get("user_login"),
                            "session_id": metadata.get("session_id"),
                            "interaction_type": metadata.get("interaction_type"),
                            "timestamp": metadata.get("timestamp"),
                            "document": document,
                            "metadata": metadata,
                        }
                    )

                logger.info(f"Returning {len(interactions)} interactions")

            return interactions

        except Exception as e:
            logger.error(f"Error retrieving session interactions: {e}", exc_info=True)
            return []


# Global instance
user_interaction_manager = UserInteractionManager()
