from __future__ import annotations

from collections.abc import Iterable

from .models import ElicitationField, ElicitationRequest
from ..policies.base import InspectionIssue


def build_elicitation_request(
    tool_name: str,
    issues: Iterable[InspectionIssue],
) -> ElicitationRequest:
    issue_list = list(issues)
    fields = [
        ElicitationField(
            name=issue.field or f"field_{index}",
            description=issue.message,
            required=True,
        )
        for index, issue in enumerate(issue_list, start=1)
    ]
    return ElicitationRequest(
        message=f"Additional input is required before calling `{tool_name}`.",
        fields=fields,
    )
