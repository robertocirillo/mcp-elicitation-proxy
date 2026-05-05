from __future__ import annotations

from typing import Any

from .base import InspectionIssue, InspectionResult


def _is_empty_required_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list | dict):
        return len(value) == 0
    return False


class SchemaRequiredPolicy:
    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        if tool_schema is None:
            return InspectionResult.ok()

        required_fields = tool_schema.get("required")
        if not isinstance(required_fields, list):
            return InspectionResult.ok()

        issues: list[InspectionIssue] = []
        for field in required_fields:
            if not isinstance(field, str):
                continue

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
