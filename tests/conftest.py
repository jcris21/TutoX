import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ms_ai.app.user_interactions import UserInteractionManager
from ms_ai.app.websocket import WebSocketHandler

# ============================================================================
# MOCK CHROMADB BEFORE ANY IMPORTS
# ============================================================================

# Create mock collection FIRST
mock_collection = MagicMock()
mock_collection.add = MagicMock()

# In-memory storage for added documents so get()/where queries can work sensibly
_mock_storage: dict = {}  # id -> {"document": str, "metadata": dict}


def add_side_effect(*, ids=None, documents=None, metadatas=None, **kwargs):
    """Store added documents/metadata in-memory so get() can return them later."""
    if ids is None:
        return
    id_list = ids if isinstance(ids, list) else [ids]
    for i, iid in enumerate(id_list):
        doc = documents[i] if documents and i < len(documents) else None
        meta = metadatas[i] if metadatas and i < len(metadatas) else {}
        # Ensure interaction_id present in stored metadata
        meta = dict(meta)
        meta.setdefault("interaction_id", iid)
        _mock_storage[iid] = {"document": doc, "metadata": meta}
    return True


# Mock get() to return data for retrieval with PROPER SECURITY FILTERING
def mock_get_side_effect(**kwargs):
    """
    Mock get() to handle both adds and retrievals against _mock_storage.
    ✅ SECURITY: Filter by user_login when provided in where clause
    """
    where = kwargs.get("where")
    ids = kwargs.get("ids")

    # Request by explicit ids
    if ids:
        id_list = ids if isinstance(ids, list) else [ids]
        docs = []
        metas = []
        for iid in id_list:
            entry = _mock_storage.get(iid)
            if entry:
                docs.append(entry["document"])
                metas.append(entry["metadata"])
            else:
                docs.append(None)
                metas.append({})
        return {"ids": id_list, "documents": docs, "metadatas": metas}

    # where filters
    if where:
        # Security filter: {"$and": [{"user_login": {"$eq": u}}, {"interaction_id": {"$eq": id}}]}
        if "$and" in where:
            conditions = where["$and"]
            user_login = None
            interaction_id = None
            for cond in conditions:
                if "user_login" in cond:
                    user_login = cond["user_login"].get("$eq")
                if "interaction_id" in cond:
                    interaction_id = cond["interaction_id"].get("$eq")

            if interaction_id:
                entry = _mock_storage.get(interaction_id)
                # Security: only return if user_login matches
                if entry:
                    stored_user = entry["metadata"].get("user_login")
                    if user_login is None or stored_user == user_login:
                        # Return only if no user filter OR user matches
                        return {
                            "ids": [interaction_id],
                            "documents": [entry["document"]],
                            "metadatas": [entry["metadata"]],
                        }
                # User mismatch or entry not found
                return {"ids": [], "documents": [], "metadatas": []}

        # Simple filter by user_login / interaction_type
        # where = {"user_login": {"$eq": u}, "interaction_type": {"$eq": t}} or similar
        user_eq = None
        type_eq = None
        if isinstance(where, dict):
            if "user_login" in where:
                user_eq = where["user_login"].get("$eq")
            if "interaction_type" in where:
                type_eq = where["interaction_type"].get("$eq")

        matched_ids = []
        docs = []
        metas = []
        for iid, entry in _mock_storage.items():
            meta = entry["metadata"]
            # Security: filter by user_login if specified
            if user_eq and meta.get("user_login") != user_eq:
                continue
            if type_eq and meta.get("interaction_type") != type_eq:
                continue
            matched_ids.append(iid)
            docs.append(entry["document"])
            metas.append(meta)

        return {"ids": matched_ids, "documents": docs, "metadatas": metas}

    # Default empty response
    return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}


mock_collection.add = MagicMock(side_effect=add_side_effect)
mock_collection.get = MagicMock(side_effect=mock_get_side_effect)
mock_collection.query = MagicMock(
    return_value={
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
)
mock_collection.delete = MagicMock()
mock_collection.count = MagicMock(return_value=0)

# Mock ChromaDB module
mock_chroma = MagicMock()
mock_chroma_api = MagicMock()
mock_chroma_api_models = MagicMock()
mock_chroma_api_models_collection = MagicMock()
mock_chroma_config = MagicMock()

# Ensure imports that chromadb.ClientCreator expects are present
# Provide a FastAPI mock whose get_collection().configuration_json is an empty dict
mock_chroma_api.FastAPI.return_value.get_collection.return_value.configuration_json = {}
sys.modules["chromadb.api.fastapi"] = mock_chroma_api

# Prevent chromadb utils from downloading ONNX models in tests
sys.modules["chromadb.utils.embedding_functions"] = MagicMock()
mock_chroma.utils = MagicMock()
mock_chroma.utils.embedding_functions = MagicMock()
sys.modules["chromadb"] = mock_chroma
sys.modules["chromadb.api"] = mock_chroma_api
sys.modules["chromadb.api.models"] = mock_chroma_api_models
sys.modules["chromadb.api.models.Collection"] = mock_chroma_api_models_collection
sys.modules["chromadb.config"] = mock_chroma_config

# ============================================================================
# Set environment variables EARLY
# ============================================================================

os.environ["OPENAI_API_KEY"] = "fake-key-for-testing"
os.environ["API_KEY"] = "x-api-key"
os.environ["CHROMA_HOST"] = "localhost"
os.environ["CHROMA_PORT"] = "8500"
os.environ["CHROMA_TENANT"] = "default_tenant"
os.environ["CHROMA_DATABASE"] = "default_database"
os.environ["REDIS_URL"] = "redis://localhost:6379"

# ============================================================================
# Mock Redis before langchain imports
# ============================================================================


class MockRedis:
    def __init__(self):
        self.data = {}

    async def ping(self):
        return True

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value
        return True

    async def setex(self, key, time, value):
        self.data[key] = value
        return True

    async def delete(self, key):
        self.data.pop(key, None)
        return True

    async def rpush(self, key, value):
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)
        return len(self.data[key])

    async def lrange(self, key, start, end):
        return self.data.get(key, [])[start:end]

    async def incrby(self, key, amount=1):
        if key not in self.data:
            self.data[key] = 0
        self.data[key] += amount
        return self.data[key]

    async def expire(self, key, time):
        return True

    async def lpush(self, key, value):
        if key not in self.data:
            self.data[key] = []
        self.data[key].insert(0, value)
        return len(self.data[key])

    async def ltrim(self, key, start, end):
        if key in self.data:
            self.data[key] = self.data[key][start : end + 1]
        return True

    async def close(self):
        return True

    async def publish(self, channel, message):
        return True


