import asyncio
import json
import logging
import time
from typing import Dict, Optional
from uuid import uuid4

from fastapi import WebSocket

from .chat_service import process_chat
from .exercise_manager import get_exercise
from .redis_manager import redis_manager
from .user_interactions import user_interaction_manager
from ms_ai.app.reinforce_subagent.ui_event_processor import process_ui_event

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and sessions"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(
        self, websocket: WebSocket, session_id: Optional[str] = None
    ) -> str:
        """Establishes WebSocket connection and returns session ID"""
        await websocket.accept()

        if not session_id:
            session_id = str(uuid4())

        self.active_connections[session_id] = websocket
        logger.info(f"New connection established: {session_id}")
        return session_id

    async def disconnect(self, session_id: str):
        """Removes connection and cleans up session data"""
        if session_id in self.active_connections:
            self.active_connections.pop(session_id)
            logger.info(f"Connection closed: {session_id}")

    def get_active_sessions_count(self) -> int:
        """Returns count of active connections"""
        return len(self.active_connections)

    async def send_message(self, session_id: str, message: dict):
        """Sends message to specific session"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {str(e)}")
                await self.disconnect(session_id)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Broadcasts message to all connections except excluded session"""
        for session_id, websocket in self.active_connections.items():
            if session_id != exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {session_id}: {str(e)}")
                    await self.disconnect(session_id)


