import logging
from typing import Any, Dict, Optional

from .exercise_manager import exercise_manager

logger = logging.getLogger(__name__)


class InstructionService:
    """
    Service to find and prepare exercises for modification based on feedback
    """

    def find_instruction_from_feedback(
        self, exercise_id: str, step_order: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the instruction that needs to be modified based on exercise and step

        Args:
            exercise_id: The exercise ID (e.g., "ex-create-quotation")
            step_order: Current step order (1-based index)

        Returns:
            Dict with instruction details or None
        """
        try:
            if not step_order or step_order < 1:
                return None

            logger.info(
                f"Finding instruction: exercise={exercise_id}, step={step_order}"
            )

            step = exercise_manager.get_exercise_step(exercise_id, step_order)

            if not step:
                logger.error(f"Step {step_order} not found in exercise {exercise_id}")
                return None

            logger.info(f"Found step: {step.step_id}")

            return {
                "step_id": step.step_id,
                "step_order": step.step_order,
                "instruction": step.instruction,
                "expected_action": step.expected_action.model_dump(),
                "hints": step.hints,
                "exercise_id": exercise_id,
            }

        except Exception as e:
            logger.error(f"Error finding instruction: {e}", exc_info=True)
            return None

    def get_instruction_context(
        self,
        exercise_id: str,
        step_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Gets full context for a specific instruction including surrounding steps.
        Useful for AI to understand the context before modifying.

        Args:
            exercise_id: Exercise ID
            step_id: Specific step ID (e.g., "ex-create-quotation_step-002")

        Returns:
            Dict with instruction context
        """
        try:
            logger.info(
                f"Getting instruction context: exercise={exercise_id}, step_id={step_id}"
            )

            exercise = exercise_manager.get_exercise(exercise_id)
            if not exercise:
                logger.error(f"Exercise not found: {exercise_id}")
                return None

            # Find the step
            current_step = None
            current_idx = None

            for idx, step in enumerate(exercise.steps):
                if step.step_id == step_id:
                    current_step = step
                    current_idx = idx
                    break

            if not current_step:
                logger.error(f"Step {step_id} not found in exercise {exercise_id}")
                return None

            logger.info(f"Found step at index {current_idx}: {step_id}")

            # Get previous and next steps for context
            prev_step = exercise.steps[current_idx - 1] if current_idx > 0 else None
            next_step = (
                exercise.steps[current_idx + 1]
                if current_idx < len(exercise.steps) - 1
                else None
            )

            context = {
                "exercise_id": exercise_id,
                "exercise_goal": exercise.goal,
                "module": exercise.module,
                "current_step": {
                    "step_id": current_step.step_id,
                    "step_order": current_step.step_order,
                    "instruction": current_step.instruction,
                    "expected_action": current_step.expected_action.model_dump(),
                    "hints": current_step.hints,
                },
                "previous_step": (
                    {
                        "step_id": prev_step.step_id,
                        "step_order": prev_step.step_order,
                        "instruction": prev_step.instruction,
                    }
                    if prev_step
                    else None
                ),
                "next_step": (
                    {
                        "step_id": next_step.step_id,
                        "step_order": next_step.step_order,
                        "instruction": next_step.instruction,
                    }
                    if next_step
                    else None
                ),
            }

            logger.info("Context retrieved successfully")
            return context

        except Exception as e:
            logger.error(f"Error getting instruction context: {e}", exc_info=True)
            return None


# Global instance
instruction_service = InstructionService()