mock_redis_module = MagicMock()
mock_redis_module.from_url = AsyncMock(return_value=MockRedis())
sys.modules["redis.asyncio"] = mock_redis_module
sys.modules["redis"] = MagicMock()
sys.modules["redis"].asyncio = mock_redis_module

# ============================================================================
# Mock LangChain BEFORE imports
# ============================================================================


class MockChatOpenAI:
    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, messages):
        mock_response = MagicMock()
        mock_response.content = "Test AI response"
        return mock_response

    async def ainvoke(self, messages):
        # Async version - needed for process_chat
        mock_response = MagicMock()
        mock_response.content = (
            "Test AI response - This is a quick mock response for testing purposes."
        )
        return mock_response


sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_openai"].ChatOpenAI = MockChatOpenAI
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["sentence_transformers.util"] = MagicMock()

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)

# Set event loop policy for Windows
try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except AttributeError:
    pass


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_embedding_model():
    """
    Minimal embedding model stub so autouse patch never crashes.
    Provider-agnostic: works whether you used SentenceTransformers before or not.
    """
    model = MagicMock()
    model.encode.return_value = [[0.0] * 8]
    model.embed_documents.return_value = [[0.0] * 8]
    model.embed_query.return_value = [0.0] * 8
    return model


@pytest.fixture
def mock_redis():
    """Redis mock fixture"""
    from ms_ai.app.redis_manager import redis_manager

    redis_mock = MockRedis()
    redis_manager.client = redis_mock
    yield redis_mock


@pytest.fixture
def client():
    """FastAPI test client fixture"""
    from ms_ai.app.main import app

    # Ensure verify_api_key used by routes is overridden for tests
    try:
        from ms_ai.app import dependencies

        app.dependency_overrides[dependencies.verify_api_key] = (
            lambda x_api_key=None: x_api_key or "test-key"
        )
    except Exception:
        # fallback: patch will handle it in autouse fixture
        pass

    return TestClient(app)


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for API testing"""
    from ms_ai.app.main import app

    return TestClient(app)


@pytest.fixture
def mock_chroma_client(mock_http_client):
    """Mock ChromaDB client (kept for backwards compatibility with older tests)."""
    return mock_http_client


@pytest.fixture
def interaction_manager_with_mock(mock_chroma_client):
    """UserInteractionManager with mocked ChromaDB"""
    manager = UserInteractionManager()
    manager._collection = mock_collection
    return manager


@pytest.fixture
def websocket_handler_with_mocks():
    """WebSocketHandler with mocked dependencies"""
    with patch("ms_ai.app.websocket.redis_manager"):
        handler = WebSocketHandler()
        return handler


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    mock_client = AsyncMock()
    mock_client.set = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.incr = AsyncMock()
    mock_client.rpush = AsyncMock()
    mock_client.lrange = AsyncMock()
    mock_client.publish = AsyncMock()
    mock_client.subscribe = AsyncMock()
    return mock_client


@pytest.fixture
def sample_session_id():
    """Generate a sample session ID"""
    return str(uuid4())


@pytest.fixture
def sample_user_login():
    """Generate a sample user login"""
    return "test_user_123"


@pytest.fixture
def sample_interaction_id():
    """Generate a sample interaction ID"""
    return str(uuid4())


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.receive_json = AsyncMock()
    mock_ws.disconnect = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing"""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("CHROMA_PATH", "./test_chroma_data")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    monkeypatch.setenv("API_KEY", "test-api-key-123")


@pytest.fixture
def db_session():
    """Create a database session for tests"""
    pass


# Autouse fixture: make get_embedding_model return a lightweight mock by default
@pytest.fixture(autouse=True)
def _auto_patch_embedding_model(mock_embedding_model):
    """
    Prevent real embedding model / ONNX downloads in tests that don't request mock explicitly.
    If get_embedding_model no longer exists in chat_service, patching will be skipped.
    """
    try:
        with patch(
            "ms_ai.app.chat_service.get_embedding_model",
            return_value=mock_embedding_model,
        ):
            yield
    except (AttributeError, ModuleNotFoundError):
        # chat_service has no get_embedding_model anymore (provider changed)
        yield


# Add autouse fixture to mock API key verification for tests
@pytest.fixture(autouse=True)
def _auto_mock_verify_api_key():
    """Patch verify_api_key so test HTTP calls with x-api-key succeed."""

    def verify_key(x_api_key: str = ""):
        if not x_api_key:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return x_api_key

    with patch("ms_ai.app.dependencies.verify_api_key", side_effect=verify_key):
        yield


@pytest.fixture
def interaction_manager():
    """Create a UserInteractionManager instance for testing"""
    with patch("ms_ai.app.user_interactions.get_chroma_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client

        manager = UserInteractionManager()
        manager.reset_cache()
        yield manager
        manager.reset_cache()


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "websocket: mark test as a WebSocket test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
