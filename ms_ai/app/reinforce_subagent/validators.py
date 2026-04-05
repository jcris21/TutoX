from typing import Dict, Any
from ms_ai.app.models import DeterministicValidationResult


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def validate_field_changed(
    event: Dict[str, Any],
    expected: Dict[str, Any],
) -> DeterministicValidationResult:

    received_type = event.get("type")
    received_label = event.get("label")
    received_value = event.get("value")

    expected_type = expected.get("type")
    expected_label = expected.get("label")
    expected_value = expected.get("value")
    expected_has_value = "value" in expected

    type_match = received_type == expected_type
    label_match = _normalize_text(received_label) == _normalize_text(expected_label)
    value_match = (
        str(received_value) == str(expected_value)
        if expected_has_value
        else True
    )

    # 1. Wrong event type -> not recoverable
    if not type_match:
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

    # 2. Missing label -> not recoverable (bad frontend payload)
    if received_label is None:
        return {
            "matched": False,
            "event_type": expected_type,
            "failure_reason": "missing_label",
            "recoverable": False,
            "expected": expected,
            "received": event,
            "comparison": {
                "type_match": True,
                "label_match": False,
                "value_match": value_match,
            },
        }

    # 3. Missing value -> recoverable
    if expected_has_value and received_value is None:
        return {
            "matched": False,
            "event_type": expected_type,
            "failure_reason": "missing_value",
            "recoverable": True,
            "expected": expected,
            "received": event,
            "comparison": {
                "type_match": True,
                "label_match": label_match,
                "value_match": False,
            },
        }

    # 4. Perfect match
    if label_match and value_match:
        return {
            "matched": True,
            "event_type": expected_type,
            "failure_reason": None,
            "recoverable": None,
            "expected": expected,
            "received": event,
            "comparison": {
                "type_match": True,
                "label_match": True,
                "value_match": True,
            },
        }

    # 5. Wrong field and wrong value
    if not label_match and not value_match:
        return {
            "matched": False,
            "event_type": expected_type,
            "failure_reason": "wrong_field_and_value",
            "recoverable": True,
            "expected": expected,
            "received": event,
            "comparison": {
                "type_match": True,
                "label_match": False,
                "value_match": False,
            },
        }

    # 6. Wrong field only
    if not label_match and value_match:
        return {
            "matched": False,
            "event_type": expected_type,
            "failure_reason": "wrong_field",
            "recoverable": True,
            "expected": expected,
            "received": event,
            "comparison": {
                "type_match": True,
                "label_match": False,
                "value_match": True,
            },
        }

    # 7. Wrong value only
    if label_match and not value_match:
        return {
            "matched": False,
            "event_type": expected_type,
            "failure_reason": "wrong_value",
            "recoverable": True,
            "expected": expected,
            "received": event,
            "comparison": {
                "type_match": True,
                "label_match": True,
                "value_match": False,
            },
        }

    # 8. Fallback for unmatched combinations
    return {
        "matched": False,
        "event_type": expected_type,
        "failure_reason": "wrong_field_and_value" if not label_match else "wrong_value",
        "recoverable": True,
        "expected": expected,
        "received": event,
        "comparison": {
            "type_match": True,
            "label_match": label_match,
            "value_match": value_match,
        },
    }


def validate_click(event, expected):
    received_type = event.get("type")
    received_label = event.get("label")

    expected_type = expected.get("type")
    expected_label = expected.get("label")

    type_match = received_type == expected_type
    label_match = _normalize_text(received_label) == _normalize_text(expected_label)

    if not type_match:
        return {
            "matched": False,
            "failure_reason": "wrong_event_type",
            "recoverable": False,
            "expected": expected,
            "received": event,
        }

    if received_label is None:
        return {
            "matched": False,
            "failure_reason": "missing_label",
            "recoverable": False,
            "expected": expected,
            "received": event,
        }

    if label_match:
        return {
            "matched": True,
            "failure_reason": None,
            "recoverable": None,
            "expected": expected,
            "received": event,
        }

    return {
        "matched": False,
        "failure_reason": "wrong_label",
        "recoverable": True,
        "expected": expected,
        "received": event,
    }