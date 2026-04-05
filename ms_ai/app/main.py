import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import verify_api_key
from .redis_manager import redis_manager
from .session_manager import connection_manager
from .websocket import websocket_handler

# Load environment variables
load_dotenv(find_dotenv())

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    try:
        # Initialize Redis on startup
        await redis_manager.connect()
        yield
    finally:
        # Cleanup on shutdown
        if redis_manager.client:
            await redis_manager.disconnect()


# Customised FastAPI app metadata
app = FastAPI(
    title="Odoo AI Tutor – AI Microservice",
    description="Provides AI chat interactions powered by GPT for the Odoo learning environment with WebSocket support.",
    version="2.0.0",
    docs_url="/api-docs",
    redoc_url="/api-redoc",
    openapi_url="/api-schema.json",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Healt check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check"""
    redis_status = "connected"
    try:
        await redis_manager.client.ping()
    except Exception:
        redis_status = "disconnected"

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis": redis_status,
        "active_websockets": connection_manager.get_active_sessions_count(),
        "llm_model": "gpt-4o-2024-11-20",
    }


# test purposes root endpoint
@app.get("/", tags=["Health"])
def read_root():
    return {
        "message": "AI Service is running",
        "version": "2.0.0",
        "websocket_enabled": True,
        "active_connections": connection_manager.get_active_sessions_count(),
    }


#  WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None),
    user_login: Optional[str] = Query(None),
    db: Optional[str] = Query(None),
):
    """WebSocket endpoint for real-time bidirectional communication.

    Query parameters:
    - session_id: Optional session ID (generated if not provided)
    - user_login: User login name
    - db: Database name

    Supported message types:
    1. Chat Message: {"type": "chat", "message": "...", "context": {"model": "sale.order"}}
    2. UI Event: {"type": "ui_event", "event_name": "button_click", "event_data": {...}}
    3. Context Update: {"type": "context_update", "context": {...}}
    """
    await websocket_handler.handle_connection(
        websocket, session_id=session_id, user_login=user_login, db=db
    )


#  Monitoring Endpoints
@app.get("/stats", tags=["Monitoring"])
async def get_stats():
    """Get system statistics"""
    return {
        "active_connections": connection_manager.get_active_sessions_count(),
        "total_messages_processed": await redis_manager.get_counter("total_messages"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# User Interactions Endpoints
@app.get("/user/interactions", tags=["User Analytics"])
async def get_user_interactions(
    user_login: str = Query(...),
    interaction_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    auth: str = Depends(verify_api_key),
):
    """
    Retrieve interactions for a specific user.

    Query Parameters:
    - user_login: Odoo username (required)
    - interaction_type: Optional filter (chat, feedback_event, ui_event)
    - limit: Max number of results (1-500)

    Returns:
    - List of interactions with metadata

    Useful for:
    - Session history
    - User behavior analysis
    - Context retrieval for RAG
    """
    try:
        from .user_interactions import user_interaction_manager

        interactions = user_interaction_manager.get_user_interactions(
            user_login=user_login,
            interaction_type=interaction_type,
            n_results=limit,
        )

        return {
            "user_login": user_login,
            "interaction_type": interaction_type,
            "total": len(interactions),
            "interactions": interactions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving user interactions: {e}")
        return {
            "error": str(e),
            "user_login": user_login,
            "interactions": [],
        }


# Session Interactions Endpoints
@app.get("/session/{session_id}/interactions", tags=["User Analytics"])
async def get_session_interactions(
    session_id: str,
    user_login: str = Query(...),
    auth: str = Depends(verify_api_key),
):
    """
    Retrieve all interactions from a specific session.

    Query Parameters:
    - user_login: Odoo username (required, for segmentation)

    Returns:
    - All interactions in the session

    Useful for:
    - Complete session replay
    - Session analysis
    """
    try:
        from .user_interactions import user_interaction_manager

        interactions = user_interaction_manager.get_session_interactions(
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "user_login": user_login,
            "total": len(interactions),
            "interactions": interactions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving session interactions: {e}")
        return {
            "error": str(e),
            "interactions": [],
        }


# Endpoint for semantic search over user interactions
@app.post("/user/interactions/search", tags=["User Analytics"])
async def search_user_interactions(
    user_login: str = Query(...),
    query: str = Query(...),
    n_results: int = Query(10, ge=1, le=100),
    auth: str = Depends(verify_api_key),
):
    """
    Semantic search over user interactions (RAG).

    Query Parameters:
    - user_login: Odoo username (required)
    - query: Search query string (required)
    - n_results: Number of results (1-100)

    Returns:
    - List of relevant interactions with similarity scores

    Useful for:
    - Finding relevant context (RAG)
    - Pattern analysis
    - Similar feedback discovery
    """
    try:
        from .user_interactions import user_interaction_manager

        results = user_interaction_manager.search_interactions(
            user_login=user_login,
            query=query,
            n_results=n_results,
        )

        return {
            "user_login": user_login,
            "query": query,
            "total": len(results),
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error searching interactions: {e}")
        return {
            "error": str(e),
            "results": [],
        }


# Endpoint to get a single interaction by ID
@app.get("/interaction/{interaction_id}", tags=["User Analytics"])
async def get_interaction(
    interaction_id: str,
    user_login: Optional[str] = Query(None),
    auth: str = Depends(verify_api_key),
):
    """
    Retrieve a specific interaction by ID.

    Query Parameters:
    - user_login: Optional - filter by user (recommended for security)

    Returns:
    - Interaction data with metadata
    """
    try:
        from .user_interactions import user_interaction_manager

        interaction = user_interaction_manager.get_interaction_by_id(
            interaction_id=interaction_id,
            user_login=user_login,
        )

        if not interaction:
            return {
                "error": "Interaction not found",
                "interaction_id": interaction_id,
            }

        return {
            "interaction_id": interaction_id,
            "data": interaction,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving interaction: {e}")
        return {
            "error": str(e),
        }


# Delete user interactions endpoint
@app.delete("/user/{user_login}/interactions", tags=["User Analytics"])
async def delete_user_interactions(
    user_login: str,
    auth: str = Depends(verify_api_key),
):
    """
    Delete all interactions for a user (GDPR compliance).

    Args:
    - user_login: Odoo username

    Returns:
    - Number of deleted interactions
    """
    try:
        from .user_interactions import user_interaction_manager

        deleted_count = user_interaction_manager.delete_user_interactions(user_login)

        return {
            "user_login": user_login,
            "deleted_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} interactions",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error deleting user interactions: {e}")
        return {
            "error": str(e),
            "user_login": user_login,
        }


@app.get("/exercise/{exercise_id}/step/{step_order}", tags=["Exercises"])
async def get_exercise_step(
    exercise_id: str,
    step_order: int,
    auth: str = Depends(verify_api_key),
):
    """
    Get a specific step from an exercise.

    Args:
    - exercise_id: Exercise ID (e.g., "ex-create-quotation")
    - step_order: Step order (1-based)

    Returns:
    - Step details with instruction and expected action
    """
    try:
        from .instruction_service import instruction_service

        step_info = instruction_service.find_instruction_from_feedback(
            exercise_id=exercise_id,
            step_order=step_order,
        )

        if not step_info:
            return {
                "error": "Step not found",
                "exercise_id": exercise_id,
                "step_order": step_order,
            }

        return {
            "exercise_id": exercise_id,
            "step": step_info,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving step: {e}")
        return {"error": str(e)}


@app.get("/exercise/{exercise_id}/step-context/{step_id}", tags=["Exercises"])
async def get_step_context(
    exercise_id: str,
    step_id: str,
    auth: str = Depends(verify_api_key),
):
    """
    Get instruction context (current + previous + next steps).
    Useful for feedback processing and AI modification.

    Args:
    - exercise_id: Exercise ID
    - step_id: Step ID (e.g., "ex-create-quotation_step-001")

    Returns:
    - Complete instruction context
    """
    try:
        from .instruction_service import instruction_service

        context = instruction_service.get_instruction_context(
            exercise_id=exercise_id,
            step_id=step_id,
        )

        if not context:
            return {
                "error": "Instruction context not found",
                "exercise_id": exercise_id,
                "step_id": step_id,
            }

        return {
            "exercise_id": exercise_id,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving step context: {e}")
        return {"error": str(e)}


@app.post("/test/create-exercise", tags=["Testing"])
async def create_test_exercise(auth: str = Depends(verify_api_key)):
    """
    Create a test exercise with proper step structure.
    Only for testing purposes.
    """
    try:
        from datetime import datetime

        from .exercise_manager import exercise_manager
        from .models import Exercise, ExerciseStep, ExpectedAction

        test_exercise = Exercise(
            exercise_id="ex-create-quotation",
            module="sales",
            goal="Learn how to create a sales quotation from scratch for a new B2B customer.",
            odoo_version="18",
            steps=[
                ExerciseStep(
                    step_id="ex-create-quotation_step-001",
                    step_order=1,
                    instruction="Go to **Sales > Quotations**. Click **New**.",
                    expected_action=ExpectedAction(
                        model="sale.order",
                        action="create",
                        metadata={"view_type": "form"},
                    ),
                    hints=["You can access Sales from the main menu."],
                ),
                ExerciseStep(
                    step_id="ex-create-quotation_step-002",
                    step_order=2,
                    instruction="Create a new customer named **Company**.",
                    expected_action=ExpectedAction(
                        model="res.partner",
                        action="create",
                    ),
                    hints=["Click on the customer field and select 'Create and Edit'."],
                ),
                ExerciseStep(
                    step_id="ex-create-quotation_step-003",
                    step_order=3,
                    instruction="Add the following products: Consulting Hours (10 units at $20/unit), Hosting Service (1 unit at $50/unit)",
                    expected_action=ExpectedAction(
                        model="sale.order.line",
                        action="create",
                    ),
                    hints=["Use the 'Add a line' button in the order lines section."],
                ),
                ExerciseStep(
                    step_id="ex-create-quotation_step-004",
                    step_order=4,
                    instruction="Apply a 10% discount to the total order.",
                    expected_action=ExpectedAction(
                        model="sale.order",
                        action="write",
                    ),
                    hints=["Look for the Discount field near the total amount."],
                ),
                ExerciseStep(
                    step_id="ex-create-quotation_step-005",
                    step_order=5,
                    instruction="Save the quotation.",
                    expected_action=ExpectedAction(
                        model="sale.order",
                        action="write",
                    ),
                    hints=["Click the Save button or use Ctrl+S."],
                ),
            ],
            success_criteria=[
                "A draft quotation exists for **Company** with the specified products and a 10% discount.",
            ],
            created_at=datetime.utcnow().isoformat(),
        )

        exercise_manager.save_exercise(test_exercise)

        return {
            "message": "✅ Test exercise created successfully",
            "exercise_id": test_exercise.exercise_id,
            "steps": len(test_exercise.steps),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error creating test exercise: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/user/interactions/search")
async def search_user_interactions_endpoint(
    query: str,
    user_login: Optional[str] = None,
    interaction_type: Optional[str] = None,
    limit: int = 5,
):
    """
    Semantic search over user interactions.

    Query Parameters:
    - query: Search query (required)
    - user_login: Optional filter by user
    - interaction_type: Optional filter by type
    - limit: Number of results (default: 5)
    """
    try:
        logger.info(
            f"Searching interactions: query='{query}', "
            f"user={user_login}, type={interaction_type}, limit={limit}"
        )

        # Import the manager used for searching interactions
        from .user_interactions import user_interaction_manager

        results = user_interaction_manager.search_interactions(
            query=query,
            user_login=user_login,
            interaction_type=interaction_type,
            n_results=limit,
        )

        logger.info(f"Found {len(results)} matching interactions")

        return {
            "query": query,
            "total": len(results),
            "interactions": results,
        }

    except Exception as e:
        logger.error(f"Error searching interactions: {e}", exc_info=True)
        return {
            "error": str(e),
            "query": query,
            "interactions": [],
        }


@app.get("/session/interactions")
async def get_session_interactions_endpoint(
    session_id: str,
    limit: int = 50,
):
    """
    Get all interactions for a specific session.

    Query Parameters:
    - session_id: ID of the session (required)
    - limit: Number of results to return (default: 50)
    """
    try:
        logger.info(
            f"Getting session interactions: session_id={session_id}, limit={limit}"
        )

        # Import the manager used to fetch session interactions
        from .user_interactions import user_interaction_manager

        interactions = user_interaction_manager.get_session_interactions(
            session_id=session_id,
            n_results=limit,
        )

        logger.info(f"Retrieved {len(interactions)} interactions for session")

        return {
            "session_id": session_id,
            "total": len(interactions),
            "interactions": interactions,
        }

    except Exception as e:
        logger.error(f"Error retrieving session interactions: {e}", exc_info=True)
        return {
            "error": str(e),
            "session_id": session_id,
            "interactions": [],
        }
