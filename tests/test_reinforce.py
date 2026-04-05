import json
import pytest

from ms_ai.app.reinforce_subagent.reinforce import evaluate_reinforce, validate_event, get_candidate_expected_actions
from ms_ai.app.reinforce_subagent.ui_event_processor import process_ui_event


# -----------------------------
# UNIT TESTS → VALIDATOR
# -----------------------------

def test_field_changed_success():
    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    expected = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = validate_event(event, expected)

    assert result["matched"] is True
    assert result["comparison"]["type_match"] is True
    assert result["comparison"]["label_match"] is True
    assert result["comparison"]["value_match"] is True


def test_field_changed_wrong_value():
    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "Mike",
    }

    expected = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = validate_event(event, expected)

    assert result["matched"] is False
    assert result["recoverable"] is True
    assert result["failure_reason"] == "wrong_value"


def test_field_changed_wrong_type_blocking():
    event = {
        "type": "button_clicked",
        "label": "Name",
        "value": "John",
    }

    expected = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = validate_event(event, expected)

    assert result["matched"] is False
    assert result["recoverable"] is False
    assert result["failure_reason"] == "wrong_event_type"


def test_field_changed_wrong_field_and_value_recoverable():
    event = {
        "type": "field_changed",
        "label": "Email",
        "value": "john@example.com",
    }

    expected = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = validate_event(event, expected)

    assert result["matched"] is False
    assert result["failure_reason"] == "wrong_field_and_value"
    assert result["recoverable"] is True
    assert result["comparison"]["type_match"] is True
    assert result["comparison"]["label_match"] is False
    assert result["comparison"]["value_match"] is False


def test_field_changed_wrong_field_recoverable():
    event = {
        "type": "field_changed",
        "label": "MAX",
        "value": "10",
    }

    expected = {
        "type": "field_changed",
        "label": "MIN",
        "value": "10",
    }

    result = validate_event(event, expected)

    assert result["matched"] is False
    assert result["failure_reason"] == "wrong_field"
    assert result["recoverable"] is True
    assert result["comparison"]["label_match"] is False
    assert result["comparison"]["value_match"] is True


# -----------------------------
# UNIT TESTS → SEQUENCE_ANY HELPERS
# -----------------------------

def test_get_candidate_expected_actions_sequence():
    validation_steps = {
        "sequence": [
            {"type": "field_changed", "label": "Name"},
            {"type": "button_clicked", "label": "Save"},
        ]
    }
    candidates = get_candidate_expected_actions(validation_steps, 0)
    assert candidates == [{"type": "field_changed", "label": "Name"}]

    candidates = get_candidate_expected_actions(validation_steps, 1)
    assert candidates == [{"type": "button_clicked", "label": "Save"}]

    candidates = get_candidate_expected_actions(validation_steps, 2)
    assert candidates == []


def test_get_candidate_expected_actions_sequence_any():
    validation_steps = {
        "sequence_any": [
            [
                {"type": "link_clicked", "label": "Product Z"},
                {"type": "button_clicked", "label": "Save"},
            ],
            [
                {"type": "field_changed", "label": "Product", "value": "Product Z"},
                {"type": "button_clicked", "label": "Save"},
            ],
        ]
    }
    candidates = get_candidate_expected_actions(validation_steps, 0)
    expected = [
        {"type": "link_clicked", "label": "Product Z"},
        {"type": "field_changed", "label": "Product", "value": "Product Z"},
    ]
    assert candidates == expected

    candidates = get_candidate_expected_actions(validation_steps, 1)
    expected = [
        {"type": "button_clicked", "label": "Save"},
        {"type": "button_clicked", "label": "Save"},
    ]
    assert candidates == expected

    candidates = get_candidate_expected_actions(validation_steps, 2)
    assert candidates == []


# -----------------------------
# INTEGRATION TEST → REINFORCE
# -----------------------------

@pytest.mark.asyncio
async def test_wrong_field_is_recoverable(monkeypatch):
    state = {"current_step": 0}

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence": [
                    {
                        "type": "field_changed",
                        "label": "Name",
                        "value": "John",
                    }
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    event = {
        "type": "field_changed",
        "label": "Email",
        "value": "test@test.com",
    }

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "recoverable_error"
    assert result["current_step"] == 0
    assert result["failure_reason"] == "wrong_field_and_value"
    assert "feedback_message" in result


@pytest.mark.asyncio
async def test_evaluate_reinforce_success(monkeypatch):
    state = {"current_step": 0}

    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence": [
                    {
                        "type": "field_changed",
                        "label": "Name",
                        "value": "John",
                    }
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "success"
    assert result["current_step"] == 1


