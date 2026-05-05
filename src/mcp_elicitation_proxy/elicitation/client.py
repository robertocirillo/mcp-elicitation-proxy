from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import mcp.types as mt
from pydantic import BaseModel

from .builder import build_elicitation_request
from ..policies.base import InspectionIssue


logger = logging.getLogger(__name__)


class ElicitationOutcomeStatus(StrEnum):
    ACCEPTED = "accepted"
    UNAVAILABLE = "unavailable"
    DECLINED = "elicitation_declined"
    CANCELLED = "elicitation_cancelled"
    FAILED = "elicitation_failed"


@dataclass(slots=True)
class ElicitationOutcome:
    status: ElicitationOutcomeStatus
    fields: list[str]
    values: dict[str, Any] | None = None
    message: str | None = None

    @classmethod
    def accepted(
        cls,
        fields: list[str],
        values: dict[str, Any],
    ) -> "ElicitationOutcome":
        return cls(
            status=ElicitationOutcomeStatus.ACCEPTED,
            fields=fields,
            values=values,
        )

    @classmethod
    def unavailable(cls, fields: list[str]) -> "ElicitationOutcome":
        return cls(status=ElicitationOutcomeStatus.UNAVAILABLE, fields=fields)

    @classmethod
    def blocked(
        cls,
        status: ElicitationOutcomeStatus,
        fields: list[str],
        message: str,
    ) -> "ElicitationOutcome":
        return cls(status=status, fields=fields, message=message)


async def request_missing_values(
    context: Any,
    tool_name: str,
    issues: list[InspectionIssue],
    tool_schema: dict[str, Any] | None,
) -> ElicitationOutcome:
    request = build_elicitation_request(tool_name, issues, tool_schema)
    fields = [field.name for field in request.fields]
    if not fields or request.response_model is None:
        return ElicitationOutcome.unavailable(fields)

    elicit = getattr(context, "elicit", None)
    if not callable(elicit):
        return ElicitationOutcome.unavailable(fields)
    if not _client_supports_elicitation(context):
        return ElicitationOutcome.unavailable(fields)

    try:
        response = await elicit(request.message, request.response_model)
    except Exception:
        logger.warning(
            "Elicitation failed for tool %r; returning structured fallback.",
            tool_name,
            exc_info=True,
        )
        return ElicitationOutcome.blocked(
            ElicitationOutcomeStatus.FAILED,
            fields,
            "Elicitation failed before values were provided.",
        )

    action = getattr(response, "action", None)
    if action == "accept":
        values = _accepted_values(response)
        if values is None:
            return ElicitationOutcome.blocked(
                ElicitationOutcomeStatus.FAILED,
                fields,
                "Elicitation accepted but did not provide structured values.",
            )
        return ElicitationOutcome.accepted(fields, values)

    if action == "decline":
        return ElicitationOutcome.blocked(
            ElicitationOutcomeStatus.DECLINED,
            fields,
            "Elicitation was rejected before the upstream tool call.",
        )

    if action == "cancel":
        return ElicitationOutcome.blocked(
            ElicitationOutcomeStatus.CANCELLED,
            fields,
            "Elicitation was cancelled before the upstream tool call.",
        )

    return ElicitationOutcome.blocked(
        ElicitationOutcomeStatus.FAILED,
        fields,
        "Elicitation returned an unsupported response.",
    )


def merge_elicited_values(
    arguments: dict[str, Any],
    values: dict[str, Any],
    fields: list[str],
) -> dict[str, Any]:
    updated_arguments = dict(arguments)
    for field in fields:
        if field in values:
            updated_arguments[field] = values[field]
    return updated_arguments


def _accepted_values(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    if data is None:
        data = getattr(response, "content", None)

    if isinstance(data, BaseModel):
        return data.model_dump(by_alias=True)

    if isinstance(data, dict):
        return dict(data)

    return None


def _client_supports_elicitation(context: Any) -> bool:
    session = getattr(context, "session", None)
    check_client_capability = getattr(session, "check_client_capability", None)
    if not callable(check_client_capability):
        return True

    return bool(
        check_client_capability(
            mt.ClientCapabilities(elicitation=mt.ElicitationCapability())
        )
    )
