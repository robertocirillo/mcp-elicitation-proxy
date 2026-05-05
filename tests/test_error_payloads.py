from __future__ import annotations

import json

from mcp_elicitation_proxy.errors import (
    StructuredToolErrorPayload,
    build_elicitation_blocked_payload,
    build_tool_call_blocked_payload,
    to_json_message,
)
from mcp_elicitation_proxy.policies.base import InspectionIssue, InspectionResult


def _as_json(payload: StructuredToolErrorPayload) -> dict[str, object]:
    parsed = json.loads(to_json_message(payload))
    assert parsed == payload.model_dump()
    return parsed


def test_elicitation_disabled_payload_is_stable_json() -> None:
    payload = build_elicitation_blocked_payload(
        "search_docs",
        reason="elicitation_disabled",
        fields=["project"],
    )

    assert _as_json(payload) == {
        "error": "elicitation_required",
        "tool": "search_docs",
        "status": "needs_elicitation",
        "reason": "elicitation_disabled",
        "missing_or_ambiguous": ["project"],
        "message": "Input incompleto. Richiama il tool specificando i campi mancanti.",
    }


def test_elicitation_declined_reason_is_stable_json() -> None:
    payload = build_elicitation_blocked_payload(
        "search_docs",
        reason="elicitation_declined",
        fields=["project"],
    )

    parsed = _as_json(payload)
    assert parsed["reason"] == "elicitation_declined"
    assert parsed["status"] == "needs_elicitation"


def test_elicitation_cancelled_reason_is_stable_json() -> None:
    payload = build_elicitation_blocked_payload(
        "search_docs",
        reason="elicitation_cancelled",
        fields=["project"],
    )

    parsed = _as_json(payload)
    assert parsed["reason"] == "elicitation_cancelled"
    assert parsed["status"] == "needs_elicitation"


def test_elicitation_unsupported_reason_is_stable_json() -> None:
    payload = build_elicitation_blocked_payload(
        "search_docs",
        reason="elicitation_unsupported",
        fields=["project"],
    )

    parsed = _as_json(payload)
    assert parsed["reason"] == "elicitation_unsupported"
    assert parsed["missing_or_ambiguous"] == ["project"]


def test_sensitive_required_field_payload_is_stable_json() -> None:
    result = InspectionResult.reject(
        [
            InspectionIssue(
                field="api_key",
                reason="sensitive_required_field",
                message=(
                    "Tool call blocked because form-mode elicitation cannot "
                    "request sensitive required field 'api_key'."
                ),
            )
        ]
    )

    assert _as_json(build_tool_call_blocked_payload("save_secret", result)) == {
        "error": "tool_call_blocked",
        "tool": "save_secret",
        "status": "reject",
        "reason": "sensitive_required_field",
        "missing_or_ambiguous": ["api_key"],
        "message": (
            "Tool call blocked because form-mode elicitation cannot request "
            "sensitive required field 'api_key'."
        ),
    }


def test_multi_issue_same_reject_reason_preserves_reason() -> None:
    result = InspectionResult.reject(
        [
            InspectionIssue("api_key", "sensitive_required_field", "api_key blocked."),
            InspectionIssue("token", "sensitive_required_field", "token blocked."),
        ]
    )

    parsed = _as_json(build_tool_call_blocked_payload("save_secret", result))
    assert parsed["reason"] == "sensitive_required_field"
    assert parsed["missing_or_ambiguous"] == ["api_key", "token"]
    assert parsed["message"] == "api_key blocked. token blocked."


def test_multi_issue_mixed_reject_reasons_use_policy_rejected() -> None:
    result = InspectionResult.reject(
        [
            InspectionIssue("api_key", "sensitive_required_field", "api_key blocked."),
            InspectionIssue("item_id", "confirmation_required", "confirmation needed."),
        ]
    )

    parsed = _as_json(build_tool_call_blocked_payload("save_secret", result))
    assert parsed["reason"] == "policy_rejected"
    assert parsed["missing_or_ambiguous"] == ["api_key", "item_id"]