@pytest.mark.asyncio
async def test_evaluate_reinforce_recoverable_error(monkeypatch):
    state = {"current_step": 0}

    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "Mike",
    }

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence": [
                    {
                        "type": "field_changed",
                        "label": "Name",
                        "value": "John",
                    }
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "recoverable_error"
    assert result["current_step"] == 0
    assert result["failure_reason"] == "wrong_value"
    assert "feedback_message" in result


@pytest.mark.asyncio
async def test_evaluate_reinforce_blocking_error(monkeypatch):
    state = {"current_step": 0}

    event = {
        "type": "button_clicked",
        "label": "Name",
        "value": "John",
    }

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence": [
                    {
                        "type": "field_changed",
                        "label": "Name",
                        "value": "John",
                    }
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "blocking_error"
    assert result["current_step"] == 0
    assert "feedback_message" in result


@pytest.mark.asyncio
async def test_evaluate_reinforce_sequence_progress(monkeypatch):
    state = {"current_step": 0, "step_progress": 0}

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence": [
                    {
                        "type": "button_clicked",
                        "label": "Operations",
                    },
                    {
                        "type": "tab_changed",
                        "label": "Replenishment",
                    },
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    first_event = {
        "type": "button_clicked",
        "label": "Operations",
    }
    first_result = await evaluate_reinforce(state, first_event)

    assert first_result["status"] == "success"
    assert first_result["current_step"] == 0
    assert first_result["step_progress"] == 1

    second_state = {"current_step": 0, "step_progress": 1}
    second_event = {
        "type": "tab_changed",
        "label": "Replenishment",
    }
    second_result = await evaluate_reinforce(second_state, second_event)

    assert second_result["status"] == "success"
    assert second_result["current_step"] == 1
    assert second_result["step_progress"] == 0


# -----------------------------
# END-TO-END TEST → UI FLOW
# -----------------------------

@pytest.mark.asyncio
async def test_process_ui_event_wrong_value_returns_feedback(monkeypatch, mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_wrong_value"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set Name to John",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Name",
                                        "value": "John",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "Mike",
    }

    result = await process_ui_event(
        session_id=session_id,
        event=event,
    )

    assert result is not None
    assert result["kind"] == "feedback"
    assert "John" in result["response"]
    assert result["current_step"] == 0
    assert result["exercise_id"] == "ex-test"

    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 0
    assert session["mode"] == "exercise_active"


@pytest.mark.asyncio
async def test_process_ui_event_wrong_field_and_value_is_ignored_as_noise(monkeypatch, mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_wrong_field"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set MIN to 10",
                            "validation_steps": {
                                "required_module": "stock.warehouse.orderpoint",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "MIN",
                                        "value": "10",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    event = {
        "type": "field_changed",
        "label": "RANGE",
        "value": "20",
    }

    result = await process_ui_event(
        session_id=session_id,
        event=event,
    )

    assert result is None

    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 0
    assert session["mode"] == "exercise_active"
    assert session.get("step_progress", 0) == 0


@pytest.mark.asyncio
async def test_process_ui_event_success_advances_and_returns_next_instruction(monkeypatch, mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_success"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set Name to John",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Name",
                                        "value": "John",
                                    }
                                ],
                            },
                        },
                        {
                            "instruction": "Set Email to john@example.com",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Email",
                                        "value": "john@example.com",
                                    }
                                ],
                            },
                        },
                    ]
                }
            ),
        },
    )

    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = await process_ui_event(
        session_id=session_id,
        event=event,
    )

    assert result is not None
    assert result["kind"] == "success"
    assert result["current_step"] == 1
    assert result["response"] == "Set Email to john@example.com"
    assert result["exercise_id"] == "ex-test"

    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 1
    assert session["mode"] == "exercise_active"
    assert session["required_module"] == "res.partner"


@pytest.mark.asyncio
async def test_process_ui_event_completes_exercise_when_no_next_step(monkeypatch, mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_complete"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set Name to John",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Name",
                                        "value": "John",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = await process_ui_event(
        session_id=session_id,
        event=event,
    )

    assert result is not None
    assert result["kind"] == "feedback"
    assert result["response"] == "Exercise completed."
    assert result["current_step"] == 1

    session = await redis_manager.get_session(session_id)
    assert session["mode"] == "idle"


@pytest.mark.asyncio
async def test_process_ui_event_returns_none_when_not_exercise_active(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_idle"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "idle",
            "current_step": 0,
        },
    )

    event = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result = await process_ui_event(
        session_id=session_id,
        event=event,
    )

    assert result is None


