import logging
from typing import Any, Dict, Optional

from ms_ai.app.exercise_manager import get_step
from ms_ai.app.redis_manager import redis_manager
from .reinforce import evaluate_reinforce

logger = logging.getLogger(__name__)

def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


async def process_ui_event(
    *,
    session_id: str,
    event: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    session = await redis_manager.get_session(session_id) or {}

    mode = session.get("mode")
    if mode != "exercise_active":
        return None

    current_step = session.get("current_step", 0)
    current_step_data = get_step(session, current_step)
    if current_step_data:
        step_progress = session.get("step_progress", 0)
        if not isinstance(step_progress, int) or step_progress < 0:
            step_progress = 0

    state = {
        **session,
        "session_id": session_id,
        "event": event,
    }

    result = await evaluate_reinforce(state, event)
    status = result.get("status")

    # Recoverable / blocking -> immediate tutor feedback
    if status in ("recoverable_error", "blocking_error"):
        if result.get("failure_reason") in ("wrong_event_type", "wrong_label", "wrong_field_and_value"):
            return None

        return {
            "kind": "feedback",
            "response": result.get("feedback_message") or "",
            "current_step": result.get("current_step"),
            "exercise_id": session.get("exercise_id"),
        }

    # Success -> persist step and push next instruction
    if status == "success":
        previous_step = session.get("current_step", 0)
        new_step = result["current_step"]
        new_step_progress = result.get("step_progress", 0)

        await redis_manager.update_session(
            session_id,
            {
                "current_step": new_step,
                "step_progress": new_step_progress,
                "mode": "exercise_active",
            },
        )

        # Step sequence still in progress; no tutor push yet.
        if new_step == previous_step:
            return None

        next_step = get_step(
            {
                **session,
                "current_step": new_step,
            },
            new_step,
        )

        if not next_step:
            await redis_manager.update_session(
                session_id,
                {
                    "mode": "idle",
                    "step_progress": 0,
                },
            )
            return {
                "kind": "feedback",
                "response": "Exercise completed.",
                "current_step": new_step,
                "exercise_id": session.get("exercise_id"),
            }

        required_module = (
            next_step.get("validation_steps", {}).get("required_module")
        )

        await redis_manager.update_session(
            session_id,
            {
                "required_module": required_module,
            },
        )

        return {
            "kind": "success",
            "response": next_step.get("instruction") or "",
            "current_step": new_step,
            "exercise_id": session.get("exercise_id"),
        }

    return None