class WebSocketHandler:
    """Handles WebSocket message processing and routing"""

    def __init__(self):
        self.connection_manager = ConnectionManager()

    async def initialize(self):
        """Ensure Redis is connected"""
        if not redis_manager.client:
            await redis_manager.connect()

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
        user_login: Optional[str] = None,
        db: Optional[str] = None,
    ):
        """
        Handles new WebSocket connection.

        Args:
            websocket: WebSocket connection object
            session_id: Optional session ID (generated if not provided)
            user_login: Odoo username (IMPORTANT for user segmentation)
            db: Database name
        """
        await self.initialize()
        session_id = await self.connection_manager.connect(websocket, session_id)

        try:
            # Store session data in Redis with user_login
            await redis_manager.store_session(
                session_id,
                {
                    "user_login": user_login,
                    "db": db,
                    "connected_at": time.time(),
                },
            )

            # Send connection confirmation
            await websocket.send_json(
                {
                    "type": "connection_established",
                    "session_id": session_id,
                    "user_login": user_login,
                    "timestamp": time.time(),
                }
            )

            # Message processing loop
            while True:
                raw = None
                try:
                    raw = await websocket.receive_text()

                    if not raw or raw.strip() == "":
                        continue

                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Invalid JSON format",
                                "timestamp": time.time(),
                            }
                        )
                        continue

                    msg_type = message.get("type")

                    #  Log structured payload after parsing
                    if msg_type in ("context_update", "live_context"):
                        logger.info(
                            f"[CTX RAW] session={session_id} "
                            f"context_model={message.get('context_model')} | "
                            f"context.model={message.get('context', {}).get('model')} | "
                            f"full_keys={list(message.keys())}"
                        )
                    else:
                        logger.info(
                            f"[WS IN] session={session_id} type={msg_type} keys={list(message.keys())}"
                        )

                    response = None

                    if msg_type == "chat":
                        response = await self.handle_chat_message(
                            session_id, user_login, message
                        )

                    elif msg_type == "feedback_event":
                        response = await self.handle_feedback_event(
                            session_id, user_login, message
                        )

                    elif msg_type == "ui_event":
                        response = await self.handle_ui_event(
                            session_id, user_login, message
                        )

                    elif msg_type in ("context_update", "live_context"):
                        response = await self.handle_context_event(
                            session_id, user_login, message
                        )

                    else:
                        response = {
                            "type": "error",
                            "message": "Unknown message type",
                            "timestamp": time.time(),
                        }

                    if response is not None:
                        await websocket.send_json(response)

                except json.JSONDecodeError:
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Invalid JSON format",
                                "timestamp": time.time(),
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to send error response: {e}")

                except Exception as e:
                    logger.error(
                        f"Unexpected error in message loop: {str(e)}", exc_info=True
                    )
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Server error processing message",
                                "timestamp": time.time(),
                            }
                        )
                    except Exception:
                        break

        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            await self.connection_manager.disconnect(session_id)
            await redis_manager.delete_session(session_id)

    async def handle_chat_message(
        self, session_id: str, user_login: str, message: dict
    ) -> dict:
        """
        Handle chat message and generate response using chat_service
        """
        try:
            message_text = message.get("message", "")
            context = message.get("context", {})
            context_model = (
                message.get("model")
                or message.get("context", {}).get("model")
                or "unknown"
            )

            # Validate that message is not empty
            if not message_text or not message_text.strip():
                return {
                    "type": "error",
                    "message": "Message cannot be empty",
                    "timestamp": time.time(),
                }

            logger.info(f"Chat message from {user_login}: {message_text[:50]}...")

            # Process chat using chat_service
            chat_response = await process_chat(
                session_id=session_id,
                message=message_text,
                context_model=context_model,
            )

            # Generate interaction_id
            interaction_id = None
            try:
                interaction_id = user_interaction_manager.save_user_interaction(
                    user_login=user_login,
                    session_id=session_id,
                    interaction_type="chat",
                    event_data={"context": context},
                    message_text=message_text,
                )
            except Exception as e:
                logger.error(f"Failed to save interaction: {e}")

            # Build response with all fields
            response = {
                "type": "chat_response_complete",
                "response": chat_response.response,
                "exercise_id": chat_response.exercise_id,
                "current_step": chat_response.current_step,
                "fallback": chat_response.fallback,
                "interaction_id": interaction_id,
                "timestamp": time.time(),
                "status": chat_response.status or "complete",
            }

            logger.info(
                f"Chat response prepared: exercise_id={chat_response.exercise_id}, current_step={chat_response.current_step}"
            )

            return response

        except Exception as e:
            logger.error(f"Error handling chat message: {e}", exc_info=True)
            return {
                "type": "error",
                "message": f"Error processing chat: {str(e)}",
                "timestamp": time.time(),
            }

    async def _process_chat_in_background(
        self,
        session_id: str,
        user_message: str,
        interaction_id: str,
        message: dict,
    ):
        """Process the chat in background and send result when ready"""
        try:
            # Extract context model properly
            context_model = (
                message.get("model")
                or message.get("context", {}).get("model")
                or "unknown"
            )

            response = await process_chat(
                session_id=session_id,
                message=user_message,
                context_model=context_model,
            )

            await self.connection_manager.send_message(
                session_id,
                {
                    "type": "chat_response_complete",
                    "response": response.response,
                    "exercise_id": response.exercise_id,
                    "fallback": response.fallback,
                    "interaction_id": interaction_id,
                    "timestamp": time.time(),
                    "status": "complete",
                },
            )

            logger.info(
                f"Chat processing completed: session={session_id}, interaction_id={interaction_id}"
            )

        except Exception as e:
            logger.error(f"Error in background chat processing: {str(e)}")
            await self.connection_manager.send_message(
                session_id,
                {
                    "type": "error",
                    "message": "Failed to process chat message",
                    "interaction_id": interaction_id,
                    "timestamp": time.time(),
                },
            )

    async def handle_feedback_event(
        self, session_id: str, user_login: str, message: dict
    ) -> dict:
        """
        Process feedback events from users.
        Always generates interaction_id.
        interaction_type must be "feedback_event".
        Finds and prepares the instruction for modification.
        """
        try:
            event_name = message.get("event_name")
            event_data = message.get("event_data", {})
            message_text = event_data.get("message_body_text", "")

            # 1. Get current exercise and step from session
            session = await redis_manager.get_session(session_id) or {}
            exercise_id = session.get("exercise_id")
            current_step = session.get("current_step", 0)

            logger.info(
                f"Feedback Event - Exercise: {exercise_id}, Step: {current_step}, Type: {event_name}"
            )

            #  Save feedback to ChromaDB
            interaction_id = None
            try:
                interaction_id = user_interaction_manager.save_user_interaction(
                    user_login=user_login,
                    session_id=session_id,
                    interaction_type="feedback_event",
                    event_data=message,
                    message_text=message_text,
                )
                logger.info(
                    f"Feedback interaction saved: user={user_login}, id={interaction_id}"
                )
            except Exception as e:
                logger.error(f"Failed to save feedback interaction: {e}")
                return {
                    "type": "error",
                    "message": "Failed to save feedback",
                    "error": str(e),
                    "timestamp": time.time(),
                }

            if not interaction_id:
                logger.error("interaction_id was not generated for feedback event")
                return {
                    "type": "error",
                    "message": "Failed to generate interaction ID",
                    "timestamp": time.time(),
                }

            # Store in Redis
            await redis_manager.push_message(
                session_id,
                {
                    "type": "feedback_event",
                    "event_name": event_name,
                    "timestamp": time.time(),
                    "interaction_id": interaction_id,
                },
            )

            # Find the instruction that needs modification
            instruction_context = None
            instruction_found = False

            if (
                exercise_id
                and current_step > 0
                and event_name
                in [
                    "ai_feedback_unclear",
                    "ai_feedback_technical_issue",
                ]
            ):
                logger.info(
                    f"Searching for instruction: exercise={exercise_id}, step={current_step}"
                )

                try:
                    step = get_exercise(exercise_id)

                    if step:
                        step_id = step.step_id
                        logger.info(f"Found step_id: {step_id}")

                        # Get instruction context using instruction_service
                        from .instruction_service import instruction_service

                        instruction_context = (
                            instruction_service.get_instruction_context(
                                exercise_id=exercise_id,
                                step_id=step_id,
                            )
                        )

                        if instruction_context:
                            instruction_found = True
                            logger.info(
                                f"Found instruction for feedback: step={step_id}, "
                                f"event={event_name}"
                            )

                            # Send to background processing for AI modification
                            asyncio.create_task(
                                self._process_feedback_modification(
                                    session_id=session_id,
                                    exercise_id=exercise_id,
                                    interaction_id=interaction_id,
                                    event_name=event_name,
                                    feedback_text=message_text,
                                    instruction_context=instruction_context,
                                )
                            )

                except Exception as e:
                    logger.error(f"Error finding instruction: {e}", exc_info=True)

            return {
                "type": "feedback_acknowledged",
                "event_name": event_name,
                "interaction_id": interaction_id,
                "instruction_found": instruction_found,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}", exc_info=True)
            return {
                "type": "error",
                "message": "Failed to save feedback",
                "timestamp": time.time(),
            }

    async def _process_feedback_modification(
        self,
        session_id: str,
        exercise_id: str,
        interaction_id: str,
        event_name: str,
        feedback_text: str,
        instruction_context: dict,
    ):
        """
        Background processing: Find instruction and prepare for modification
        (Actual modification will be done in next phase)
        """
        try:
            current_step_info = instruction_context.get("current_step", {})

            logger.info(
                f"Processing feedback modification:\n"
                f"  Exercise: {exercise_id}\n"
                f"  Step ID: {current_step_info.get('step_id')}\n"
                f"  Feedback Type: {event_name}\n"
                f"  Comment: {feedback_text}"
            )

            # Send response to client indicating instruction was found
            await self.connection_manager.send_message(
                session_id,
                {
                    "type": "instruction_modification_initiated",
                    "interaction_id": interaction_id,
                    "step_id": current_step_info.get("step_id"),
                    "status": "processing",
                    "message": f"Processing {event_name}. Your feedback will be used to improve this instruction.",
                    "timestamp": time.time(),
                },
            )

            logger.info(
                f"Feedback modification pipeline initiated: interaction_id={interaction_id}"
            )

        except Exception as e:
            logger.error(
                f"Error in feedback modification pipeline: {str(e)}", exc_info=True
            )
            await self.connection_manager.send_message(
                session_id,
                {
                    "type": "error",
                    "message": "Failed to process instruction modification",
                    "interaction_id": interaction_id,
                    "timestamp": time.time(),
                },
            )

    async def handle_ui_event(
    self, session_id: str, user_login: str, message: dict
) -> dict:
        try:
    

            event_name = message.get("event_name")
            raw_event = message.get("event_data", {})

            def normalize_value(value):
                if value is None:
                    return None
                try:
                    num = float(value)
                    if num.is_integer():
                        return str(int(num))
                    return str(num)
                except Exception:
                    return str(value)

            normalized_event = {
                "type": raw_event.get("type"),
                "label": raw_event.get("label"),
                "field": raw_event.get("field"),
                "value": normalize_value(raw_event.get("value")),
                "meta": raw_event.get("meta"),
                "event_name": event_name,
            }

            interaction_id = None
            try:
                interaction_id = user_interaction_manager.save_user_interaction(
                    user_login=user_login,
                    session_id=session_id,
                    interaction_type="ui_event",
                    event_data=message,
                )
                logger.info(
                    f"UI event interaction saved: user={user_login}, id={interaction_id}, type=ui_event"
                )
            except Exception as e:
                logger.error(f"Failed to save UI event interaction: {e}")
                return {
                    "type": "error",
                    "message": "Failed to save UI event",
                    "error": str(e),
                    "timestamp": time.time(),
                }

            if not interaction_id:
                # Do not block tutor flow if interaction persistence fails.
                interaction_id = str(uuid4())
                logger.warning(
                    "UI event interaction ID missing after save; using fallback ID",
                    extra={"session_id": session_id, "user_login": user_login},
                )

            await redis_manager.push_message(
                session_id,
                {
                    "type": "ui_event",
                    "event_name": event_name,
                    "event_data": normalized_event,
                    "timestamp": time.time(),
                    "interaction_id": interaction_id,
                },
            )

            ui_result = await process_ui_event(
                session_id=session_id,
                event=normalized_event,
            )

            if ui_result and ui_result.get("response"):
                return {
                    "type": "tutor_push",
                    "response": ui_result["response"],
                    "exercise_id": ui_result.get("exercise_id"),
                    "current_step": ui_result.get("current_step"),
                    "interaction_id": interaction_id,
                    "timestamp": time.time(),
                }

            return {
                "type": "ui_event_acknowledged",
                "event_name": event_name,
                "interaction_id": interaction_id,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Error processing UI event: {str(e)}", exc_info=True)
            return {
                "type": "error",
                "message": "Failed to process UI event",
                "timestamp": time.time(),
            }
        
    async def handle_context_event(
        self, session_id: str, user_login: str, message: dict
    ) -> Optional[dict]:
        """Handle context change events (view navigation, module switches, etc.)"""

        # Log incoming structure
        logger.info(
            f"[WS IN] type={message.get('type')} "
            f"keys={list(message.keys())} "
            f"context_model={message.get('context_model')} "
            f"context.model={message.get('context', {}).get('model')}"
        )

        # Extract context_model robustly (supports all payload variants)
        context_model = (
            message.get("context_model")
            or message.get("model")
            or message.get("context", {}).get("model")
            or "unknown"
        )

        event_type = message.get("event_type")

        # Store context in Redis session
        await redis_manager.update_session(
            session_id,
            {
                "context_model": context_model,
                "context": {"model": context_model},
                "last_context_update": time.time(),
            },
        )

        logger.info(
            f"[CTX_EVENT] session={session_id} user={user_login} "
            f"event_type={event_type} model={context_model}"
        )

        # Trigger tutor graph with context-only call
        try:
            session = await redis_manager.get_session(session_id) or {}
            mode = session.get("mode")

            # Only trigger tutor when waiting for module
            if mode != "module_gate":
                return {
                    "type": "context_event_acknowledged",
                    "event_type": event_type,
                    "context_model": context_model,
                    "timestamp": time.time(),
                }

            chat_response = await process_chat(
                session_id=session_id,
                message="",
                context_model=context_model,
            )
        except Exception as e:
            logger.error(f"Error processing context event: {str(e)}", exc_info=True)
            return {
                "type": "error",
                "message": "Failed to process context change",
                "timestamp": time.time(),
            }

        # If tutor produced a push message (e.g. start first step)
        if chat_response.response:
            logger.info(
                f"Tutor push triggered by context change: exercise={chat_response.exercise_id}"
            )
            return {
                "type": "tutor_push",
                "response": chat_response.response,
                "exercise_id": chat_response.exercise_id,
                "current_step": getattr(chat_response, "current_step", None),
                "fallback": chat_response.fallback,
                "timestamp": time.time(),
            }

        # Otherwise just acknowledge context update
        return {
            "type": "context_event_acknowledged",
            "event_type": event_type,
            "context_model": context_model,
            "timestamp": time.time(),
        }


# Global instances
websocket_handler = WebSocketHandler()
connection_manager = ConnectionManager()
