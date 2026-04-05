from typing import Any, Dict


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def build_feedback_message(result: Dict[str, Any]) -> str:
    reason = result.get("failure_reason")
    expected = result.get("expected") or {}
    received = result.get("received") or {}

    expected_label = _to_text(expected.get("label"))
    expected_value = _to_text(expected.get("value"))
    received_label = _to_text(received.get("label"))
    received_value = _to_text(received.get("value"))

    if reason == "wrong_field":
        if received_label and expected_label:
            return (
                f"It looks like you edited '{received_label}', but we need '{expected_label}' first."
            )
        return "It looks like you changed a different field than expected."

    if reason == "wrong_label":
        return f"You clicked '{received_label}', but we need '{expected_label}'."

    if reason == "wrong_value":
        if expected_label and expected_value:
            return (
                f"You're in the right field ('{expected_label}'), but the value should be '{expected_value}'."
            )
        if expected_value:
            return f"The value should be '{expected_value}'."
        return "The value entered is not the expected one for this step."

    if reason == "wrong_field_and_value":
        if received_label and expected_label and expected_value:
            return (
                f"It seems you've entered '{received_value}' in '{received_label}'. "
                f"Please set '{expected_value}' in '{expected_label}'."
            )
        return "You edited a different field and the value also does not match this step."

    if reason == "missing_value":
        if expected_label:
            return f"Please enter a value for '{expected_label}' to continue."
        return "Please enter a value to continue."

    if reason == "missing_label":
        return "I could not identify which field was edited. Please try again on the required field."

    if reason == "wrong_event_type":
        return "That action does not match the expected step yet."

    return "That input does not match the expected step yet."