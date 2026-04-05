import logging
from typing import Any, Dict, List, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from ms_ai.app.models import llm

logger = logging.getLogger(__name__)


class ReinforceAgentState(TypedDict, total=False):
    # deterministic payload
    result: Dict[str, Any]
    current_step: int
    step_progress: int
    step_instruction: str
    recent_events: List[Dict[str, Any]]

    # graph working state
    system_prompt: str
    user_prompt: str
    feedback_message: str


def build_prompts_node(state: ReinforceAgentState) -> ReinforceAgentState:
    result = state.get("result", {}) or {}
    expected = result.get("expected") or {}
    received = result.get("received") or {}
    comparison = result.get("comparison") or {}

    system_prompt = """
You are a UI exercise feedback assistant.

The validation result was already computed deterministically.
You must not decide whether the user is correct or incorrect.
You must only explain the mistake and tell the user what to do next.

Rules:
- Use only the provided payload.
- Do not invent fields, labels, buttons, or values.
- Do not mention internal keys like failure_reason, comparison, expected, or received.
- Keep the answer short: maximum 2 sentences.
- Be concrete and action-oriented.
- If a field label exists, use it.
- If an expected value exists, mention it when useful.
- Do not use markdown bullets.
""".strip()

    user_prompt = f"""
Current step: {state.get("current_step")}
Step progress: {state.get("step_progress")}
Step instruction: {state.get("step_instruction", "")}

Validation result:
- failure_reason: {result.get("failure_reason")}
- recoverable: {result.get("recoverable")}
- matched: {result.get("matched")}

Expected:
{expected}

Received:
{received}

Comparison:
{comparison}

Recent events:
{state.get("recent_events", [])}

Write the feedback message for the user.
""".strip()

    return {
        **state,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }


async def generate_feedback_node(
    state: ReinforceAgentState,
) -> ReinforceAgentState:
    system_prompt = state.get("system_prompt", "")
    user_prompt = state.get("user_prompt", "")

    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )

    content = response.content
    if isinstance(content, str):
        feedback_message = content.strip()
    elif isinstance(content, list):
        feedback_message = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    else:
        feedback_message = str(content or "").strip()

    return {
        **state,
        "feedback_message": feedback_message,
    }


reinforce_graph = StateGraph(ReinforceAgentState)
reinforce_graph.add_node("build_prompts", build_prompts_node)
reinforce_graph.add_node("generate_feedback", generate_feedback_node)

reinforce_graph.set_entry_point("build_prompts")
reinforce_graph.add_edge("build_prompts", "generate_feedback")
reinforce_graph.add_edge("generate_feedback", END)

reinforce_agent = reinforce_graph.compile()


async def reinforce_entry_point(
    *,
    result: Dict[str, Any],
    current_step: int,
    step_progress: int,
    step_instruction: str = "",
    recent_events: List[Dict[str, Any]] | None = None,
) -> str:
    """
    Adapter used by reinforce flow.
    Returns only the final feedback message.
    """
    try:
        output = await reinforce_agent.ainvoke(
            {
                "result": result,
                "current_step": current_step,
                "step_progress": step_progress,
                "step_instruction": step_instruction,
                "recent_events": recent_events or [],
            }
        )
        return (output.get("feedback_message") or "").strip()
    except Exception:
        logger.exception("reinforce_entry_point failed")
        raise