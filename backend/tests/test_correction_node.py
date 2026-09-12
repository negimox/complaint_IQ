"""Unit tests for the Correction Node (intent diffing, field restrictions, audit readiness)."""
import pytest
from unittest.mock import patch, MagicMock
from app.agents.nodes.correction_node import (
    ALLOWED_CORRECTION_FIELDS,
    execute_correction,
)


def test_allowed_correction_fields_contain_core_qms():
    """Verify that ALLOWED_CORRECTION_FIELDS covers all editable QMS fields."""
    expected = {
        "customer_name",
        "product_name",
        "batch_lot_number",
        "complaint_category",
        "manufacturing_date",
        "expiry_date",
        "affected_quantity",
        "severity_suggested",
        "priority",
    }
    assert expected.issubset(ALLOWED_CORRECTION_FIELDS)


def test_execute_correction_filters_unauthorized_fields():
    """Verify that fields outside ALLOWED_CORRECTION_FIELDS are stripped from diffs."""
    mock_llm_response = {
        "is_correction": True,
        "diffs": [
            {"field": "batch_lot_number", "old_value": "OLD-1", "new_value": "NEW-2"},
            {"field": "unauthorized_secret_field", "old_value": "A", "new_value": "B"},
            {"field": "id", "old_value": "CC-1", "new_value": "CC-999"},  # immutable key
        ],
        "reply": "I have updated the batch number to NEW-2.",
    }

    import json
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = json.dumps(mock_llm_response)
    mock_client.chat.completions.create.return_value = mock_completion

    with patch("app.agents.nodes.correction_node.Groq", return_value=mock_client):
        result = execute_correction(
            current_complaint={"batch_lot_number": "OLD-1"},
            user_message="Change batch to NEW-2",
        )

    # Diffs should ONLY include allowed fields
    diff_fields = [d["field"] for d in result["diffs"]]
    assert "batch_lot_number" in diff_fields
    assert "unauthorized_secret_field" not in diff_fields
    assert "id" not in diff_fields
    assert result["reply"] != ""


def test_execute_correction_handles_non_json_fallback():
    """Verify that non-JSON output from LLM degrades gracefully into a general conversational reply."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = "I could not find the batch number in our database."
    mock_client.chat.completions.create.return_value = mock_completion

    with patch("app.agents.nodes.correction_node.Groq", return_value=mock_client):
        result = execute_correction(
            current_complaint={"batch_lot_number": "BAT-123"},
            user_message="What batch number is this?",
        )

    assert result["is_correction"] is False
    assert len(result["diffs"]) == 0
    assert "batch number" in result["reply"]
