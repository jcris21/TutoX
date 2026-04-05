import logging
from typing import Any, Dict, List

from ms_ai.app.models import DeterministicValidationResult, pick_best_failure
from ms_ai.app.reinforce_subagent.entry_point import reinforce_entry_point
from .validators import validate_field_changed, validate_click

from  ms_ai.app.exercise_manager import get_step


logger = logging.getLogger(__name__)


def get_candidate_expected_actions(
    validation_steps: Dict[str, Any],
    step_progress: int,
) -> List[Dict[str, Any]]:
    sequence_any = validation_steps.get("sequence_any")
    if sequence_any:
        candidates = []
        for branch in sequence_any:
            if not isinstance(branch, list):
                continue
            if 0 <= step_progress < len(branch):
                candidates.append(branch[step_progress])
        return candidates

    sequence = validation_steps.get("sequence", [])
    if 0 <= step_progress < len(sequence):
        return [sequence[step_progress]]

    return []

def is_same_action(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        a.get("type") == b.get("type")
        and a.get("label") == b.get("label")
        and a.get("value") == b.get("value")
    )

async def evaluate_reinforce(
    state: Dict[str, Any],
    event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Main reinforcement evaluation:
    - gets current step
    - extracts expected action
    - validates incoming event
    - returns structured result for tutor
    """

    step_index = state.get("current_step", 0)
    logger.info(
        f"[REINFORCE] step={step_index} event={event.get('type')} label={event.get('label')}"
    )

    step = get_step(state, step_index)
    if not step:
        return {
            "status": "blocking_error",
            "current_step": step_index,
            "failure_reason": "step_not_found",
        }

    validation_steps = step.get("validation_steps", {}) or {}

    step_progress = state.get("step_progress", 0)
    if not isinstance(step_progress, int) or step_progress < 0:
        step_progress = 0

    candidate_actions = get_candidate_expected_actions(validation_steps, step_progress)

    if not candidate_actions:
        return {
            "status": "blocking_error",
            "current_step": step_index,
            "failure_reason": "no_validation_defined",
            "step_progress": step_progress,
        }

    candidate_results = []
    matched_result = None
    matched_sequence_len = None

    sequence_any = validation_steps.get("sequence_any")
    sequence = validation_steps.get("sequence", [])

    for idx, expected_action in enumerate(candidate_actions):
        result = validate_event(event, expected_action)

        if result.get("matched"):
            matched_result = result

            if sequence_any:
                for branch in sequence_any:
                    if step_progress < len(branch) and is_same_action(branch[step_progress], expected_action):
                        matched_sequence_len = len(branch)
                        break
            else:
                matched_sequence_len = len(sequence)

            break

        candidate_results.append(result)

    if matched_result:
        if matched_sequence_len is None:
            matched_sequence_len = len(sequence) if sequence else 1

        sequence_len = matched_sequence_len

        if step_progress + 1 < sequence_len:
            response = {
                "status": "success",
                "current_step": step_index,
                "step_progress": step_progress + 1,
            }
        else:
            response = {
                "status": "success",
                "current_step": step_index + 1,
                "step_progress": 0,
            }
    else:
        best_failure = pick_best_failure(candidate_results)

        response = {
            "status": "recoverable_error" if best_failure.get("recoverable") else "blocking_error",
            "current_step": step_index,
            "failure_reason": best_failure.get("failure_reason"),
            "expected": best_failure.get("expected"),
            "received": best_failure.get("received"),
            "comparison": best_failure.get("comparison"),
            "step_progress": step_progress,
        }

    logger.info(
        f"[REINFORCE RESULT] step={step_index} "
        f"status={response.get('status')} "
        f"reason={response.get('failure_reason')}"
    )

    if response["status"] in ("recoverable_error", "blocking_error"):
        response["feedback_message"] = await reinforce_entry_point(
            result=best_failure,
            current_step=step_index,
            step_progress=step_progress,
            step_instruction=step.get("instruction", ""),
            recent_events=state.get("recent_ui_events", []),
        )

    return response

def build_reinforce_response(
    result: DeterministicValidationResult,
    step_index: int,
    step_progress: int,
    sequence_len: int,
) -> Dict[str, Any]:
    # SUCCESS -> advance within sequence or move to next step.
    if result["matched"]:
        status = "success"
        if step_progress + 1 < sequence_len:
            response = {
                "status": status,
                "current_step": step_index,
                "step_progress": step_progress + 1,
            }
        else:
            response = {
                "status": status,
                "current_step": step_index + 1,
                "step_progress": 0,
            }
    elif result["recoverable"]:
        status = "recoverable_error"
        response = {
            "status": status,
            "current_step": step_index,
            "failure_reason": result["failure_reason"],
            "expected": result["expected"],
            "received": result["received"],
            "comparison": result["comparison"],
            "step_progress": step_progress,
        }
    else:
        status = "blocking_error"
        response = {
            "status": status,
            "current_step": step_index,
            "failure_reason": result["failure_reason"],
            "step_progress": step_progress,
        }

    logger.info(
        f"[REINFORCE DECISION] step={step_index} → status={status}"
    )
    return response

def _unsupported_event_result(
    event: Dict[str, Any],
    expected: Dict[str, Any],
) -> DeterministicValidationResult:
    expected_type = expected.get("type", "unknown")

    return {
        "matched": False,
        "event_type": expected_type,
        "failure_reason": "wrong_event_type",
        "recoverable": False,
        "expected": expected,
        "received": event,
        "comparison": {
            "type_match": False,
            "label_match": False,
            "value_match": False,
        },
    }


def validate_event(
    event: Dict[str, Any],
    expected: Dict[str, Any],
) -> DeterministicValidationResult:
    """
    Dispatch deterministic validation based on the expected event type.
    """ 

    expected_type = expected.get("type")

    validators = {
        "field_changed": validate_field_changed,
        "button_clicked": validate_click,
        "tab_changed": validate_click,
        "link_clicked": validate_click,
    }

    validator = validators.get(expected_type)

    if not validator:
        return _unsupported_event_result(event, expected)

    return validator(event, expected)