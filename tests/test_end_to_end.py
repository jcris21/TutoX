import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ms_ai.app.main import app

# Initialize FastAPI test client
client = TestClient(app)


# Fixture to mock environment variables
@pytest.fixture
def mock_env(monkeypatch):
    print("Applying mock_env")
    monkeypatch.setenv("API_KEY", "x-api-key")
    monkeypatch.setenv("CHROMA_HOST", "localhost")
    monkeypatch.setenv("CHROMA_PORT", "8500")
    monkeypatch.setenv("CHROMA_TENANT", "default_tenant")
    monkeypatch.setenv("CHROMA_DATABASE", "default_database")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-testing")


# Fixture to mock ChromaDB collection
@pytest.fixture
def mock_chroma_collection(mock_env):
    with patch("ms_ai.app.vectordb.get_chroma_collection") as mock:
        collection = MagicMock()
        collection.get.return_value = {
            "ids": ["1"],
            "metadatas": [
                {
                    "id": "1",
                    "goal": "Create a quotation in Odoo",
                    "instructions": json.dumps(
                        ["Go to Sales module", "Click New Quotation"]
                    ),
                }
            ],
            "documents": ["Create a quotation in Odoo"],
            "embeddings": [[0.1] * 384],
        }
        mock.return_value = collection
        yield mock


@pytest.fixture
def mock_sentence_transformer_util():
    # This fixture is no longer needed as util is not imported in the current code
    # Keeping it as a no-op to avoid breaking test signatures
    yield None


# Fixture to mock LLM (CORRECT MODULE)
@pytest.fixture
def mock_llm():
    with patch("ms_ai.app.chat_service.llm") as mock:
        mock.invoke.return_value = MagicMock(
            content="Mocked AI response: Create a quotation by navigating to Sales."
        )
        yield mock


# Fixture to mock verify_api_key dependency
@pytest.fixture
def mock_verify_api_key():
    print("Applying mock_verify_api_key")
    from ms_ai.app.dependencies import verify_api_key

    async def mock_dependency():
        return "x-api-key"

    app.dependency_overrides[verify_api_key] = mock_dependency
    yield
    app.dependency_overrides = {}


# -------------------------------
# TESTS
# -------------------------------


def test_end_to_end_matching_exercise(
    mock_chroma_collection,
    mock_embedding_model,
    mock_llm,
    mock_verify_api_key,
    mock_env,
    mock_sentence_transformer_util,
):
    """
    REST /chat does not exist → expect 404.
    Business logic is covered by WebSocket tests.
    """
    response = client.post(
        "/chat",
        json={
            "message": "How do I create a quotation?",
            "context": {"model": "sale.order"},
        },
        headers={"x-api-key": "x-api-key"},
    )

    assert response.status_code == 404


def test_end_to_end_no_matching_exercise(
    mock_chroma_collection,
    mock_embedding_model,
    mock_llm,
    mock_verify_api_key,
    mock_env,
    mock_sentence_transformer_util,
):
    response = client.post(
        "/chat",
        json={
            "message": "How do I create a report?",
            "context": {"model": "sale.order"},
        },
        headers={"x-api-key": "x-api-key"},
    )

    assert response.status_code == 404


def test_end_to_end_empty_message(
    mock_chroma_collection,
    mock_verify_api_key,
    mock_env,
):
    response = client.post(
        "/chat",
        json={"message": "", "context": {"model": "sale.order"}},
        headers={"x-api-key": "x-api-key"},
    )

    assert response.status_code == 404
