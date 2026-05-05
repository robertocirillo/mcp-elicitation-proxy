from __future__ import annotations

import json

from pydantic import BaseModel, Field

from .policies.base import InspectionIssue, InspectionResult, InspectionStatus


class StructuredToolErrorPayload(BaseModel):
    error: str
    tool: str
    status: str
    reason: str
    missing_or_ambiguous: list[str] = Field(default_factory=list)
    message: str


def build_tool_call_blocked_payload(
    tool_name: str,
    result: InspectionResult,
) -> StructuredToolErrorPayload:
    """Build the Task 3 structured-result fallback, not an MCP protocol error."""
    return StructuredToolErrorPayload(
        error="tool_call_blocked",
        tool=tool_name,
        status=result.status.value,
        reason=_reason_for(result),
        missing_or_ambiguous=_fields_for(result.issues),
        message=_message_for(result),
    )


def build_elicitation_blocked_payload(
    tool_name: str,
    *,
    reason: str,
    fields: list[str],
    message: str | None = None,
) -> StructuredToolErrorPayload:
    return StructuredToolErrorPayload(
        error="elicitation_required",
        tool=tool_name,
        status=InspectionStatus.NEEDS_ELICITATION.value,
        reason=reason,
        missing_or_ambiguous=fields,
        message=message
        or "Input incompleto. Richiama il tool specificando i campi mancanti.",
    )


def to_json_message(payload: StructuredToolErrorPayload) -> str:
    return json.dumps(payload.model_dump())


def _reason_for(result: InspectionResult) -> str:
    if result.status == InspectionStatus.NEEDS_ELICITATION:
        return "required_fields_missing_or_empty"
    if result.status == InspectionStatus.REJECT:
        reasons = {issue.reason for issue in result.issues if issue.reason}
        if len(reasons) == 1:
            return next(iter(reasons))
        if reasons:
            return "policy_rejected"
    return result.status.value


def _fields_for(issues: list[InspectionIssue]) -> list[str]:
    return [issue.field for issue in issues if issue.field is not None]


def _message_for(result: InspectionResult) -> str:
    if result.status == InspectionStatus.NEEDS_ELICITATION:
        fields = _fields_for(result.issues)
        if fields:
            return "Tool call requires additional input for: " + ", ".join(fields) + "."
        return "Tool call requires additional input."

    messages = [issue.message for issue in result.issues]
    return " ".join(messages) if messages else "Tool call was blocked."
