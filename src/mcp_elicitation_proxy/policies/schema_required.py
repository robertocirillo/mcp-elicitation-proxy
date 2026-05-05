from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .base import InspectionIssue, InspectionResult
from .required_fields import combined_required_fields


def _is_empty_required_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list | dict):
        return len(value) == 0
    return False


class SchemaRequiredPolicy:
    def __init__(
        self,
        tool_required_fields: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._tool_required_fields = {
            tool_name: list(required_fields)
            for tool_name, required_fields in (tool_required_fields or {}).items()
        }

    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        required_fields = combined_required_fields(
            tool_name, tool_schema, self._tool_required_fields
        )
        if not required_fields:
            return InspectionResult.ok()

        issues: list[InspectionIssue] = []
        for field in required_fields:
            if field not in arguments:
                issues.append(
                    InspectionIssue(
                        field=field,
                        reason="missing_required_field",
                        message=f"Required field '{field}' is missing.",
                    )
                )
                continue

            if _is_empty_required_value(arguments[field]):
                issues.append(
                    InspectionIssue(
                        field=field,
                        reason="empty_required_field",
                        message=f"Required field '{field}' is empty.",
                    )
                )

        if issues:
            return InspectionResult.needs_elicitation(issues)

        return InspectionResult.ok()
