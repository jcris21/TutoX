from typing import Any, Dict, List, Optional, TypedDict, Literal

from pydantic import BaseModel
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o-2024-11-20",
    temperature=0,
)

FAILURE_PRIORITY = {
    "wrong_value": 10,
    "missing_value": 20,
    "wrong_label": 30,
    "wrong_field": 40,
    "wrong_field_and_value": 50,
    "missing_label": 60,
    "wrong_event_type": 70,
}


def pick_best_failure(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {
            "matched": False,
            "failure_reason": "wrong_event_type",
            "recoverable": False,
            "expected": {},
            "received": {},
            "comparison": {},
        }

    def score(result: Dict[str, Any]):
        recoverable_rank = 0 if result.get("recoverable") else 1
        reason_rank = FAILURE_PRIORITY.get(result.get("failure_reason"), 999)
        return (recoverable_rank, reason_rank)

    return sorted(results, key=score)[0]

FailureReason = Literal[
    "wrong_event_type",
    "missing_label",
    "missing_value",
    "wrong_field",
    "wrong_field_and_value",
    "wrong_label",
    "wrong_value",
    "wrong_label_and_value",
    "irrelevant_event",
]


class ExpectedAction(BaseModel):
    model: str
    action: str
    metadata: Optional[Dict[str, Any]] = None


class ExerciseStep(BaseModel):
    step_id: str
    step_order: int
    instruction: str
    expected_action: ExpectedAction
    hints: Optional[List[str]] = None
    validation_rule: Optional[Dict[str, Any]] = None


class Exercise(BaseModel):
    exercise_id: str
    module: str
    goal: str
    odoo_version: str
    steps: List[ExerciseStep]
    success_criteria: Optional[List[str]] = None
    created_at: Optional[str] = None


class ChatResponse(BaseModel):
    response: Optional[str] = None
    exercise_id: Optional[str] = None
    current_step: Optional[int] = None
    fallback: Optional[bool] = None
    interaction_id: Optional[str] = None
    timestamp: Optional[float] = None
    status: Optional[str] = None


class OdooContext(BaseModel):
    model: Optional[str] = None
    view: Optional[str] = None
    mode: Optional[str] = None


class ValidateExerciseResponse(BaseModel):
    valid: bool
    message: str
    errors: Optional[List[str]] = None


class TutorState(TypedDict):
    last_known_module: str | None
    paused: bool

    session_id: str
    message: str
    context_model: str

    lang: str

    mode: str
    exercise_id: str | None
    required_module: str | None
    current_step: int | None
    response: str | None
    detour_question: str | None

    exercise_document: str | None
    pending_exercise_id: str | None
    pending_required_module: str | None
    pending_exercise_document: str | None
    pending_goal: str | None
    pending_distance: float | None
    pending_user_msg: str | None


class ReinforceResult(TypedDict, total=False):
    success: bool
    mode: str
    response: Optional[str]
    next_step: Optional[int]

class EventComparison(TypedDict):
    type_match: bool
    label_match: bool
    value_match: bool

class DeterministicValidationResult(TypedDict):
    matched: bool
    event_type: str
    failure_reason: Optional[FailureReason]
    recoverable: Optional[bool]
    expected: Dict[str, Any]
    received: Dict[str, Any]
    comparison: EventComparison