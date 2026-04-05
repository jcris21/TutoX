from unittest.mock import MagicMock, patch

import pytest

from ms_ai.app.user_interactions import UserInteractionManager


@pytest.fixture
def interaction_manager():
    """Create a UserInteractionManager instance for testing"""
    manager = UserInteractionManager()
    manager.reset_cache()  # Reset cache before test
    yield manager
    manager.reset_cache()


@pytest.fixture
def mock_chroma_collection():
    """Create a mock ChromaDB collection"""
    collection = MagicMock()
    collection.add = MagicMock()
    collection.get = MagicMock()
    collection.query = MagicMock()
    collection.delete = MagicMock()
    return collection


@pytest.fixture
def sample_chat_message():
    """Sample chat event data"""
    return {
        "type": "chat",
        "message": "How do I create a quotation?",
        "context": {"model": "sale.order"},
    }


@pytest.fixture
def sample_feedback_event():
    """Sample feedback event data"""
    return {
        "type": "feedback_event",
        "event_name": "ai_feedback",
        "event_data": {
            "message_body_text": "The response was helpful",
            "message_body_html": "<p>The response was helpful</p>",
            "message_uid": "18a152c3-dfbd-4483-bc29-6d9d1a5654e8",
            "vote": "up",
            "saved_to_odoo": True,
        },
    }


@pytest.fixture
def sample_ui_event():
    """Sample UI event data"""
    return {
        "type": "ui_event",
        "event_name": "button_click",
        "event_data": {
            "button_id": "create_quotation",
            "timestamp": "2025-12-28T21:08:48.558Z",
        },
    }


@pytest.fixture
def manager():
    """Fixture for the manager with mocked ChromaDB"""
    from ms_ai.app.user_interactions import UserInteractionManager

    manager = UserInteractionManager()

    # Patch the collection to use mock
    from tests.conftest import mock_collection

    manager._collection = mock_collection

    manager.reset_cache()
    yield manager
    manager.reset_cache()


