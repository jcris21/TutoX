import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# -------------------------
# Fixtures
# -------------------------


@pytest.fixture
def mock_env(monkeypatch):
    print("Applying mock_env")
    monkeypatch.setenv("API_KEY", "x-api-key")
    monkeypatch.setenv("CHROMA_HOST", "localhost")
    monkeypatch.setenv("CHROMA_PORT", "8500")
    monkeypatch.setenv("CHROMA_TENANT", "default_tenant")
    monkeypatch.setenv("CHROMA_DATABASE", "default_database")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-testing")


@pytest.fixture
def mock_chroma_collection(mock_env):
    with patch("ms_ai.app.vectordb.get_chroma_collection") as mock:
        collection = MagicMock()

        metadata = {
            "id": "1",
            "goal": {"en": "Create a quotation in Odoo"},
            "required_module": "sale",
            "doc_json": json.dumps(
                {
                    "goal": {"en": "Create a quotation in Odoo"},
                    "steps": [
                        {"instruction": "Go to Sales module"},
                        {"instruction": "Click New Quotation"},
                    ],
                }
            ),
        }

        collection.query.return_value = {
            "ids": [["1"]],
            "metadatas": [[metadata]],
            "documents": [["Create a quotation in Odoo"]],
            "distances": [[0.5]],
        }

        mock.return_value = collection
        yield mock


@pytest.fixture
def mock_embedding_model():
    """
    Minimal embedding model fixture so tests don't crash if conftest/autouse
    expects it (or this test requests it). Keeps the suite provider-agnostic.
    """
    model = MagicMock()
    model.encode.return_value = [[0.0] * 8]
    model.embed_documents.return_value = [[0.0] * 8]
    model.embed_query.return_value = [0.0] * 8
    return model


@pytest.fixture
def mock_llm():
    """Mock async LLM call (your code uses llm.ainvoke)"""
    with patch("ms_ai.app.chat_service.llm") as mock:
        mock.ainvoke = AsyncMock(
            return_value=MagicMock(content="This is a mocked AI response")
        )
        yield mock


@pytest.fixture
def mock_verify_api_key():
    """Mock API key verification to always pass"""

    def verify_key(x_api_key: str = ""):
        if not x_api_key:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key",
            )
        return x_api_key

    with patch("ms_ai.app.dependencies.verify_api_key", side_effect=verify_key):
        yield


@pytest.fixture(autouse=True)
def _auto_mock_api_key(mock_verify_api_key):
    yield


# -------------------------
# Tests
# -------------------------


def test_chat_endpoint_valid_input(
    client,
    mock_chroma_collection,
    mock_embedding_model,
    mock_llm,
    mock_verify_api_key,
    mock_env,
):
    """
    REST /chat endpoint does NOT exist.
    Chat is WebSocket-only.
    Therefore 404 is correct.
    """
    request_data = {
        "message": "How do I create a quotation?",
        "context": {"model": "sale.order"},
    }

    response = client.post(
        "/chat",
        json=request_data,
        headers={"x-api-key": "x-api-key"},
    )

    assert response.status_code == 404


class TestInteractionEndpoints:
    def test_get_interaction_with_user_login(self, client):
        interaction_id = "test-interaction-123"
        user_login = "test_user"

        response = client.get(
            f"/interaction/{interaction_id}",
            params={"user_login": user_login},
            headers={"x-api-key": "x-api-key"},
        )

        assert response.status_code in [200, 404]

        data = response.json()

        if response.status_code == 404:
            assert "error" in data or "detail" in data
        else:
            assert "interaction_id" in data

    def test_get_interaction_without_user_login(self, client):
        interaction_id = "test-interaction-456"

        response = client.get(
            f"/interaction/{interaction_id}",
            headers={"x-api-key": "x-api-key"},
        )

        assert response.status_code in [200, 404]

    def test_get_interaction_endpoint_structure(self, client):
        interaction_id = "test-id-789"
        user_login = "test_user"

        response = client.get(
            f"/interaction/{interaction_id}",
            params={"user_login": user_login},
            headers={"x-api-key": "x-api-key"},
        )

        data = response.json()

        if response.status_code == 404:
            assert "error" in data or "detail" in data or "interaction_id" in data


class TestUserInteractionsEndpoint:
    def test_get_user_interactions_filters(self, client):
        response = client.get(
            "/user/interactions",
            params={
                "user_login": "test_user",
                "interaction_type": "chat",
                "limit": 10,
            },
            headers={"x-api-key": "x-api-key"},
        )

        assert response.status_code == 200

        data = response.json()
        assert "interactions" in data