@pytest.mark.asyncio
async def test_process_ui_event_ignores_noise_event_type(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_noise"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "current_step": 0,
            "step_progress": 0,
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set Name to John",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Name",
                                        "value": "John",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "button_clicked",
            "label": "Something else",
        },
    )

    assert result is None
    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 0
    assert session.get("step_progress", 0) == 0


@pytest.mark.asyncio
async def test_process_ui_event_ignores_wrong_label_for_same_type(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_wrong_label_noise"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "current_step": 0,
            "step_progress": 0,
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Open replenishment",
                            "validation_steps": {
                                "required_module": "stock.picking.type",
                                "sequence": [
                                    {
                                        "type": "button_clicked",
                                        "label": "Operations",
                                    },
                                    {
                                        "type": "tab_changed",
                                        "label": "Replenishment",
                                    },
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "button_clicked",
            "label": "Save",
        },
    )

    assert result is None
    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 0
    assert session.get("step_progress", 0) == 0


@pytest.mark.asyncio
async def test_process_ui_event_matches_label_case_insensitively(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_label_casefold"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-casefold",
            "current_step": 0,
            "step_progress": 0,
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Open consulting hours",
                            "validation_steps": {
                                "required_module": "resource.calendar",
                                "sequence": [
                                    {
                                        "type": "button_clicked",
                                        "label": "Consulting Hours",
                                    }
                                ],
                            },
                        },
                        {
                            "instruction": "Click Save",
                            "validation_steps": {
                                "required_module": "resource.calendar",
                                "sequence": [
                                    {
                                        "type": "button_clicked",
                                        "label": "Save",
                                    }
                                ],
                            },
                        },
                    ]
                }
            ),
        },
    )

    result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "button_clicked",
            "label": " consulting hours ",
        },
    )

    assert result is not None
    assert result["kind"] == "success"
    assert result["current_step"] == 1
    assert result["response"] == "Click Save"

    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 1
    assert session.get("step_progress", 0) == 0


@pytest.mark.asyncio
async def test_process_ui_event_ignores_future_sequence_action(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_future_action_early"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "current_step": 0,
            "step_progress": 0,
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Open replenishment",
                            "validation_steps": {
                                "required_module": "stock.picking.type",
                                "sequence": [
                                    {
                                        "type": "button_clicked",
                                        "label": "Operations",
                                    },
                                    {
                                        "type": "tab_changed",
                                        "label": "Replenishment",
                                    },
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "tab_changed",
            "label": "Replenishment",
        },
    )

    assert result is None
    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 0
    assert session.get("step_progress", 0) == 0


@pytest.mark.asyncio
async def test_process_ui_event_multi_action_step_progression(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_multi_action"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "step_progress": 0,
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Open replenishment",
                            "validation_steps": {
                                "required_module": "stock.picking.type",
                                "sequence": [
                                    {
                                        "type": "button_clicked",
                                        "label": "Operations",
                                    },
                                    {
                                        "type": "tab_changed",
                                        "label": "Replenishment",
                                    },
                                ],
                            },
                        },
                        {
                            "instruction": "Click New",
                            "validation_steps": {
                                "required_module": "stock.warehouse.orderpoint",
                                "sequence": [
                                    {
                                        "type": "button_clicked",
                                        "label": "New",
                                    }
                                ],
                            },
                        },
                    ]
                }
            ),
        },
    )

    first_result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "button_clicked",
            "label": "Operations",
        },
    )

    assert first_result is None
    session_after_first = await redis_manager.get_session(session_id)
    assert session_after_first["current_step"] == 0
    assert session_after_first["step_progress"] == 1

    second_result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "tab_changed",
            "label": "Replenishment",
        },
    )

    assert second_result is not None
    assert second_result["kind"] == "success"
    assert second_result["current_step"] == 1
    assert second_result["response"] == "Click New"

    session_after_second = await redis_manager.get_session(session_id)
    assert session_after_second["current_step"] == 1
    assert session_after_second["step_progress"] == 0