class TestUserInteractionManager:
    """Test suite for UserInteractionManager"""

    def test_initialization(self, interaction_manager):
        """Test manager initialization"""
        assert interaction_manager.client is None
        assert interaction_manager.collection is None

    @patch("ms_ai.app.user_interactions.get_chroma_client")
    def test_get_or_create_collection_new(
        self, mock_get_chroma_client, interaction_manager, mock_chroma_collection
    ):
        """Test creating a new collection"""
        interaction_manager.reset_cache()  # Clear cache

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_chroma_collection
        mock_get_chroma_client.return_value = mock_client

        collection = interaction_manager._get_collection()

        # Verify behavior: get_or_create_collection was called
        assert collection is not None
        mock_client.get_or_create_collection.assert_called_once_with(
            name="user_interactions", metadata={"hnsw:space": "cosine"}
        )

    @patch("ms_ai.app.user_interactions.get_chroma_client")
    def test_get_or_create_collection_existing(
        self, mock_get_chroma_client, interaction_manager, mock_chroma_collection
    ):
        """Test retrieving an existing collection"""
        interaction_manager.reset_cache()  # Clear cache

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_chroma_collection
        mock_get_chroma_client.return_value = mock_client

        collection = interaction_manager._get_collection()

        # Verify behavior: get_or_create_collection was called
        assert collection is not None
        mock_client.get_or_create_collection.assert_called_once_with(
            name="user_interactions", metadata={"hnsw:space": "cosine"}
        )

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_save_user_interaction_chat(
        self,
        mock_get_collection,
        interaction_manager,
        sample_chat_message,
        mock_chroma_collection,
    ):
        """Test saving a chat interaction"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        user_login = "test_user"
        session_id = "test_session_123"

        interaction_id = interaction_manager.save_user_interaction(
            user_login=user_login,
            session_id=session_id,
            interaction_type="chat",
            event_data=sample_chat_message,
            message_text="How do I create a quotation?",
        )

        # Verify interaction was saved
        assert interaction_id is not None
        mock_chroma_collection.add.assert_called_once()

        # Verify metadata
        call_args = mock_chroma_collection.add.call_args
        assert call_args[1]["ids"][0] == interaction_id
        assert call_args[1]["documents"][0] == "How do I create a quotation?"

        metadata = call_args[1]["metadatas"][0]
        assert metadata["user_login"] == user_login
        assert metadata["session_id"] == session_id
        assert metadata["interaction_type"] == "chat"

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_save_feedback_interaction(
        self,
        mock_get_collection,
        interaction_manager,
        sample_feedback_event,
        mock_chroma_collection,
    ):
        """Test saving a feedback interaction"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        user_login = "test_user"
        session_id = "test_session_456"

        interaction_id = interaction_manager.save_user_interaction(
            user_login=user_login,
            session_id=session_id,
            interaction_type="feedback_event",
            event_data=sample_feedback_event,
        )

        # Verify interaction was saved
        assert interaction_id is not None
        mock_chroma_collection.add.assert_called_once()

        # Verify metadata contains feedback-specific fields
        call_args = mock_chroma_collection.add.call_args
        metadata = call_args[1]["metadatas"][0]
        assert metadata["interaction_type"] == "feedback_event"
        assert metadata["event_name"] == "ai_feedback"
        assert metadata["feedback_type"] == "ai_feedback"

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_save_ui_event_interaction(
        self,
        mock_get_collection,
        interaction_manager,
        sample_ui_event,
        mock_chroma_collection,
    ):
        """Test saving a UI event interaction"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        user_login = "test_user"
        session_id = "test_session_789"

        interaction_id = interaction_manager.save_user_interaction(
            user_login=user_login,
            session_id=session_id,
            interaction_type="ui_event",
            event_data=sample_ui_event,
        )

        # Verify interaction was saved
        assert interaction_id is not None
        mock_chroma_collection.add.assert_called_once()

        # Verify metadata
        call_args = mock_chroma_collection.add.call_args
        metadata = call_args[1]["metadatas"][0]
        assert metadata["interaction_type"] == "ui_event"
        assert metadata["event_name"] == "button_click"

    @patch("ms_ai.app.user_interactions.get_chroma_client")
    def test_save_interaction_handles_errors_gracefully(
        self, mock_get_chroma_client, interaction_manager, sample_chat_message
    ):
        """Test that errors during save are handled gracefully"""
        # Mock ChromaDB client to raise an error
        mock_client = MagicMock()
        mock_client.get_or_create_collection.side_effect = Exception("ChromaDB error")
        mock_get_chroma_client.return_value = mock_client

        # Should return None instead of raising
        interaction_id = interaction_manager.save_user_interaction(
            user_login="test_user",
            session_id="session_123",
            interaction_type="chat",
            event_data=sample_chat_message,
        )

        assert interaction_id is None

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_user_interactions(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test retrieving user interactions"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        # Mock ChromaDB response
        mock_chroma_collection.get.return_value = {
            "ids": ["interaction_1", "interaction_2"],
            "documents": ["Chat message 1", "Feedback text"],
            "metadatas": [
                {
                    "user_login": "test_user",
                    "interaction_type": "chat",
                    "timestamp": "2025-12-28T21:00:00Z",
                },
                {
                    "user_login": "test_user",
                    "interaction_type": "feedback_event",
                    "timestamp": "2025-12-28T21:05:00Z",
                },
            ],
        }

        interactions = interaction_manager.get_user_interactions("test_user")

        assert len(interactions) == 2
        assert interactions[0]["interaction_id"] == "interaction_1"
        assert interactions[1]["metadata"]["interaction_type"] == "feedback_event"
        mock_chroma_collection.get.assert_called_once()

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_user_interactions_filtered_by_type(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test retrieving user interactions filtered by type"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        mock_chroma_collection.get.return_value = {
            "ids": ["interaction_1"],
            "documents": ["Chat message"],
            "metadatas": [
                {
                    "user_login": "test_user",
                    "interaction_type": "chat",
                }
            ],
        }

        interactions = interaction_manager.get_user_interactions(
            "test_user", interaction_type="chat"
        )

        assert len(interactions) == 1
        call_args = mock_chroma_collection.get.call_args
        where_filter = call_args[1]["where"]
        assert where_filter == {
            "$and": [
                {"user_login": "test_user"},
                {"interaction_type": "chat"},
            ]
        }

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_session_interactions(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test retrieving session interactions"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        mock_chroma_collection.get.return_value = {
            "ids": ["interaction_1"],
            "documents": ["Message"],
            "metadatas": [
                {
                    "user_login": "test_user",
                    "session_id": "session_123",
                    "timestamp": "2025-12-28T21:00:00Z",
                }
            ],
        }

        interactions = interaction_manager.get_session_interactions(
            session_id="session_123"
        )

        assert len(interactions) == 1
        call_args = mock_chroma_collection.get.call_args
        where_filter = call_args[1]["where"]
        assert where_filter["session_id"] == "session_123"

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_search_user_interactions(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test semantic search over user interactions"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        # Mock semantic search response
        mock_chroma_collection.query.return_value = {
            "ids": [["interaction_1", "interaction_2"]],
            "documents": [["Chat message", "Similar feedback"]],
            "metadatas": [
                [
                    {"user_login": "test_user", "interaction_type": "chat"},
                    {"user_login": "test_user", "interaction_type": "feedback_event"},
                ]
            ],
            "distances": [[0.2, 0.35]],  # Lower distance = higher similarity
        }

        results = interaction_manager.search_interactions(
            query="How to create a quotation?", user_login="test_user", n_results=2
        )

        assert len(results) == 2
        assert results[0]["similarity_score"] > results[1]["similarity_score"]
        mock_chroma_collection.query.assert_called_once()

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_found(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test retrieving a specific interaction"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        mock_chroma_collection.get.return_value = {
            "ids": ["interaction_1"],
            "documents": ["Chat message"],
            "metadatas": [{"user_login": "test_user", "interaction_type": "chat"}],
        }

        interaction = interaction_manager.get_interaction_by_id("interaction_1")

        assert interaction is not None
        assert interaction["interaction_id"] == "interaction_1"

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_not_found(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test retrieving a non-existent interaction"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        mock_chroma_collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }

        interaction = interaction_manager.get_interaction_by_id("nonexistent")

        assert interaction is None

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_delete_interaction(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Test deleting a single interaction"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        result = interaction_manager.delete_interaction("interaction_1")

        assert result is True
        mock_chroma_collection.delete.assert_called_once_with(ids=["interaction_1"])


class TestGetInteractionById:
    """Tests for get_interaction_by_id with user_login filter"""

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_with_user_login_found(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """get_interaction_by_id when filtering by user_login"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        user_login = "test_user"
        interaction_id = "test_interaction_123"

        mock_chroma_collection.get.return_value = {
            "ids": [interaction_id],
            "documents": ["Hello"],
            "metadatas": [
                {
                    "user_login": user_login,
                    "interaction_type": "chat",
                }
            ],
        }

        result = interaction_manager.get_interaction_by_id(
            interaction_id=interaction_id, user_login=user_login
        )

        assert result is not None
        assert result["interaction_id"] == interaction_id
        assert result["metadata"]["user_login"] == user_login
        assert result["metadata"]["interaction_type"] == "chat"
        mock_chroma_collection.get.assert_called_once()

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_without_user_login(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Must find interaction without user_login filter (if exists)"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        interaction_id = "test_interaction_456"

        mock_chroma_collection.get.return_value = {
            "ids": [interaction_id],
            "documents": ["Hello"],
            "metadatas": [
                {
                    "user_login": "test_user",
                    "interaction_type": "chat",
                }
            ],
        }

        result = interaction_manager.get_interaction_by_id(
            interaction_id=interaction_id, user_login=None
        )

        assert result is not None
        assert result["interaction_id"] == interaction_id
        mock_chroma_collection.get.assert_called_once()

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_wrong_user_returns_none(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Must return None when filtering by incorrect user_login"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        interaction_id = "test_interaction_789"

        mock_chroma_collection.get.return_value = {
            "ids": [interaction_id],
            "documents": ["Hello"],
            "metadatas": [
                {
                    "user_login": "original_user",
                    "interaction_type": "chat",
                }
            ],
        }

        result = interaction_manager.get_interaction_by_id(
            interaction_id=interaction_id, user_login="different_user"
        )

        assert result is None

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_nonexistent(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Must return None for nonexistent interaction_id"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        mock_chroma_collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }

        result = interaction_manager.get_interaction_by_id(
            interaction_id="nonexistent_id", user_login="test_user"
        )

        assert result is None

    @patch("ms_ai.app.user_interactions.UserInteractionManager._get_collection")
    def test_get_interaction_by_id_multiple_types(
        self, mock_get_collection, interaction_manager, mock_chroma_collection
    ):
        """Must work with all interaction types"""
        mock_get_collection.return_value = mock_chroma_collection
        interaction_manager.collection = mock_chroma_collection

        user_login = "test_user"
        chat_id = "chat_123"
        feedback_id = "feedback_456"
        ui_id = "ui_789"

        # Test chat type
        mock_chroma_collection.get.return_value = {
            "ids": [chat_id],
            "documents": ["Chat message"],
            "metadatas": [
                {
                    "user_login": user_login,
                    "interaction_type": "chat",
                }
            ],
        }

        chat_result = interaction_manager.get_interaction_by_id(
            interaction_id=chat_id, user_login=user_login
        )
        assert chat_result["metadata"]["interaction_type"] == "chat"

        # Test feedback type
        mock_chroma_collection.get.return_value = {
            "ids": [feedback_id],
            "documents": ["Feedback text"],
            "metadatas": [
                {
                    "user_login": user_login,
                    "interaction_type": "feedback_event",
                }
            ],
        }

        feedback_result = interaction_manager.get_interaction_by_id(
            interaction_id=feedback_id, user_login=user_login
        )
        assert feedback_result["metadata"]["interaction_type"] == "feedback_event"

        # Test UI event type
        mock_chroma_collection.get.return_value = {
            "ids": [ui_id],
            "documents": ["UI Event"],
            "metadatas": [
                {
                    "user_login": user_login,
                    "interaction_type": "ui_event",
                }
            ],
        }

        ui_result = interaction_manager.get_interaction_by_id(
            interaction_id=ui_id, user_login=user_login
        )
        assert ui_result["metadata"]["interaction_type"] == "ui_event"