@pytest.mark.asyncio
async def test_process_ui_event_sequence_any_success(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_sequence_any"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Select Product Z",
                            "validation_steps": {
                                "required_module": "stock.warehouse.orderpoint",
                                "sequence_any": [
                                    [
                                        {"type": "link_clicked", "label": "Product Z"},
                                    ],
                                    [
                                        {"type": "field_changed", "label": "Product", "value": "Product Z"},
                                    ],
                                ]
                            },
                        },
                        {
                            "instruction": "Click Save",
                            "validation_steps": {
                                "required_module": "stock.warehouse.orderpoint",
                                "sequence": [
                                    {"type": "button_clicked", "label": "Save"},
                                ]
                            },
                        },
                    ]
                }
            ),
        },
    )

    # Test first branch: link_clicked
    result1 = await process_ui_event(
        session_id=session_id,
        event={
            "type": "link_clicked",
            "label": "Product Z",
        },
    )

    assert result1 is not None
    assert result1["kind"] == "success"
    assert result1["current_step"] == 1
    assert result1["response"] == "Click Save"

    session = await redis_manager.get_session(session_id)
    assert session["current_step"] == 1
    assert session["step_progress"] == 0


@pytest.mark.asyncio
async def test_process_ui_event_sequence_any_success_second_branch(mock_redis):
    from ms_ai.app.redis_manager import redis_manager

    session_id = "test_session_sequence_any_2"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Select Product Z",
                            "validation_steps": {
                                "required_module": "stock.warehouse.orderpoint",
                                "sequence_any": [
                                    [
                                        {"type": "link_clicked", "label": "Product Z"},
                                    ],
                                    [
                                        {"type": "field_changed", "label": "Product", "value": "Product Z"},
                                    ],
                                ]
                            },
                        },
                    ]
                }
            ),
        },
    )

    # Test second branch: field_changed
    result = await process_ui_event(
        session_id=session_id,
        event={
            "type": "field_changed",
            "label": "Product",
            "value": "Product Z",
        },
    )

    assert result is not None
    assert result["kind"] == "feedback"
    assert result["response"] == "Exercise completed."
    assert result["current_step"] == 1

    session = await redis_manager.get_session(session_id)
    assert session["mode"] == "idle"


@pytest.mark.asyncio
async def test_correction_after_error(monkeypatch):
    state = {"current_step": 0}

    expected_step = {
        "validation_steps": {
            "sequence": [
                {
                    "type": "field_changed",
                    "label": "Name",
                    "value": "John",
                }
            ]
        }
    }

    def mock_get_step(state, step_index):
        return expected_step

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    wrong_event = {
        "type": "field_changed",
        "label": "Name",
        "value": "Mike",
    }

    result_wrong = await evaluate_reinforce(state, wrong_event)

    assert result_wrong["status"] == "recoverable_error"
    assert result_wrong["current_step"] == 0

    correct_event = {
        "type": "field_changed",
        "label": "Name",
        "value": "John",
    }

    result_correct = await evaluate_reinforce(state, correct_event)

    assert result_correct["status"] == "success"
    assert result_correct["current_step"] == 1

@pytest.mark.asyncio
async def test_evaluate_reinforce_sequence_any_success_first_branch(monkeypatch):
    state = {"current_step": 0, "step_progress": 0}

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence_any": [
                    [
                        {"type": "link_clicked", "label": "Product Z"},
                    ],
                    [
                        {"type": "field_changed", "label": "Product", "value": "Product Z"},
                    ],
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    event = {
        "type": "link_clicked",
        "label": "Product Z",
    }

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "success"
    assert result["current_step"] == 1
    assert result["step_progress"] == 0


@pytest.mark.asyncio
async def test_evaluate_reinforce_sequence_any_success_second_branch(monkeypatch):
    state = {"current_step": 0, "step_progress": 0}

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence_any": [
                    [
                        {"type": "link_clicked", "label": "Product Z"},
                    ],
                    [
                        {"type": "field_changed", "label": "Product", "value": "Product Z"},
                    ],
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    event = {
        "type": "field_changed",
        "label": "Product",
        "value": "Product Z",
    }

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "success"
    assert result["current_step"] == 1
    assert result["step_progress"] == 0


@pytest.mark.asyncio
async def test_evaluate_reinforce_sequence_any_failure_picks_best(monkeypatch):
    state = {"current_step": 0, "step_progress": 0}

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence_any": [
                    [
                        {"type": "link_clicked", "label": "Product Z"},
                    ],
                    [
                        {"type": "field_changed", "label": "Product", "value": "Product Z"},
                    ],
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    event = {
        "type": "field_changed",
        "label": "Product",
        "value": "Wrong Product",
    }

    result = await evaluate_reinforce(state, event)

    assert result["status"] == "recoverable_error"
    assert result["current_step"] == 0
    assert result["failure_reason"] == "wrong_value"  # Should pick the best failure
    assert "feedback_message" in result


@pytest.mark.asyncio
async def test_evaluate_reinforce_sequence_any_multi_step_progress(monkeypatch):
    state = {"current_step": 0, "step_progress": 0}

    def mock_get_step(state, step_index):
        return {
            "validation_steps": {
                "sequence_any": [
                    [
                        {"type": "link_clicked", "label": "Product Z"},
                        {"type": "button_clicked", "label": "Save"},
                    ],
                    [
                        {"type": "field_changed", "label": "Product", "value": "Product Z"},
                        {"type": "button_clicked", "label": "Save"},
                    ],
                ]
            }
        }

    monkeypatch.setattr(
        "ms_ai.app.reinforce_subagent.reinforce.get_step",
        mock_get_step,
    )

    # First event: link_clicked
    first_event = {
        "type": "link_clicked",
        "label": "Product Z",
    }
    first_result = await evaluate_reinforce(state, first_event)

    assert first_result["status"] == "success"
    assert first_result["current_step"] == 0
    assert first_result["step_progress"] == 1

    # Second event: button_clicked Save
    second_state = {"current_step": 0, "step_progress": 1}
    second_event = {
        "type": "button_clicked",
        "label": "Save",
    }
    second_result = await evaluate_reinforce(second_state, second_event)

    assert second_result["status"] == "success"
    assert second_result["current_step"] == 1
    assert second_result["step_progress"] == 0

@pytest.mark.asyncio
async def test_handle_ui_event_returns_tutor_push_on_wrong_value(monkeypatch, mock_redis):
    from ms_ai.app.websocket import websocket_handler
    from ms_ai.app.redis_manager import redis_manager

    session_id = "ws_test_session"
    user_login = "test@odooconcept.com"

    # -------------------------
    # Setup session
    # -------------------------
    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set Name to John",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Name",
                                        "value": "John",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ),
        },
    )

    # -------------------------
    # UI event (wrong value)
    # -------------------------
    message = {
        "event_name": "field_changed",
        "event_data": {
            "type": "field_changed",
            "label": "Name",
            "value": "Mike",
        },
    }

    response = await websocket_handler.handle_ui_event(
        session_id=session_id,
        user_login=user_login,
        message=message,
    )

    # -------------------------
    # Assertions
    # -------------------------
    assert response["type"] == "tutor_push"
    assert "John" in response["response"]  
    assert response["current_step"] == 0
    assert response["exercise_id"] == "ex-test"

@pytest.mark.asyncio
async def test_handle_ui_event_success_returns_next_instruction(monkeypatch, mock_redis):
    from ms_ai.app.websocket import websocket_handler
    from ms_ai.app.redis_manager import redis_manager

    session_id = "ws_test_success"
    user_login = "test@odooconcept.com"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "exercise_active",
            "exercise_id": "ex-test",
            "current_step": 0,
            "lang": "en",
            "exercise_document": json.dumps(
                {
                    "steps": [
                        {
                            "instruction": "Set Name to John",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Name",
                                        "value": "John",
                                    }
                                ],
                            },
                        },
                        {
                            "instruction": "Set Email",
                            "validation_steps": {
                                "required_module": "res.partner",
                                "sequence": [
                                    {
                                        "type": "field_changed",
                                        "label": "Email",
                                        "value": "john@example.com",
                                    }
                                ],
                            },
                        },
                    ]
                }
            ),
        },
    )

    message = {
        "event_name": "field_changed",
        "event_data": {
            "type": "field_changed",
            "label": "Name",
            "value": "John",
        },
    }

    response = await websocket_handler.handle_ui_event(
        session_id=session_id,
        user_login=user_login,
        message=message,
    )

    assert response["type"] == "tutor_push"
    assert response["current_step"] == 1
    assert response["response"] == "Set Email"

@pytest.mark.asyncio
async def test_handle_ui_event_returns_ack_when_not_in_exercise(mock_redis):
    from ms_ai.app.websocket import websocket_handler
    from ms_ai.app.redis_manager import redis_manager

    session_id = "ws_test_idle"
    user_login = "test@odooconcept.com"

    await redis_manager.store_session(
        session_id,
        {
            "mode": "idle",
        },
    )

    message = {
        "event_name": "field_changed",
        "event_data": {
            "type": "field_changed",
            "label": "Name",
            "value": "John",
        },
    }

    response = await websocket_handler.handle_ui_event(
        session_id=session_id,
        user_login=user_login,
        message=message,
    )

    assert response["type"] == "ui_event_acknowledged"